from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from lineage_lifeboat.config import Settings
from lineage_lifeboat.datahub_vertical_slice import (
    CONTROL_URNS,
    DEFAULT_WRITEBACK_TARGET,
    WRITEBACK_TAG_URN,
    DataHubIntegrationError,
    writeback_and_verify,
)
from lineage_lifeboat.domain.models import (
    GraphSnapshot,
    RecoveryRunStatus,
    StepExecutionStatus,
)
from lineage_lifeboat.estate import (
    FEATURE_URN,
    INVENTORY_URN,
    Adapter,
    DemoEstateError,
    RecoveryAdapterError,
)
from lineage_lifeboat.workflow import (
    ApprovalMismatchError,
    ApprovalRequiredError,
    ImmutableEvidenceError,
    InvalidRunIdError,
    RecoveryWorkflow,
    execute_with_datahub_writeback,
)

ROOT = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path, *, token: str | None = None) -> Settings:
    return replace(
        Settings.from_env({}),
        app_state_dir=tmp_path / "lineage-lifeboat",
        datahub_token=token,
    )


def _prepare(workflow: RecoveryWorkflow, run_id: str = "test-run-001"):
    workflow.initialize_estate("lineage-lifeboat")
    workflow.trigger_outage("lineage-lifeboat")
    return workflow.compile_run(run_id, requester="test-commander")


class FailOnceAdapter:
    def __init__(self, inner: Adapter) -> None:
        self.inner = inner
        self.failed = False

    def execute(self, step, idempotency_key):
        if step.adapter_parameters.get("job") == "customer_value" and not self.failed:
            self.failed = True
            raise RecoveryAdapterError("injected one-time feature build failure")
        return self.inner.execute(step, idempotency_key)


class DeleteFeatureAfterBuildAdapter:
    def __init__(self, workflow: RecoveryWorkflow, inner: Adapter) -> None:
        self.workflow = workflow
        self.inner = inner

    def execute(self, step, idempotency_key):
        evidence = self.inner.execute(step, idempotency_key)
        if step.target_urn == FEATURE_URN:
            self.workflow.estate.artifact_path(FEATURE_URN).unlink()
        return evidence


class FakeMutationPort:
    def __init__(self) -> None:
        self.writebacks: list[tuple[str, str]] = []

    def seed(self, snapshot: GraphSnapshot) -> dict[str, Any]:
        raise AssertionError("seed is not part of recovery outcome writeback")

    def writeback(self, target_urn: str, run_id: str) -> dict[str, Any]:
        self.writebacks.append((target_urn, run_id))
        return {
            "mutation": "globalTags UPSERT",
            "target_urn": target_urn,
            "marker_tag_urn": WRITEBACK_TAG_URN,
            "run_id": run_id,
        }

    def reset(self, snapshot: GraphSnapshot) -> dict[str, Any]:
        raise AssertionError("reset is not part of recovery outcome writeback")


class FakeContextPort:
    async def read_context(self, urns, lineage_roots):
        raise AssertionError("context graph was already bound to the approved plan")

    async def read_entities(self, urns):
        return {
            "advertised_tools": ["get_entities"],
            "get_entities": [
                {
                    "result": {
                        "content": [*urns, WRITEBACK_TAG_URN, *CONTROL_URNS]
                    }
                }
            ],
        }


def test_complete_recovery_requires_approval_and_preserves_unrelated_asset(
    tmp_path: Path,
) -> None:
    workflow = RecoveryWorkflow(_settings(tmp_path))
    sentinel = workflow.state_root / "preserve-coordinator-evidence.json"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text(json.dumps({"keep": True}), encoding="utf-8")
    planned = _prepare(workflow)

    with pytest.raises(ApprovalRequiredError, match="approval"):
        workflow.execute(planned.run_id)
    with pytest.raises(ApprovalMismatchError, match="plan_id"):
        workflow.approve(
            planned.run_id,
            plan_id="another-plan",
            approved_by="test-commander",
        )

    workflow.approve(
        planned.run_id,
        plan_id=planned.plan.plan_id,
        approved_by="test-commander",
    )
    completed = workflow.execute(planned.run_id)

    assert completed.status == RecoveryRunStatus.COMPLETED
    assert len(completed.steps) == 6
    assert all(
        step.status == StepExecutionStatus.VERIFIED for step in completed.steps
    )
    assert all(
        validation.passed
        for step in completed.steps
        for validation in step.validations
        if validation.required
    )
    assert workflow.estate.asset_exists(INVENTORY_URN)
    assert sentinel.is_file()
    assert Path(completed.report_json_path).is_file()
    assert Path(completed.report_markdown_path).is_file()

    resumed = workflow.resume(planned.run_id)
    assert [step.attempts for step in resumed.steps] == [1, 1, 1, 1, 1, 1]


