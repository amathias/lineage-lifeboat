from __future__ import annotations

import json
from pathlib import Path

import pytest
from lineage_lifeboat.domain.models import GraphSnapshot
from lineage_lifeboat.safety import DataHubScopePolicy, NamespaceViolationError

ROOT = Path(__file__).resolve().parents[1]


def _snapshot() -> GraphSnapshot:
    fixture = ROOT / "demo" / "fixtures" / "lineage-lifeboat" / "graph_snapshot.json"
    return GraphSnapshot.model_validate(json.loads(fixture.read_text(encoding="utf-8")))


def _policy() -> DataHubScopePolicy:
    return DataHubScopePolicy(
        domain="Demo / Lineage Lifeboat",
        required_tag="project-lineage-lifeboat",
        urn_prefix="lifeboat.",
    )


def test_canonical_snapshot_is_inside_project_scope() -> None:
    _policy().assert_snapshot(_snapshot())


def test_foreign_urn_fails_closed() -> None:
    snapshot = _snapshot()
    foreign = snapshot.assets[0].model_copy(
        update={"urn": "urn:li:dataset:(urn:li:dataPlatform:duckdb,other.raw.orders,PROD)"}
    )

    with pytest.raises(NamespaceViolationError, match="outside"):
        _policy().assert_asset(foreign)


def test_missing_project_tag_fails_closed() -> None:
    snapshot = _snapshot()
    untagged = snapshot.assets[0].model_copy(update={"tags": ()})

    with pytest.raises(NamespaceViolationError, match="lacks required tag"):
        _policy().assert_asset(untagged)