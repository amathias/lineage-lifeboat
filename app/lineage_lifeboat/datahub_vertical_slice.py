from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    DatasetPropertiesClass,
    DomainsClass,
    DomainPropertiesClass,
    GlobalTagsClass,
    OwnerClass,
    OwnershipClass,
    StatusClass,
    TagAssociationClass,
    TagPropertiesClass,
    UpstreamClass,
    UpstreamLineageClass,
)
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from lineage_lifeboat.config import Settings
from lineage_lifeboat.demo_state import _assert_safe_state_dir, _load_fixture
from lineage_lifeboat.domain.models import AssetContext, GraphSnapshot
from lineage_lifeboat.safety import DataHubScopePolicy, NamespaceViolationError

PROJECT_DOMAIN_URN = "urn:li:domain:lifeboat"
PROJECT_TAG_URN = "urn:li:tag:project-lineage-lifeboat"
WRITEBACK_TAG = "lifeboat-recovery-verified"
WRITEBACK_TAG_URN = f"urn:li:tag:{WRITEBACK_TAG}"
CONTROL_URNS = (PROJECT_DOMAIN_URN, PROJECT_TAG_URN, WRITEBACK_TAG_URN)
DEFAULT_WRITEBACK_TARGET = (
    "urn:li:dataset:(urn:li:dataPlatform:duckdb,"
    "lifeboat.analytics.customer_revenue,PROD)"
)
CONTEXT_RECEIPT = "context-read-receipt.json"
DATAHUB_SEED_RECEIPT = "datahub-seed-receipt.json"
RESET_RECEIPT = "datahub-reset-receipt.json"
WRITEBACK_RECEIPT = "writeback-receipt.json"
VERTICAL_SLICE_RECEIPT = "vertical-slice-receipt.json"
MCP_LINEAGE_RESULT_LIMIT = 100


class DataHubIntegrationError(RuntimeError):
    """Base error for a failed or unverifiable DataHub operation."""


class MissingDataHubTokenError(DataHubIntegrationError):
    """Raised before any GMS mutation when no token is configured."""


class McpContractError(DataHubIntegrationError):
    """Raised when the MCP server lacks or violates the required read contract."""


class WritebackVerificationError(DataHubIntegrationError):
    """Raised when the immediate MCP reread does not prove the writeback."""


class ResetConfirmationError(DataHubIntegrationError):
    """Raised when the explicit project reset confirmation is absent or wrong."""


class MutationPort(Protocol):
    def seed(self, snapshot: GraphSnapshot) -> Mapping[str, Any]: ...

    def writeback(self, target_urn: str, run_id: str) -> Mapping[str, Any]: ...

    def reset(self, snapshot: GraphSnapshot) -> Mapping[str, Any]: ...


class ContextPort(Protocol):
    async def read_context(
        self, urns: Sequence[str], lineage_roots: Sequence[str]
    ) -> Mapping[str, Any]: ...

    async def read_entities(self, urns: Sequence[str]) -> Mapping[str, Any]: ...


def _scope_policy(settings: Settings) -> DataHubScopePolicy:
    return DataHubScopePolicy(
        domain=settings.datahub_domain,
        required_tag=settings.datahub_project_tag,
        urn_prefix=settings.datahub_urn_prefix,
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _receipt_path(settings: Settings, filename: str) -> Path:
    state_dir = _assert_safe_state_dir(settings.app_state_dir)
    receipt_dir = state_dir / "datahub-receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    return receipt_dir / filename


def _assert_no_secret_material(payload: Any, token: str | None) -> None:
    sensitive_keys = {
        "apikey",
        "authorization",
        "cookie",
        "datahubtoken",
        "refreshtoken",
        "secret",
        "setcookie",
        "token",
        "accesstoken",
    }

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                normalized_key = re.sub(r"[^a-z]", "", str(key).lower())
                if normalized_key in sensitive_keys:
                    raise DataHubIntegrationError(
                        f"receipt payload contains forbidden sensitive key: {key}"
                    )
                walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child)
        elif token and isinstance(value, str) and token in value:
            raise DataHubIntegrationError("receipt payload contains DATAHUB_TOKEN")

    walk(payload)


def _persist_receipt(
    settings: Settings, filename: str, receipt: Mapping[str, Any]
) -> dict[str, Any]:
    payload = dict(receipt)
    _assert_no_secret_material(payload, settings.datahub_token)
    path = _receipt_path(settings, filename)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {**payload, "receipt_path": str(path)}