def test_failure_resumes_without_rerunning_verified_steps(tmp_path: Path) -> None:
    workflow = RecoveryWorkflow(_settings(tmp_path))
    workflow.adapter_registry["python_build"] = FailOnceAdapter(
        workflow.adapter_registry["python_build"]
    )
    planned = _prepare(workflow, "resume-run-001")
    workflow.approve(
        planned.run_id,
        plan_id=planned.plan.plan_id,
        approved_by="test-commander",
    )

    failed = workflow.execute(planned.run_id)

    assert failed.status == RecoveryRunStatus.FAILED
    assert [step.status for step in failed.steps[:3]] == [
        StepExecutionStatus.VERIFIED,
        StepExecutionStatus.VERIFIED,
        StepExecutionStatus.VERIFIED,
    ]
    assert failed.steps[3].status == StepExecutionStatus.FAILED
    assert failed.steps[5].status == StepExecutionStatus.PENDING

    completed = workflow.resume(planned.run_id)

    assert completed.status == RecoveryRunStatus.COMPLETED
    assert [step.attempts for step in completed.steps[:3]] == [1, 1, 1]
    assert completed.steps[3].attempts == 2
    assert all(
        step.status == StepExecutionStatus.VERIFIED for step in completed.steps
    )


def test_required_validation_failure_blocks_consumers(tmp_path: Path) -> None:
    workflow = RecoveryWorkflow(_settings(tmp_path))
    workflow.adapter_registry["python_build"] = DeleteFeatureAfterBuildAdapter(
        workflow,
        workflow.adapter_registry["python_build"],
    )
    planned = _prepare(workflow, "validation-run-001")
    workflow.approve(
        planned.run_id,
        plan_id=planned.plan.plan_id,
        approved_by="test-commander",
    )

    failed = workflow.execute(planned.run_id)

    assert failed.status == RecoveryRunStatus.FAILED
    feature = failed.steps[3]
    model = failed.steps[5]
    assert feature.status == StepExecutionStatus.FAILED
    assert feature.error_type == "StepValidationFailure"
    assert model.status == StepExecutionStatus.PENDING
    assert model.attempts == 0


def test_verified_datahub_writeback_is_attached_to_final_report(tmp_path: Path) -> None:
    workflow = RecoveryWorkflow(_settings(tmp_path, token="test-only-token"))
    planned = _prepare(workflow, "writeback-run-001")
    workflow.approve(
        planned.run_id,
        plan_id=planned.plan.plan_id,
        approved_by="test-commander",
    )
    mutation = FakeMutationPort()

    completed = asyncio.run(
        execute_with_datahub_writeback(
            workflow,
            planned.run_id,
            mutation_port=mutation,
            context_port=FakeContextPort(),
        )
    )

    assert completed.status == RecoveryRunStatus.COMPLETED
    assert completed.datahub_outcome.status == "verified"
    receipt_path = Path(completed.datahub_outcome.receipt_path)
    assert receipt_path.is_file()
    assert receipt_path.parent.name == planned.run_id
    assert receipt_path.name == "datahub-writeback-receipt.json"
    assert len(completed.datahub_outcome.receipt_sha256) == 64
    assert mutation.writebacks[0][1] == planned.run_id
    assert not (
        workflow.state_root / "datahub-receipts" / "writeback-receipt.json"
    ).exists()


