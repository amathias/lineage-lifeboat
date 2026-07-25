from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from datahub.metadata.schema_classes import StatusClass

from lineage_lifeboat.config import Settings
from lineage_lifeboat.datahub_vertical_slice import (
    CONTEXT_RECEIPT,
    CONTROL_URNS,
    DATAHUB_SEED_RECEIPT,
    DEFAULT_WRITEBACK_TARGET,
    PROJECT_TAG_URN,
    RESET_RECEIPT,
    VERTICAL_SLICE_RECEIPT,
    WRITEBACK_RECEIPT,
    WRITEBACK_TAG_URN,
    DataHubSdkMutationPort,
    McpContractError,
    MissingDataHubTokenError,
    ResetConfirmationError,
    WritebackVerificationError,
    reset_datahub,
    run_vertical_slice,
    seed_datahub,
    writeback_and_verify,
    _assert_lineage_evidence,
    _entity_arguments,
    _lineage_arguments,
)
from lineage_lifeboat.domain.models import GraphSnapshot
from lineage_lifeboat.safety import NamespaceViolationError

ROOT = Path(__file__).resolve().parents[1]
FOREIGN_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:duckdb,other.analytics.revenue,PROD)"
)
NAMESPACED_BUT_UNKNOWN_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.unknown.asset,PROD)"
)


def _settings(tmp_path: Path, *, token: str | None = None) -> Settings:
    return replace(
        Settings.from_env({}),
        app_state_dir=tmp_path / "lineage-lifeboat",
        datahub_token=token,
    )


def _snapshot() -> GraphSnapshot:
    path = ROOT / "demo" / "fixtures" / "lineage-lifeboat" / "graph_snapshot.json"
    return GraphSnapshot.model_validate_json(path.read_text(encoding="utf-8"))


class FakeMutationPort:
    def __init__(self) -> None:
        self.seeded: tuple[str, ...] = ()
        self.writebacks: list[tuple[str, str]] = []
        self.resets: tuple[str, ...] = ()

    def seed(self, snapshot: GraphSnapshot) -> dict[str, Any]:
        self.seeded = tuple(sorted(asset.urn for asset in snapshot.assets))
        return {
            "asset_urns": list(self.seeded),
            "control_urns": list(CONTROL_URNS),
            "emitted_aspect_count": 48,
            "lineage_edge_count": len(snapshot.edges),
        }

    def writeback(self, target_urn: str, run_id: str) -> dict[str, Any]:
        self.writebacks.append((target_urn, run_id))
        return {
            "mutation": "globalTags UPSERT",
            "target_urn": target_urn,
            "marker_tag_urn": WRITEBACK_TAG_URN,
            "run_id": run_id,
        }

    def reset(self, snapshot: GraphSnapshot) -> dict[str, Any]:
        self.resets = tuple(sorted(asset.urn for asset in snapshot.assets))
        return {
            "delete_mode": "dataset_status_soft_delete",
            "asset_urns": list(self.resets),
            "soft_deleted_asset_count": len(self.resets),
            "retained_control_urns": list(CONTROL_URNS),
            "retained_control_count": len(CONTROL_URNS),
            "idempotent": True,
            "reseed_restores_assets": True,
        }


class FakeContextPort:
    def __init__(self, snapshot: GraphSnapshot, *, include_marker: bool = True) -> None:
        self.snapshot = snapshot
        self.include_marker = include_marker

    async def read_context(
        self, urns: tuple[str, ...] | list[str], lineage_roots: tuple[str, ...] | list[str]
    ) -> dict[str, Any]:
        return {
            "advertised_tools": ["get_entities", "get_lineage"],
            "get_entities": [{"result": {"content": list(urns)}}],
            "get_lineage": [
                {
                    "arguments": {"urn": root, "upstream": False, "max_hops": 1},
                    "result": {
                        "content": [
                            edge.downstream_urn
                            for edge in self.snapshot.edges
                            if edge.upstream_urn == root
                        ]
                    },
                }
                for root in lineage_roots
            ],
        }

    async def read_entities(
        self, urns: tuple[str, ...] | list[str]
    ) -> dict[str, Any]:
        content = list(urns)
        if self.include_marker:
            content.append(WRITEBACK_TAG_URN)
        return {
            "advertised_tools": ["get_entities"],
            "get_entities": [{"result": {"content": content}}],
        }


class FakeEmitter:
    def __init__(self) -> None:
        self.proposals: list[Any] = []

    def emit_mcp(self, proposal: Any) -> None:
        self.proposals.append(proposal)