def _asset_custom_properties(asset: AssetContext) -> dict[str, str]:
    return {
        "lifeboat.adapter": asset.adapter or "none",
        "lifeboat.adapter_parameters": json.dumps(
            asset.adapter_parameters, sort_keys=True, separators=(",", ":")
        ),
        "lifeboat.artifact_type": asset.artifact_type.value,
        "lifeboat.availability": asset.availability.value,
        "lifeboat.platform": asset.platform,
        "lifeboat.requires_approval": str(asset.requires_approval).lower(),
        "lifeboat.risk": asset.risk.value,
        "lifeboat.validations": json.dumps(
            [item.model_dump(mode="json") for item in asset.validations],
            sort_keys=True,
            separators=(",", ":"),
        ),
    }


@dataclass(slots=True)
class DataHubSdkMutationPort:
    settings: Settings
    emitter: DatahubRestEmitter | None = None

    def __post_init__(self) -> None:
        self.settings.assert_coordinator_allocation()
        if not self.settings.datahub_token:
            raise MissingDataHubTokenError(
                "DATAHUB_TOKEN is required for DataHub seed, writeback, and reset"
            )
        if self.emitter is None:
            self.emitter = DatahubRestEmitter(
                gms_server=self.settings.datahub_gms_url,
                token=self.settings.datahub_token,
                connect_timeout_sec=5,
                read_timeout_sec=20,
                retry_max_times=2,
            )

    def _emit(self, urn: str, aspect: Any) -> None:
        assert self.emitter is not None
        self.emitter.emit_mcp(
            MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect)
        )

    def seed(self, snapshot: GraphSnapshot) -> Mapping[str, Any]:
        policy = _scope_policy(self.settings)
        policy.assert_snapshot(snapshot)
        self._emit(
            PROJECT_DOMAIN_URN,
            DomainPropertiesClass(
                name=self.settings.datahub_domain,
                description="Isolated DataHub domain for the Lineage Lifeboat demo.",
            ),
        )
        self._emit(
            PROJECT_TAG_URN,
            TagPropertiesClass(
                name=self.settings.datahub_project_tag,
                description="Required isolation tag for Lineage Lifeboat fixtures.",
            ),
        )
        self._emit(
            WRITEBACK_TAG_URN,
            TagPropertiesClass(
                name=WRITEBACK_TAG,
                description="Receipt marker written after a verified recovery action.",
            ),
        )

        upstreams_by_downstream: dict[str, list[str]] = defaultdict(list)
        for edge in snapshot.edges:
            policy.assert_urn(edge.upstream_urn)
            policy.assert_urn(edge.downstream_urn)
            upstreams_by_downstream[edge.downstream_urn].append(edge.upstream_urn)

        aspect_count = 3
        for asset in sorted(snapshot.assets, key=lambda item: item.urn):
            policy.assert_asset(asset)
            self._emit(asset.urn, StatusClass(removed=False))
            self._emit(
                asset.urn,
                DatasetPropertiesClass(
                    name=asset.display_name,
                    description=(
                        f"Lineage Lifeboat {asset.artifact_type.value} recovery fixture."
                    ),
                    customProperties=_asset_custom_properties(asset),
                ),
            )
            self._emit(
                asset.urn,
                GlobalTagsClass(tags=[TagAssociationClass(tag=PROJECT_TAG_URN)]),
            )
            self._emit(asset.urn, DomainsClass(domains=[PROJECT_DOMAIN_URN]))
            aspect_count += 4
            if asset.owner:
                self._emit(
                    asset.urn,
                    OwnershipClass(
                        owners=[OwnerClass(owner=asset.owner, type="TECHNICAL_OWNER")]
                    ),
                )
                aspect_count += 1
            upstreams = sorted(upstreams_by_downstream.get(asset.urn, []))
            if upstreams:
                self._emit(
                    asset.urn,
                    UpstreamLineageClass(
                        upstreams=[
                            UpstreamClass(dataset=urn, type="TRANSFORMED")
                            for urn in upstreams
                        ]
                    ),
                )
                aspect_count += 1
        return {
            "asset_urns": sorted(asset.urn for asset in snapshot.assets),
            "control_urns": list(CONTROL_URNS),
            "emitted_aspect_count": aspect_count,
            "lineage_edge_count": len(snapshot.edges),
        }

    def writeback(self, target_urn: str, run_id: str) -> Mapping[str, Any]:
        policy = _scope_policy(self.settings)
        policy.assert_urn(target_urn)
        if not run_id.strip():
            raise DataHubIntegrationError("run_id must not be blank")
        self._emit(
            target_urn,
            GlobalTagsClass(
                tags=[
                    TagAssociationClass(tag=PROJECT_TAG_URN),
                    TagAssociationClass(tag=WRITEBACK_TAG_URN, context=run_id),
                ]
            ),
        )
        return {
            "mutation": "globalTags UPSERT",
            "target_urn": target_urn,
            "marker_tag_urn": WRITEBACK_TAG_URN,
            "run_id": run_id,
        }

    def reset(self, snapshot: GraphSnapshot) -> Mapping[str, Any]:
        policy = _scope_policy(self.settings)
        policy.assert_snapshot(snapshot)
        asset_urns = sorted(asset.urn for asset in snapshot.assets)
        for urn in asset_urns:
            policy.assert_urn(urn)
            self._emit(urn, StatusClass(removed=True))
        control_urns = tuple(CONTROL_URNS)
        if set(control_urns) != {
            PROJECT_DOMAIN_URN,
            PROJECT_TAG_URN,
            WRITEBACK_TAG_URN,
        }:
            raise NamespaceViolationError("DataHub reset control allowlist was altered")
        for urn in control_urns:
            self._emit(urn, StatusClass(removed=True))
        return {
            "delete_mode": "soft_status_removed",
            "asset_urns": asset_urns,
            "control_urns": list(CONTROL_URNS),
            "deleted_count": len(asset_urns) + len(CONTROL_URNS),
        }


