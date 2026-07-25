from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

import networkx as nx

from lineage_lifeboat.domain.models import (
    AssetAvailability,
    AssetSelection,
    GraphSnapshot,
    RecoveryPlan,
    RecoveryRequest,
    RecoveryStep,
    SelectionDecision,
)
from lineage_lifeboat.safety import DataHubScopePolicy


class RecoveryPlanningError(ValueError):
    """Base error for plans that cannot be compiled safely."""


class UnknownAssetError(RecoveryPlanningError):
    pass


class InvalidLineageError(RecoveryPlanningError):
    pass


class RecoveryCycleError(RecoveryPlanningError):
    pass


class MissingAdapterError(RecoveryPlanningError):
    pass


class UnresolvedPrerequisiteError(RecoveryPlanningError):
    pass


class RecoveryCompiler:
    """Compile DataHub-shaped context into a deterministic recovery DAG."""

    compiler_version = "0.1.0"

    def __init__(
        self,
        supported_adapters: Iterable[str],
        scope_policy: DataHubScopePolicy,
    ) -> None:
        self._supported_adapters = frozenset(supported_adapters)
        self._scope_policy = scope_policy

    def compile(
        self, request: RecoveryRequest, snapshot: GraphSnapshot
    ) -> RecoveryPlan:
        self._scope_policy.assert_snapshot(snapshot)
        assets = {asset.urn: asset for asset in snapshot.assets}
        graph = self._build_graph(snapshot, assets)

        unknown_requested = sorted(set(request.unavailable_asset_urns) - assets.keys())
        if unknown_requested:
            raise UnknownAssetError(
                f"requested assets are absent from the graph snapshot: {unknown_requested}"
            )

        recovery_targets, distances = self._discover_targets(request, graph, assets)
        recovery_graph = graph.subgraph(recovery_targets).copy()
        self._assert_acyclic(recovery_graph)
        self._assert_supported(recovery_targets, assets)

        plan_id = self._plan_id(request, snapshot.fingerprint)
        step_ids = {
            urn: self._step_id(plan_id, urn) for urn in sorted(recovery_targets)
        }

        ordered_urns = tuple(nx.lexicographical_topological_sort(recovery_graph))
        steps = tuple(
            self._compile_step(
                urn=urn,
                graph=graph,
                recovery_targets=recovery_targets,
                assets=assets,
                step_ids=step_ids,
            )
            for urn in ordered_urns
        )
        waves = tuple(
            tuple(step_ids[urn] for urn in wave)
            for wave in self._topological_waves(recovery_graph)
        )
        selections = self._selection_evidence(
            graph=graph,
            assets=assets,
            recovery_targets=recovery_targets,
            distances=distances,
            max_depth=request.max_blast_radius_depth,
        )

        return RecoveryPlan(
            plan_id=plan_id,
            compiler_version=self.compiler_version,
            request_id=request.request_id,
            graph_fingerprint=snapshot.fingerprint,
            steps=steps,
            waves=waves,
            selections=selections,
        )

    @staticmethod
    def _build_graph(snapshot: GraphSnapshot, assets: dict[str, object]) -> nx.DiGraph:
        graph = nx.DiGraph()
        graph.add_nodes_from(sorted(assets))
        for edge in sorted(
            snapshot.edges,
            key=lambda item: (item.upstream_urn, item.downstream_urn),
        ):
            missing = [
                urn
                for urn in (edge.upstream_urn, edge.downstream_urn)
                if urn not in assets
            ]
            if missing:
                raise InvalidLineageError(
                    f"lineage edge references assets absent from the snapshot: {missing}"
                )
            graph.add_edge(
                edge.upstream_urn,
                edge.downstream_urn,
                evidence=edge.evidence,
            )
        return graph

    @staticmethod
    def _discover_targets(
        request: RecoveryRequest,
        graph: nx.DiGraph,
        assets: dict[str, object],
    ) -> tuple[set[str], dict[str, int]]:
        targets: set[str] = set()
        distances: dict[str, int] = {}
        for source in request.unavailable_asset_urns:
            discovered = nx.single_source_shortest_path_length(
                graph,
                source,
                cutoff=request.max_blast_radius_depth,
            )
            for urn, distance in discovered.items():
                targets.add(urn)
                distances[urn] = min(distance, distances.get(urn, distance))

        # If an impacted consumer has another unavailable prerequisite, that
        # prerequisite must also become a recovery target.
        changed = True
        while changed:
            changed = False
            for target in sorted(targets):
                for upstream in sorted(graph.predecessors(target)):
                    availability = assets[upstream].availability
                    if (
                        availability == AssetAvailability.UNAVAILABLE
                        and upstream not in targets
                    ):
                        targets.add(upstream)
                        changed = True
        return targets, distances

    @staticmethod
    def _assert_acyclic(graph: nx.DiGraph) -> None:
        if nx.is_directed_acyclic_graph(graph):
            return
        cycle = nx.find_cycle(graph)
        rendered = " -> ".join(edge[0] for edge in cycle) + f" -> {cycle[0][0]}"
        raise RecoveryCycleError(f"affected recovery graph contains a cycle: {rendered}")

    def _assert_supported(
        self,
        recovery_targets: set[str],
        assets: dict[str, object],
    ) -> None:
        for urn in sorted(recovery_targets):
            adapter = assets[urn].adapter
            if not adapter:
                raise MissingAdapterError(f"recovery target has no adapter: {urn}")
            if adapter not in self._supported_adapters:
                raise MissingAdapterError(
                    f"adapter {adapter!r} for {urn} is not registered"
                )

    @staticmethod
    def _compile_step(
        *,
        urn: str,
        graph: nx.DiGraph,
        recovery_targets: set[str],
        assets: dict[str, object],
        step_ids: dict[str, str],
    ) -> RecoveryStep:
        dependencies: list[str] = []
        healthy_preconditions: list[str] = []
        for upstream in sorted(graph.predecessors(urn)):
            if upstream in recovery_targets:
                dependencies.append(step_ids[upstream])
                continue
            availability = assets[upstream].availability
            if availability == AssetAvailability.HEALTHY:
                healthy_preconditions.append(upstream)
                continue
            raise UnresolvedPrerequisiteError(
                f"{urn} requires prerequisite {upstream} with state {availability}"
            )

        asset = assets[urn]
        return RecoveryStep(
            step_id=step_ids[urn],
            target_urn=urn,
            dependency_step_ids=tuple(dependencies),
            healthy_precondition_urns=tuple(healthy_preconditions),
            adapter=asset.adapter,
            adapter_parameters=asset.adapter_parameters,
            validations=asset.validations,
            risk=asset.risk,
            requires_approval=asset.requires_approval,
        )

    @staticmethod
    def _topological_waves(graph: nx.DiGraph) -> tuple[tuple[str, ...], ...]:
        remaining = graph.copy()
        waves: list[tuple[str, ...]] = []
        while remaining:
            ready = tuple(
                sorted(node for node, degree in remaining.in_degree() if degree == 0)
            )
            if not ready:
                raise RecoveryCycleError("affected recovery graph contains a cycle")
            waves.append(ready)
            remaining.remove_nodes_from(ready)
        return tuple(waves)

    @staticmethod
    def _selection_evidence(
        *,
        graph: nx.DiGraph,
        assets: dict[str, object],
        recovery_targets: set[str],
        distances: dict[str, int],
        max_depth: int,
    ) -> tuple[AssetSelection, ...]:
        healthy_prerequisites = {
            upstream
            for target in recovery_targets
            for upstream in graph.predecessors(target)
            if upstream not in recovery_targets
            and assets[upstream].availability == AssetAvailability.HEALTHY
        }
        selections: list[AssetSelection] = []
        for urn in sorted(assets):
            if urn in recovery_targets:
                decision = SelectionDecision.RECOVERY_TARGET
                reason = "selected outage asset or downstream impact"
            elif urn in healthy_prerequisites:
                decision = SelectionDecision.HEALTHY_PRECONDITION
                reason = "required upstream asset is healthy and must pass preflight"
            elif urn in distances and distances[urn] > max_depth:
                decision = SelectionDecision.EXCLUDED
                reason = "outside the configured blast-radius depth"
            else:
                decision = SelectionDecision.EXCLUDED
                reason = "not connected to the selected outage scope"
            selections.append(
                AssetSelection(urn=urn, decision=decision, reason=reason)
            )
        return tuple(selections)

    def _plan_id(self, request: RecoveryRequest, graph_fingerprint: str) -> str:
        payload = {
            "compiler_version": self.compiler_version,
            "graph_fingerprint": graph_fingerprint,
            "request": request.model_dump(mode="json"),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]
        return f"plan-{digest}"

    @staticmethod
    def _step_id(plan_id: str, urn: str) -> str:
        digest = hashlib.sha256(f"{plan_id}:{urn}".encode("utf-8")).hexdigest()[:16]
        return f"step-{digest}"

