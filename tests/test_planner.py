from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lineage_lifeboat.domain.models import (
    AssetAvailability,
    GraphSnapshot,
    LineageEdge,
    LineageEvidence,
    RecoveryRequest,
    SelectionDecision,
)
from lineage_lifeboat.planner import (
    InvalidLineageError,
    MissingAdapterError,
    RecoveryCompiler,
    RecoveryCycleError,
    UnresolvedPrerequisiteError,
)
from lineage_lifeboat.safety import DataHubScopePolicy

ROOT = Path(__file__).resolve().parents[1]
ORDERS_URN = "urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.raw.orders,PROD)"
CUSTOMERS_URN = "urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.raw.customers,PROD)"
STG_ORDERS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.analytics.stg_orders,PROD)"
)
REVENUE_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.analytics.customer_revenue,PROD)"
)
FEATURE_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:featurestore,lifeboat.features.customer_value,PROD)"
)
MODEL_URN = "urn:li:dataset:(urn:li:dataPlatform:mlflow,lifeboat.models.churn_model,PROD)"
DASHBOARD_URN = "urn:li:dataset:(urn:li:dataPlatform:looker,lifeboat.dashboards.executive_revenue,PROD)"
UNRELATED_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.inventory.forecast,PROD)"
)


def _scope_policy() -> DataHubScopePolicy:
    return DataHubScopePolicy(
        domain="Demo / Lineage Lifeboat",
        required_tag="project-lineage-lifeboat",
        urn_prefix="lifeboat.",
    )


@pytest.fixture
def snapshot() -> GraphSnapshot:
    payload = json.loads((ROOT / "demo" / "fixtures" / "lineage-lifeboat" / "graph_snapshot.json").read_text())
    return GraphSnapshot.model_validate(payload)


@pytest.fixture
def recovery_request() -> RecoveryRequest:
    return RecoveryRequest(
        request_id="incident-commerce-001",
        incident_type="commerce_analytics_outage",
        unavailable_asset_urns=(ORDERS_URN,),
        target_recovery_point=datetime(2026, 7, 24, 11, 55, tzinfo=UTC),
        max_blast_radius_depth=10,
        risk_mode="demo",
        requester="incident-commander",
    )


@pytest.fixture
def compiler() -> RecoveryCompiler:
    return RecoveryCompiler(
        supported_adapters={
            "snapshot_restore",
            "sql_transform",
            "python_build",
            "report_refresh",
        },
        scope_policy=_scope_policy(),
    )


def wave_urns(plan) -> tuple[tuple[str, ...], ...]:
    by_id = {step.step_id: step.target_urn for step in plan.steps}
    return tuple(tuple(by_id[step_id] for step_id in wave) for wave in plan.waves)


def test_compiles_expected_dependency_waves(
    compiler: RecoveryCompiler,
    recovery_request: RecoveryRequest,
    snapshot: GraphSnapshot,
) -> None:
    plan = compiler.compile(recovery_request, snapshot)

    assert wave_urns(plan) == (
        (ORDERS_URN,),
        (STG_ORDERS_URN,),
        (REVENUE_URN,),
        (FEATURE_URN, DASHBOARD_URN),
        (MODEL_URN,),
    )
    assert len(plan.steps) == 6
    assert plan.step_for_urn(REVENUE_URN).healthy_precondition_urns == (
        CUSTOMERS_URN,
    )

    decisions = {selection.urn: selection.decision for selection in plan.selections}
    assert decisions[CUSTOMERS_URN] == SelectionDecision.HEALTHY_PRECONDITION
    assert decisions[UNRELATED_URN] == SelectionDecision.EXCLUDED