class DataHub160StrictEmitter(FakeEmitter):
    def emit_mcp(self, proposal: Any) -> None:
        if proposal.entityUrn in CONTROL_URNS and isinstance(
            proposal.aspect, StatusClass
        ):
            raise AssertionError("DataHub 1.6.0 rejects status on Domain and Tag")
        super().emit_mcp(proposal)



def test_official_mcp_tool_schemas_produce_downstream_batch_arguments() -> None:
    assert _entity_arguments(
        {"properties": {"urns": {"type": ["array", "string"]}}},
        ["urn:one", "urn:two"],
    ) == [{"urns": ["urn:one", "urn:two"]}]
    assert _lineage_arguments(
        {
            "properties": {
                "urn": {"type": "string"},
                "upstream": {"type": "boolean", "default": True},
                "max_hops": {"type": "integer", "default": 1},
                "max_results": {"type": "integer", "default": 30},
            }
        },
        "urn:root",
    ) == {
        "urn": "urn:root",
        "upstream": False,
        "max_hops": 1,
        "max_results": 100,
    }


@pytest.mark.parametrize(
    "argument_name",
    ("max_results", "maxResults", "limit", "count", "page_size", "pageSize"),
)
def test_lineage_result_limit_honors_advertised_aliases(argument_name: str) -> None:
    arguments = _lineage_arguments(
        {
            "properties": {
                "urn": {"type": "string"},
                argument_name: {"type": "integer", "maximum": 75},
            }
        },
        "urn:root",
    )

    assert arguments[argument_name] == 75


def test_lineage_evidence_requires_both_revenue_downstream_edges() -> None:
    snapshot = _snapshot()
    revenue_edges = tuple(
        edge
        for edge in snapshot.edges
        if "lifeboat.analytics.customer_revenue" in edge.upstream_urn
    )
    assert len(revenue_edges) == 2
    sibling_snapshot = snapshot.model_copy(update={"edges": revenue_edges})
    lineage_call = {
        "arguments": {
            "urn": revenue_edges[0].upstream_urn,
            "upstream": False,
            "max_hops": 1,
            "max_results": 100,
        },
        "result": {"content": [edge.downstream_urn for edge in revenue_edges]},
    }

    _assert_lineage_evidence({"get_lineage": [lineage_call]}, sibling_snapshot)

    lineage_call["result"] = {"content": [revenue_edges[0].downstream_urn]}
    with pytest.raises(McpContractError, match="dashboards.executive_revenue"):
        _assert_lineage_evidence({"get_lineage": [lineage_call]}, sibling_snapshot)


def test_real_mutation_port_fails_honestly_without_token(tmp_path: Path) -> None:
    with pytest.raises(MissingDataHubTokenError, match="DATAHUB_TOKEN"):
        DataHubSdkMutationPort(_settings(tmp_path))


def test_sdk_seed_emits_only_fixture_and_exact_project_controls(tmp_path: Path) -> None:
    emitter = FakeEmitter()
    settings = _settings(tmp_path, token="test-only-token")
    port = DataHubSdkMutationPort(settings, emitter=emitter)  # type: ignore[arg-type]

    evidence = port.seed(_snapshot())

    emitted_urns = {proposal.entityUrn for proposal in emitter.proposals}
    fixture_urns = {asset.urn for asset in _snapshot().assets}
    assert emitted_urns == fixture_urns | set(CONTROL_URNS)
    assert all("lifeboat." in urn for urn in fixture_urns)
    assert evidence["lineage_edge_count"] == 6
    assert evidence["emitted_aspect_count"] == len(emitter.proposals) == 48
    assert PROJECT_TAG_URN in emitted_urns


def test_sdk_reset_retains_controls_and_reseed_restores_partial_reset(
    tmp_path: Path,
) -> None:
    emitter = DataHub160StrictEmitter()
    settings = _settings(tmp_path, token="test-only-token")
    port = DataHubSdkMutationPort(settings, emitter=emitter)  # type: ignore[arg-type]
    snapshot = _snapshot()
    fixture_urns = tuple(sorted(asset.urn for asset in snapshot.assets))
    partially_reset_urns = fixture_urns[:3]
    for urn in partially_reset_urns:
        port._emit(urn, StatusClass(removed=True))

    first = port.reset(snapshot)
    second = port.reset(snapshot)

    assert first == second
    assert first["asset_urns"] == list(fixture_urns)
    assert first["soft_deleted_asset_count"] == 8
    assert first["retained_control_urns"] == list(CONTROL_URNS)
    assert first["retained_control_count"] == 3
    assert first["idempotent"] is True
    assert first["reseed_restores_assets"] is True

    port.seed(snapshot)

    status_by_urn = {
        urn: [
            proposal.aspect.removed
            for proposal in emitter.proposals
            if proposal.entityUrn == urn
            and isinstance(proposal.aspect, StatusClass)
        ]
        for urn in fixture_urns
    }
    assert status_by_urn == {
        urn: ([True, True, True, False] if urn in partially_reset_urns else [True, True, False])
        for urn in fixture_urns
    }
    assert not any(
        proposal.entityUrn in CONTROL_URNS
        and isinstance(proposal.aspect, StatusClass)
        for proposal in emitter.proposals
    )