def _tool_map(tools_result: Any) -> dict[str, Any]:
    return {tool.name: tool for tool in tools_result.tools}


def _tool_schema(tool: Any) -> dict[str, Any]:
    value = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
    return value if isinstance(value, dict) else {}


def _argument_name(
    properties: Mapping[str, Any], candidates: Sequence[str]
) -> str | None:
    return next((name for name in candidates if name in properties), None)


def _entity_arguments(schema: Mapping[str, Any], urns: Sequence[str]) -> list[dict[str, Any]]:
    properties = schema.get("properties", {})
    plural = _argument_name(properties, ("urns", "entity_urns", "entityUrns"))
    if plural:
        return [{plural: list(urns)}]
    singular = _argument_name(properties, ("urn", "entity_urn", "entityUrn"))
    if singular:
        return [{singular: urn} for urn in urns]
    raise McpContractError("get_entities schema has no supported URN argument")


def _lineage_arguments(schema: Mapping[str, Any], root: str) -> dict[str, Any]:
    properties = schema.get("properties", {})
    urn_name = _argument_name(
        properties, ("urn", "source_urn", "sourceUrn", "entity_urn", "entityUrn")
    )
    if urn_name is None:
        raise McpContractError("get_lineage schema has no supported root URN argument")
    arguments: dict[str, Any] = {urn_name: root}
    upstream = _argument_name(properties, ("upstream",))
    if upstream:
        arguments[upstream] = False
    else:
        direction = _argument_name(properties, ("direction",))
        if direction:
            arguments[direction] = "downstream"
    depth = _argument_name(properties, ("max_hops", "maxHops", "max_depth", "depth"))
    if depth:
        arguments[depth] = 1
    result_limit = _argument_name(
        properties,
        ("max_results", "maxResults", "limit", "count", "page_size", "pageSize"),
    )
    if result_limit:
        advertised_maximum = properties[result_limit].get("maximum")
        bounded_limit = MCP_LINEAGE_RESULT_LIMIT
        if (
            isinstance(advertised_maximum, (int, float))
            and not isinstance(advertised_maximum, bool)
            and advertised_maximum >= 1
        ):
            bounded_limit = min(bounded_limit, int(advertised_maximum))
        arguments[result_limit] = bounded_limit
    return arguments


def _result_payload(result: Any) -> dict[str, Any]:
    payload = result.model_dump(mode="json", exclude_none=True)
    if payload.get("isError") or payload.get("is_error"):
        raise McpContractError("DataHub MCP tool returned an error result")
    return payload