def test_plan_and_fingerprint_ignore_input_order(
    compiler: RecoveryCompiler,
    recovery_request: RecoveryRequest,
    snapshot: GraphSnapshot,
) -> None:
    reordered = snapshot.model_copy(
        update={
            "assets": tuple(reversed(snapshot.assets)),
            "edges": tuple(reversed(snapshot.edges)),
            "captured_at": datetime(2026, 7, 24, 13, 0, tzinfo=UTC),
        }
    )

    first = compiler.compile(recovery_request, snapshot)
    second = compiler.compile(recovery_request, reordered)

    assert snapshot.fingerprint == reordered.fingerprint
    assert first == second


def test_lineage_change_changes_plan_and_fingerprint(
    compiler: RecoveryCompiler,
    recovery_request: RecoveryRequest,
    snapshot: GraphSnapshot,
) -> None:
    new_edge = LineageEdge(
        upstream_urn=MODEL_URN,
        downstream_urn=DASHBOARD_URN,
        evidence=LineageEvidence(
            upstream_urn=MODEL_URN,
            downstream_urn=DASHBOARD_URN,
        ),
    )
    changed = snapshot.model_copy(update={"edges": snapshot.edges + (new_edge,)})

    original_plan = compiler.compile(recovery_request, snapshot)
    changed_plan = compiler.compile(recovery_request, changed)

    assert snapshot.fingerprint != changed.fingerprint
    assert original_plan.plan_id != changed_plan.plan_id
    assert wave_urns(changed_plan)[-1] == (DASHBOARD_URN,)


def test_cycle_fails_closed(
    compiler: RecoveryCompiler,
    recovery_request: RecoveryRequest,
    snapshot: GraphSnapshot,
) -> None:
    cycle_edge = LineageEdge(
        upstream_urn=MODEL_URN,
        downstream_urn=STG_ORDERS_URN,
        evidence=LineageEvidence(
            upstream_urn=MODEL_URN,
            downstream_urn=STG_ORDERS_URN,
        ),
    )
    cyclic = snapshot.model_copy(update={"edges": snapshot.edges + (cycle_edge,)})

    with pytest.raises(RecoveryCycleError, match="contains a cycle"):
        compiler.compile(recovery_request, cyclic)


def test_missing_adapter_fails_closed(
    recovery_request: RecoveryRequest,
    snapshot: GraphSnapshot,
) -> None:
    compiler = RecoveryCompiler(
        supported_adapters={"snapshot_restore", "python_build", "report_refresh"},
        scope_policy=_scope_policy(),
    )

    with pytest.raises(MissingAdapterError, match="sql_transform"):
        compiler.compile(recovery_request, snapshot)


def test_unknown_healthy_prerequisite_state_fails_closed(
    compiler: RecoveryCompiler,
    recovery_request: RecoveryRequest,
    snapshot: GraphSnapshot,
) -> None:
    changed_assets = tuple(
        asset.model_copy(update={"availability": AssetAvailability.UNKNOWN})
        if asset.urn == CUSTOMERS_URN
        else asset
        for asset in snapshot.assets
    )
    unknown_prerequisite = snapshot.model_copy(update={"assets": changed_assets})

    with pytest.raises(UnresolvedPrerequisiteError, match=re.escape(CUSTOMERS_URN)):
        compiler.compile(recovery_request, unknown_prerequisite)


def test_lineage_edge_with_missing_entity_is_rejected(
    compiler: RecoveryCompiler,
    recovery_request: RecoveryRequest,
    snapshot: GraphSnapshot,
) -> None:
    missing_urn = "urn:li:dataset:(urn:li:dataPlatform:duckdb,missing.asset,PROD)"
    invalid_edge = LineageEdge(
        upstream_urn=missing_urn,
        downstream_urn=ORDERS_URN,
        evidence=LineageEvidence(
            upstream_urn=missing_urn,
            downstream_urn=ORDERS_URN,
        ),
    )
    invalid = snapshot.model_copy(update={"edges": snapshot.edges + (invalid_edge,)})

    with pytest.raises(InvalidLineageError, match="absent from the snapshot"):
        compiler.compile(recovery_request, invalid)

