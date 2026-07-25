from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

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
    MissingDataHubTokenError,
    ResetConfirmationError,
    WritebackVerificationError,
    reset_datahub,
    run_vertical_slice,
    seed_datahub,
    writeback_and_verify,
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
            "delete_mode": "soft_status_removed",
            "asset_urns": list(self.resets),
            "control_urns": list(CONTROL_URNS),
            "deleted_count": len(self.resets) + len(CONTROL_URNS),
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
            }
        },
        "urn:root",
    ) == {"urn": "urn:root", "upstream": False, "max_hops": 1}

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
    assert receipt["evidence"]["control_urns"] == list(CONTROL_URNS)
    assert FOREIGN_URN not in receipt["evidence"]["asset_urns"]
    assert (settings.app_state_dir / "datahub-receipts" / RESET_RECEIPT).is_file()