@dataclass(slots=True)
class DataHubMcpContextPort:
    settings: Settings

    async def _session_call(
        self,
        urns: Sequence[str],
        lineage_roots: Sequence[str] | None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as http_client:
            async with streamable_http_client(
                self.settings.datahub_mcp_url, http_client=http_client
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    tools = _tool_map(tools_result)
                    required = {"get_entities"}
                    if lineage_roots is not None:
                        required.add("get_lineage")
                    missing = sorted(required - tools.keys())
                    if missing:
                        raise McpContractError(
                            f"DataHub MCP is missing required tools: {missing}"
                        )
                    entity_results = []
                    entity_arguments = _entity_arguments(
                        _tool_schema(tools["get_entities"]), urns
                    )
                    for arguments in entity_arguments:
                        result = await session.call_tool("get_entities", arguments)
                        entity_results.append(
                            {
                                "arguments": arguments,
                                "result": _result_payload(result),
                            }
                        )
                    payload: dict[str, Any] = {
                        "advertised_tools": sorted(tools),
                        "get_entities": entity_results,
                    }
                    if lineage_roots is not None:
                        lineage_results = []
                        for lineage_root in lineage_roots:
                            arguments = _lineage_arguments(
                                _tool_schema(tools["get_lineage"]), lineage_root
                            )
                            result = await session.call_tool("get_lineage", arguments)
                            lineage_results.append(
                                {
                                    "arguments": arguments,
                                    "result": _result_payload(result),
                                }
                            )
                        payload["get_lineage"] = lineage_results
                    return payload

    async def read_context(
        self, urns: Sequence[str], lineage_roots: Sequence[str]
    ) -> Mapping[str, Any]:
        return await self._session_call(urns, lineage_roots)

    async def read_entities(self, urns: Sequence[str]) -> Mapping[str, Any]:
        return await self._session_call(urns, None)


def _serialized(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _assert_entity_evidence(payload: Mapping[str, Any], urns: Sequence[str]) -> None:
    text = _serialized(payload.get("get_entities", {}))
    missing = sorted(urn for urn in urns if urn not in text)
    if missing:
        raise McpContractError(
            f"get_entities response did not contain requested fixture URNs: {missing}"
        )


def _assert_lineage_evidence(
    payload: Mapping[str, Any], snapshot: GraphSnapshot
) -> None:
    text = _serialized(payload.get("get_lineage", {}))
    calls = payload.get("get_lineage", [])
    if not isinstance(calls, list):
        raise McpContractError("get_lineage evidence is not a call list")
    missing_edges = []
    for edge in snapshot.edges:
        matched = any(
            edge.upstream_urn in _serialized(call.get("arguments", {}))
            and edge.downstream_urn in _serialized(call.get("result", {}))
            for call in calls
            if isinstance(call, Mapping)
        )
        if not matched:
            missing_edges.append((edge.upstream_urn, edge.downstream_urn))
    if missing_edges:
        raise McpContractError(
            f"get_lineage responses did not prove fixture edges: {missing_edges}"
        )


def seed_datahub(
    settings: Settings, mutation_port: MutationPort | None = None
) -> dict[str, Any]:
    snapshot, _ = _load_fixture(settings)
    port = mutation_port or DataHubSdkMutationPort(settings)
    evidence = dict(port.seed(snapshot))
    receipt = {
        "schema_version": 1,
        "operation": "datahub_seed",
        "recorded_at": _now(),
        "project_slug": settings.project_slug,
        "datahub_gms_url": settings.datahub_gms_url,
        "fixture_fingerprint": snapshot.fingerprint,
        "namespace": settings.datahub_urn_prefix,
        "supported_api": "DataHub RestEmitter MetadataChangeProposal",
        "datahub_seeded": True,
        "evidence": evidence,
    }
    return _persist_receipt(settings, DATAHUB_SEED_RECEIPT, receipt)


async def read_datahub_context(
    settings: Settings, context_port: ContextPort | None = None
) -> dict[str, Any]:
    snapshot, _ = _load_fixture(settings)
    urns = sorted(asset.urn for asset in snapshot.assets)
    lineage_roots = sorted({edge.upstream_urn for edge in snapshot.edges})
    port = context_port or DataHubMcpContextPort(settings)
    evidence = dict(await port.read_context(urns, lineage_roots))
    _assert_entity_evidence(evidence, urns)
    _assert_lineage_evidence(evidence, snapshot)
    receipt = {
        "schema_version": 1,
        "operation": "datahub_mcp_context_read",
        "recorded_at": _now(),
        "project_slug": settings.project_slug,
        "datahub_mcp_url": settings.datahub_mcp_url,
        "fixture_fingerprint": snapshot.fingerprint,
        "eligible_integration": "DataHub MCP Server",
        "verified_asset_count": len(urns),
        "verified_edge_count": len(snapshot.edges),
        "evidence_sha256": _canonical_sha256(evidence),
        "evidence": evidence,
    }
    return _persist_receipt(settings, CONTEXT_RECEIPT, receipt)


async def writeback_and_verify(
    settings: Settings,
    run_id: str,
    target_urn: str = DEFAULT_WRITEBACK_TARGET,
    mutation_port: MutationPort | None = None,
    context_port: ContextPort | None = None,
) -> dict[str, Any]:
    snapshot, _ = _load_fixture(settings)
    policy = _scope_policy(settings)
    policy.assert_urn(target_urn)
    fixture_urns = {asset.urn for asset in snapshot.assets}
    if target_urn not in fixture_urns:
        raise NamespaceViolationError(
            "writeback target is namespaced but absent from the canonical fixture"
        )
    writer = mutation_port or DataHubSdkMutationPort(settings)
    reader = context_port or DataHubMcpContextPort(settings)
    mutation = dict(writer.writeback(target_urn, run_id))
    reread = dict(await reader.read_entities([target_urn]))
    _assert_entity_evidence(reread, [target_urn])
    if WRITEBACK_TAG_URN not in _serialized(reread):
        raise WritebackVerificationError(
            "immediate MCP reread did not contain the writeback marker tag"
        )
    receipt = {
        "schema_version": 1,
        "operation": "namespace_guarded_writeback_and_reread",
        "recorded_at": _now(),
        "project_slug": settings.project_slug,
        "target_urn": target_urn,
        "run_id": run_id,
        "mutation": mutation,
        "verification": {
            "integration": "DataHub MCP Server get_entities",
            "marker_tag_urn": WRITEBACK_TAG_URN,
            "verified": True,
            "evidence_sha256": _canonical_sha256(reread),
            "evidence": reread,
        },
    }
    return _persist_receipt(settings, WRITEBACK_RECEIPT, receipt)


async def run_vertical_slice(
    settings: Settings,
    run_id: str,
    mutation_port: MutationPort | None = None,
    context_port: ContextPort | None = None,
) -> dict[str, Any]:
    writer = mutation_port or DataHubSdkMutationPort(settings)
    reader = context_port or DataHubMcpContextPort(settings)
    seed_receipt = seed_datahub(settings, writer)
    context_receipt = await read_datahub_context(settings, reader)
    writeback_receipt = await writeback_and_verify(
        settings,
        run_id=run_id,
        mutation_port=writer,
        context_port=reader,
    )
    receipt = {
        "schema_version": 1,
        "operation": "judge_ready_datahub_vertical_slice",
        "recorded_at": _now(),
        "project_slug": settings.project_slug,
        "run_id": run_id,
        "verified": True,
        "seed_receipt_path": seed_receipt["receipt_path"],
        "context_receipt_path": context_receipt["receipt_path"],
        "writeback_receipt_path": writeback_receipt["receipt_path"],
        "fixture_fingerprint": context_receipt["fixture_fingerprint"],
    }
    return _persist_receipt(settings, VERTICAL_SLICE_RECEIPT, receipt)


def reset_datahub(
    settings: Settings,
    confirm_project: str,
    mutation_port: MutationPort | None = None,
) -> dict[str, Any]:
    if confirm_project != settings.project_slug:
        raise ResetConfirmationError(
            f"reset requires --confirm-project {settings.project_slug}"
        )
    snapshot, _ = _load_fixture(settings)
    writer = mutation_port or DataHubSdkMutationPort(settings)
    evidence = dict(writer.reset(snapshot))
    receipt = {
        "schema_version": 1,
        "operation": "datahub_fixture_reset",
        "recorded_at": _now(),
        "project_slug": settings.project_slug,
        "namespace": settings.datahub_urn_prefix,
        "evidence": evidence,
    }
    return _persist_receipt(settings, RESET_RECEIPT, receipt)