def test_live_context_receipt_binds_plan_and_unsafe_inputs_fail_closed(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    snapshot = GraphSnapshot.model_validate_json(
        (settings.demo_fixture_root / "graph_snapshot.json").read_text(
            encoding="utf-8"
        )
    )
    receipt_dir = settings.app_state_dir / "datahub-receipts"
    receipt_dir.mkdir(parents=True)
    (receipt_dir / "vertical-slice-receipt.json").write_text(
        json.dumps(
            {
                "operation": "judge_ready_datahub_vertical_slice",
                "verified": True,
                "fixture_fingerprint": snapshot.fingerprint,
            }
        ),
        encoding="utf-8",
    )
    workflow = RecoveryWorkflow(settings)
    planned = _prepare(workflow, "live-context-run-001")

    assert planned.context_evidence.mode == "verified_live_datahub_mcp"
    assert len(planned.context_evidence.receipt_sha256) == 64
    with pytest.raises(InvalidRunIdError):
        workflow.compile_run("../foreign")
    with pytest.raises(DemoEstateError, match="confirm_project"):
        workflow.trigger_outage("another-project")


def test_later_run_cannot_change_prior_run_or_vertical_slice_evidence(
    tmp_path: Path,
) -> None:
    workflow = RecoveryWorkflow(_settings(tmp_path, token="test-only-token"))
    stable_path = (
        workflow.state_root / "datahub-receipts" / "writeback-receipt.json"
    )
    stable_path.parent.mkdir(parents=True)
    stable_bytes = b'{"authoritative":"milestone-b-vertical-slice"}\n'
    stable_path.write_bytes(stable_bytes)
    vertical_path = stable_path.parent / "vertical-slice-receipt.json"
    vertical_bytes = json.dumps(
        {"writeback_receipt_path": str(stable_path)}, sort_keys=True
    ).encode("utf-8")
    vertical_path.write_bytes(vertical_bytes)
    mutation = FakeMutationPort()

    first = _prepare(workflow, "immutable-run-a")
    workflow.approve(
        first.run_id,
        plan_id=first.plan.plan_id,
        approved_by="test-commander",
    )
    completed_a = asyncio.run(
        execute_with_datahub_writeback(
            workflow,
            first.run_id,
            mutation_port=mutation,
            context_port=FakeContextPort(),
        )
    )
    receipt_a = Path(completed_a.datahub_outcome.receipt_path)
    bytes_a = receipt_a.read_bytes()
    hash_a = hashlib.sha256(bytes_a).hexdigest()

    second = _prepare(workflow, "immutable-run-b")
    workflow.approve(
        second.run_id,
        plan_id=second.plan.plan_id,
        approved_by="test-commander",
    )
    completed_b = asyncio.run(
        execute_with_datahub_writeback(
            workflow,
            second.run_id,
            mutation_port=mutation,
            context_port=FakeContextPort(),
        )
    )

    reloaded_a = workflow.get_run(first.run_id)
    assert reloaded_a.datahub_outcome.receipt_path == str(receipt_a)
    assert reloaded_a.datahub_outcome.receipt_sha256 == hash_a
    assert receipt_a.read_bytes() == bytes_a
    assert hashlib.sha256(receipt_a.read_bytes()).hexdigest() == hash_a
    assert Path(completed_b.datahub_outcome.receipt_path) != receipt_a
    assert stable_path.read_bytes() == stable_bytes
    assert vertical_path.read_bytes() == vertical_bytes
    assert mutation.writebacks == [
        (DEFAULT_WRITEBACK_TARGET, first.run_id),
        (DEFAULT_WRITEBACK_TARGET, second.run_id),
    ]


def test_unsafe_run_id_and_immutable_receipt_conflict_fail_closed(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, token="test-only-token")
    mutation = FakeMutationPort()
    with pytest.raises(DataHubIntegrationError, match="run_id"):
        asyncio.run(
            writeback_and_verify(
                settings,
                run_id="../escape",
                mutation_port=mutation,
                context_port=FakeContextPort(),
                persist_receipt=False,
            )
        )
    assert mutation.writebacks == []

    workflow = RecoveryWorkflow(settings)
    planned = _prepare(workflow, "retention-failure")
    workflow.approve(
        planned.run_id,
        plan_id=planned.plan.plan_id,
        approved_by="test-commander",
    )
    immutable_path = (
        workflow.run_root / planned.run_id / "datahub-writeback-receipt.json"
    )
    original = b'{"preexisting":"different"}\n'
    immutable_path.write_bytes(original)
    failed = asyncio.run(
        execute_with_datahub_writeback(
            workflow,
            planned.run_id,
            mutation_port=mutation,
            context_port=FakeContextPort(),
        )
    )

    assert failed.status == RecoveryRunStatus.COMPLETED
    assert failed.datahub_outcome.status == "failed"
    assert "ImmutableEvidenceError" in failed.datahub_outcome.detail
    assert immutable_path.read_bytes() == original
    with pytest.raises(ImmutableEvidenceError):
        workflow.persist_datahub_receipt(planned.run_id, {"different": True})


def test_no_token_run_does_not_create_or_change_datahub_receipts(
    tmp_path: Path,
) -> None:
    workflow = RecoveryWorkflow(_settings(tmp_path))
    stable_path = (
        workflow.state_root / "datahub-receipts" / "writeback-receipt.json"
    )
    stable_path.parent.mkdir(parents=True)
    stable_bytes = b'{"authoritative":"unchanged"}\n'
    stable_path.write_bytes(stable_bytes)
    planned = _prepare(workflow, "no-token-run")
    workflow.approve(
        planned.run_id,
        plan_id=planned.plan.plan_id,
        approved_by="test-commander",
    )

    completed = asyncio.run(
        execute_with_datahub_writeback(workflow, planned.run_id)
    )

    assert completed.datahub_outcome.status == "not_configured"
    assert completed.datahub_outcome.receipt_path is None
    assert stable_path.read_bytes() == stable_bytes
    assert not (
        workflow.run_root
        / planned.run_id
        / "datahub-writeback-receipt.json"
    ).exists()