def test_seed_receipt_does_not_persist_token(tmp_path: Path) -> None:
    settings = _settings(tmp_path, token="receipt-must-not-contain-this")
    mutation = FakeMutationPort()

    receipt = seed_datahub(settings, mutation)
    persisted = (settings.app_state_dir / "datahub-receipts" / DATAHUB_SEED_RECEIPT).read_text()

    assert receipt["datahub_seeded"] is True
    assert "receipt-must-not-contain-this" not in persisted
    assert mutation.seeded == tuple(sorted(asset.urn for asset in _snapshot().assets))


def test_writeback_is_fixture_guarded_and_requires_mcp_marker(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    mutation = FakeMutationPort()
    reader = FakeContextPort(_snapshot(), include_marker=False)

    with pytest.raises(WritebackVerificationError, match="marker tag"):
        asyncio.run(
            writeback_and_verify(
                settings,
                run_id="milestone-b-test",
                mutation_port=mutation,
                context_port=reader,
            )
        )
    assert mutation.writebacks == [(DEFAULT_WRITEBACK_TARGET, "milestone-b-test")]
    assert not (settings.app_state_dir / "datahub-receipts" / WRITEBACK_RECEIPT).exists()

    with pytest.raises(NamespaceViolationError, match="outside"):
        asyncio.run(
            writeback_and_verify(
                settings,
                run_id="foreign",
                target_urn=FOREIGN_URN,
                mutation_port=mutation,
                context_port=reader,
            )
        )
    with pytest.raises(NamespaceViolationError, match="absent"):
        asyncio.run(
            writeback_and_verify(
                settings,
                run_id="unknown",
                target_urn=NAMESPACED_BUT_UNKNOWN_URN,
                mutation_port=mutation,
                context_port=reader,
            )
        )


def test_vertical_slice_preserves_all_verifiable_receipts(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    snapshot = _snapshot()
    mutation = FakeMutationPort()
    reader = FakeContextPort(snapshot)

    receipt = asyncio.run(
        run_vertical_slice(
            settings,
            run_id="milestone-b-test",
            mutation_port=mutation,
            context_port=reader,
        )
    )

    receipt_dir = settings.app_state_dir / "datahub-receipts"
    assert receipt["verified"] is True
    assert mutation.writebacks == [(DEFAULT_WRITEBACK_TARGET, "milestone-b-test")]
    assert {
        DATAHUB_SEED_RECEIPT,
        CONTEXT_RECEIPT,
        WRITEBACK_RECEIPT,
        VERTICAL_SLICE_RECEIPT,
    }.issubset(path.name for path in receipt_dir.iterdir())
    writeback = json.loads((receipt_dir / WRITEBACK_RECEIPT).read_text())
    assert writeback["verification"]["verified"] is True
    assert writeback["verification"]["marker_tag_urn"] == WRITEBACK_TAG_URN


def test_reset_requires_exact_confirmation_and_targets_only_fixture(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    mutation = FakeMutationPort()

    with pytest.raises(ResetConfirmationError, match="confirm-project"):
        reset_datahub(settings, "another-project", mutation)
    assert mutation.resets == ()

    receipt = reset_datahub(settings, "lineage-lifeboat", mutation)

    fixture_urns = tuple(sorted(asset.urn for asset in _snapshot().assets))
    assert mutation.resets == fixture_urns
    assert receipt["completed"] is True
    assert receipt["status"] == "completed"
    assert receipt["readiness"]["invalidated_before_mutation"] is True
    assert receipt["target_asset_urns"] == list(fixture_urns)
    assert receipt["retained_control_urns"] == list(CONTROL_URNS)
    assert receipt["evidence"]["retained_control_urns"] == list(CONTROL_URNS)
    assert receipt["evidence"]["soft_deleted_asset_count"] == 8
    assert FOREIGN_URN not in receipt["evidence"]["asset_urns"]
    assert (settings.app_state_dir / "datahub-receipts" / RESET_RECEIPT).is_file()
    invalidation = json.loads(
        (
            settings.app_state_dir
            / "datahub-receipts"
            / VERTICAL_SLICE_RECEIPT
        ).read_text()
    )
    assert invalidation["operation"] == "datahub_vertical_slice_invalidated"
    assert invalidation["verified"] is False
