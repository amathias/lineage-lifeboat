from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lineage_lifeboat.config import Settings
from lineage_lifeboat.datahub_vertical_slice import (
    ContextPort,
    DataHubIntegrationError,
    MutationPort,
    sanitized_receipt_bytes,
    writeback_and_verify,
)
from lineage_lifeboat.demo_state import _assert_safe_state_dir, _load_fixture
from lineage_lifeboat.domain.models import (
    ApprovalRecord,
    ContextEvidence,
    DataHubOutcome,
    RecoveryRequest,
    RecoveryRun,
    RecoveryRunStatus,
    StepExecution,
    StepExecutionStatus,
)
from lineage_lifeboat.estate import (
    ORDERS_URN,
    Adapter,
    DemoEstate,
    default_adapter_registry,
)
from lineage_lifeboat.planner import RecoveryCompiler
from lineage_lifeboat.safety import DataHubScopePolicy

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


class RecoveryWorkflowError(RuntimeError):
    """Base error for persisted recovery workflow failures."""


class RecoveryRunNotFoundError(RecoveryWorkflowError):
    pass


class ApprovalRequiredError(RecoveryWorkflowError):
    pass


class ApprovalMismatchError(RecoveryWorkflowError):
    pass


class StalePlanError(RecoveryWorkflowError):
    pass


class InvalidRunIdError(RecoveryWorkflowError):
    pass


class StepValidationFailure(RecoveryWorkflowError):
    pass


class ImmutableEvidenceError(RecoveryWorkflowError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _canonical_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


class RecoveryWorkflow:
    """Persist and execute approval-gated recovery plans against the demo estate."""

    def __init__(
        self,
        settings: Settings,
        *,
        adapter_registry: Mapping[str, Adapter] | None = None,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self.settings = settings
        self.settings.assert_coordinator_allocation()
        self.state_root = _assert_safe_state_dir(settings.app_state_dir)
        self.run_root = self.state_root / "recovery-runs"
        self.estate = DemoEstate(settings)
        self.adapter_registry = dict(
            adapter_registry or default_adapter_registry(self.estate)
        )
        self.clock = clock

    def initialize_estate(self, confirm_project: str) -> dict[str, Any]:
        return self.estate.initialize(confirm_project)

    def trigger_outage(self, confirm_project: str) -> dict[str, Any]:
        return self.estate.trigger_outage(confirm_project)

    def compile_run(
        self,
        run_id: str,
        *,
        requester: str = "incident-commander",
    ) -> RecoveryRun:
        self._assert_run_id(run_id)
        if not self.estate.inspect()["initialized"]:
            raise RecoveryWorkflowError("initialize the disposable demo estate first")
        if self.estate.asset_exists(ORDERS_URN):
            raise RecoveryWorkflowError("trigger the disposable outage before planning")
        snapshot, _ = _load_fixture(self.settings)
        request = RecoveryRequest(
            request_id=f"request-{run_id}",
            incident_type="commerce_analytics_outage",
            unavailable_asset_urns=(ORDERS_URN,),
            max_blast_radius_depth=10,
            risk_mode="demo",
            requester=requester,
        )
        compiler = RecoveryCompiler(
            supported_adapters=self.adapter_registry,
            scope_policy=DataHubScopePolicy(
                domain=self.settings.datahub_domain,
                required_tag=self.settings.datahub_project_tag,
                urn_prefix=self.settings.datahub_urn_prefix,
            ),
        )
        plan = compiler.compile(request, snapshot)
        timestamp = self.clock()
        run = RecoveryRun(
            run_id=run_id,
            created_at=timestamp,
            updated_at=timestamp,
            status=RecoveryRunStatus.PLANNED,
            request=request,
            plan=plan,
            context_evidence=self._context_evidence(snapshot.fingerprint),
            steps=tuple(
                StepExecution(step_id=step.step_id, target_urn=step.target_urn)
                for step in plan.steps
            ),
            datahub_outcome=DataHubOutcome(
                status="pending" if self.settings.datahub_token else "not_configured",
                detail=(
                    "supported writeback will run after local verification"
                    if self.settings.datahub_token
                    else "DATAHUB_TOKEN is absent; local recovery remains runnable"
                ),
            ),
        )
        self._persist(run)
        return self._export_reports(run)

    def approve(self, run_id: str, *, plan_id: str, approved_by: str) -> RecoveryRun:
        run = self.get_run(run_id)
        if plan_id != run.plan.plan_id:
            raise ApprovalMismatchError("approval plan_id does not match the persisted plan")
        if not approved_by.strip():
            raise ApprovalMismatchError("approved_by must not be blank")
        approval = ApprovalRecord(
            plan_id=plan_id,
            approved_by=approved_by.strip(),
            approved_at=self.clock(),
        )
        updated = run.model_copy(
            update={
                "approval": approval,
                "status": RecoveryRunStatus.APPROVED,
                "updated_at": self.clock(),
            }
        )
        self._persist(updated)
        return self._export_reports(updated)

    def execute(self, run_id: str) -> RecoveryRun:
        run = self.get_run(run_id)
        if run.approval is None or run.approval.plan_id != run.plan.plan_id:
            raise ApprovalRequiredError(
                "exact plan approval is required before recovery execution"
            )
        snapshot, _ = _load_fixture(self.settings)
        if snapshot.fingerprint != run.plan.graph_fingerprint:
            raise StalePlanError("current graph fingerprint differs from the approved plan")
        if run.status == RecoveryRunStatus.COMPLETED:
            return run

        run = run.model_copy(
            update={"status": RecoveryRunStatus.RUNNING, "updated_at": self.clock()}
        )
        self._persist(run)
        executions = {execution.step_id: execution for execution in run.steps}

        for step in run.plan.steps:
            current = executions[step.step_id]
            if current.status == StepExecutionStatus.VERIFIED:
                continue
            self._assert_dependencies(step.dependency_step_ids, executions)
            missing_preconditions = [
                urn
                for urn in step.healthy_precondition_urns
                if not self.estate.asset_exists(urn)
            ]
            if missing_preconditions:
                return self._fail_step(
                    run,
                    executions,
                    step.step_id,
                    current,
                    RecoveryWorkflowError(
                        f"healthy preconditions are missing: {missing_preconditions}"
                    ),
                )

            running = current.model_copy(
                update={
                    "status": StepExecutionStatus.RUNNING,
                    "attempts": current.attempts + 1,
                    "started_at": self.clock(),
                    "finished_at": None,
                    "error_type": None,
                    "error_detail": None,
                }
            )
            executions[step.step_id] = running
            run = self._replace_executions(run, executions, RecoveryRunStatus.RUNNING)
            self._persist(run)

            try:
                adapter = self.adapter_registry[step.adapter]
                idempotency_key = f"{run.plan.plan_id}:{step.step_id}"
                adapter_evidence = adapter.execute(step, idempotency_key)
                validations = self._validation_engine().validate(
                    step, adapter_evidence
                )
                failed_required = [
                    result.kind
                    for result in validations
                    if result.required and not result.passed
                ]
                if failed_required:
                    raise StepValidationFailure(
                        f"required validations failed: {failed_required}"
                    )
                verified = running.model_copy(
                    update={
                        "status": StepExecutionStatus.VERIFIED,
                        "finished_at": self.clock(),
                        "adapter_evidence": adapter_evidence,
                        "validations": validations,
                    }
                )
                executions[step.step_id] = verified
                run = self._replace_executions(
                    run, executions, RecoveryRunStatus.RUNNING
                )
                self._persist(run)
            except Exception as error:
                return self._fail_step(
                    run, executions, step.step_id, running, error
                )

        completed = self._replace_executions(
            run, executions, RecoveryRunStatus.COMPLETED
        )
        self._persist(completed)
        return self._export_reports(completed)

    def resume(self, run_id: str) -> RecoveryRun:
        return self.execute(run_id)

    def get_run(self, run_id: str) -> RecoveryRun:
        path = self._run_path(run_id)
        try:
            return RecoveryRun.model_validate_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise RecoveryRunNotFoundError(f"recovery run does not exist: {run_id}") from error

    def record_datahub_outcome(
        self,
        run_id: str,
        outcome: DataHubOutcome,
    ) -> RecoveryRun:
        run = self.get_run(run_id)
        updated = run.model_copy(
            update={"datahub_outcome": outcome, "updated_at": self.clock()}
        )
        self._persist(updated)
        return self._export_reports(updated)

    def persist_datahub_receipt(
        self,
        run_id: str,
        receipt: Mapping[str, Any],
    ) -> Path:
        self.get_run(run_id)
        run_root = self.run_root.resolve()
        run_dir = self._run_dir(run_id).resolve()
        if run_dir.parent != run_root:
            raise ImmutableEvidenceError(
                "recovery receipt directory escaped the project run root"
            )
        path = run_dir / "datahub-writeback-receipt.json"
        payload = sanitized_receipt_bytes(self.settings, receipt)
        try:
            if path.exists():
                if not path.is_file() or path.read_bytes() != payload:
                    raise ImmutableEvidenceError(
                        "immutable DataHub receipt already exists with different bytes"
                    )
                return path
            _atomic_write(path, payload)
        except OSError as error:
            raise ImmutableEvidenceError(
                "immutable DataHub receipt could not be retained"
            ) from error
        return path

    def export_examples(self, run_id: str, destination: Path) -> tuple[Path, Path, Path]:
        run = self.get_run(run_id)
        destination.mkdir(parents=True, exist_ok=True)
        plan_path = destination / "recovery-plan.json"
        report_json_path = destination / "recovery-report.json"
        report_markdown_path = destination / "recovery-report.md"
        _atomic_write(
            plan_path,
            _canonical_bytes(run.plan.model_dump(mode="json")),
        )
        portable_report = run.model_dump(mode="json")
        portable_report["report_json_path"] = "examples/recovery-report.json"
        portable_report["report_markdown_path"] = "examples/recovery-report.md"
        _atomic_write(
            report_json_path,
            _canonical_bytes(portable_report),
        )
        _atomic_write(report_markdown_path, self._markdown_report(run).encode("utf-8"))
        return plan_path, report_json_path, report_markdown_path

    def _context_evidence(self, fingerprint: str) -> ContextEvidence:
        receipt_path = (
            self.settings.app_state_dir
            / "datahub-receipts"
            / "vertical-slice-receipt.json"
        ).resolve()
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            return ContextEvidence(
                mode="captured_datahub_fixture",
                graph_fingerprint=fingerprint,
                detail=(
                    "compiled from the canonical captured DataHub graph; "
                    "live receipt is unavailable in this local run"
                ),
            )
        if (
            receipt.get("operation") == "judge_ready_datahub_vertical_slice"
            and receipt.get("verified") is True
            and receipt.get("fixture_fingerprint") == fingerprint
        ):
            return ContextEvidence(
                mode="verified_live_datahub_mcp",
                graph_fingerprint=fingerprint,
                receipt_path=str(receipt_path),
                receipt_sha256=_sha256(receipt_path),
                detail="bound to verified live DataHub MCP entity/lineage evidence",
            )
        return ContextEvidence(
            mode="captured_datahub_fixture",
            graph_fingerprint=fingerprint,
            detail="live receipt is missing, invalidated, or stale for this graph",
        )

    def _validation_engine(self):
        from lineage_lifeboat.estate import ValidationEngine

        return ValidationEngine(self.estate, clock=self.clock)

    @staticmethod
    def _assert_dependencies(
        dependency_ids: tuple[str, ...],
        executions: Mapping[str, StepExecution],
    ) -> None:
        blocked = [
            step_id
            for step_id in dependency_ids
            if executions[step_id].status != StepExecutionStatus.VERIFIED
        ]
        if blocked:
            raise RecoveryWorkflowError(
                f"dependency steps are not verified: {blocked}"
            )

    def _fail_step(
        self,
        run: RecoveryRun,
        executions: dict[str, StepExecution],
        step_id: str,
        current: StepExecution,
        error: Exception,
    ) -> RecoveryRun:
        failed = current.model_copy(
            update={
                "status": StepExecutionStatus.FAILED,
                "finished_at": self.clock(),
                "error_type": type(error).__name__,
                "error_detail": str(error)[:240],
            }
        )
        executions[step_id] = failed
        updated = self._replace_executions(
            run, executions, RecoveryRunStatus.FAILED
        )
        self._persist(updated)
        return self._export_reports(updated)

    def _replace_executions(
        self,
        run: RecoveryRun,
        executions: Mapping[str, StepExecution],
        status: RecoveryRunStatus,
    ) -> RecoveryRun:
        return run.model_copy(
            update={
                "steps": tuple(
                    executions[step.step_id] for step in run.plan.steps
                ),
                "status": status,
                "updated_at": self.clock(),
            }
        )

    def _persist(self, run: RecoveryRun) -> None:
        _atomic_write(
            self._run_path(run.run_id),
            _canonical_bytes(run.model_dump(mode="json")),
        )

    def _export_reports(self, run: RecoveryRun) -> RecoveryRun:
        run_dir = self._run_dir(run.run_id)
        json_path = run_dir / "recovery-report.json"
        markdown_path = run_dir / "recovery-report.md"
        with_paths = run.model_copy(
            update={
                "report_json_path": str(json_path.resolve()),
                "report_markdown_path": str(markdown_path.resolve()),
            }
        )
        _atomic_write(
            json_path,
            _canonical_bytes(with_paths.model_dump(mode="json")),
        )
        _atomic_write(markdown_path, self._markdown_report(with_paths).encode("utf-8"))
        self._persist(with_paths)
        return with_paths

    @staticmethod
    def _markdown_report(run: RecoveryRun) -> str:
        verified = sum(
            execution.status == StepExecutionStatus.VERIFIED
            for execution in run.steps
        )
        lines = [
            "# Lineage Lifeboat Recovery Report",
            "",
            f"- Run: `{run.run_id}`",
            f"- Plan: `{run.plan.plan_id}`",
            f"- Status: `{run.status}`",
            f"- Graph fingerprint: `{run.plan.graph_fingerprint}`",
            f"- Context: `{run.context_evidence.mode}`",
            f"- Verified steps: `{verified}/{len(run.steps)}`",
            f"- DataHub outcome: `{run.datahub_outcome.status}`",
            "",
            "## Dependency waves",
            "",
        ]
        by_id = {step.step_id: step.target_urn for step in run.plan.steps}
        for index, wave in enumerate(run.plan.waves, start=1):
            names = ", ".join(f"`{by_id[step_id]}`" for step_id in wave)
            lines.append(f"{index}. {names}")
        lines.extend(["", "## Execution evidence", ""])
        for execution in run.steps:
            action = (
                execution.adapter_evidence.action
                if execution.adapter_evidence
                else "not produced"
            )
            lines.append(
                f"- `{execution.target_urn}` — **{execution.status}**, "
                f"attempts `{execution.attempts}`, action `{action}`"
            )
            for validation in execution.validations:
                marker = "PASS" if validation.passed else "FAIL"
                lines.append(
                    f"  - {marker} `{validation.kind}`: {validation.detail}"
                )
        lines.extend(
            [
                "",
                "## Safety and writeback",
                "",
                f"- Approval: `{run.approval.approved_by if run.approval else 'missing'}`",
                f"- DataHub: {run.datahub_outcome.detail}",
                "- Cloud actions: none; all execution targets are local and disposable.",
                "",
            ]
        )
        return "\n".join(lines)

    def _run_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "run.json"

    def _run_dir(self, run_id: str) -> Path:
        self._assert_run_id(run_id)
        return self.run_root / run_id

    @staticmethod
    def _assert_run_id(run_id: str) -> None:
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise InvalidRunIdError(
                "run_id must be 1-80 safe alphanumeric, dot, underscore, or dash characters"
            )


async def execute_with_datahub_writeback(
    workflow: RecoveryWorkflow,
    run_id: str,
    *,
    mutation_port: MutationPort | None = None,
    context_port: ContextPort | None = None,
) -> RecoveryRun:
    run = workflow.execute(run_id)
    if run.status != RecoveryRunStatus.COMPLETED:
        return run
    if run.datahub_outcome.status == "verified":
        return run
    if not workflow.settings.datahub_token and mutation_port is None:
        return workflow.record_datahub_outcome(
            run_id,
            DataHubOutcome(
                status="not_configured",
                detail=(
                    "local recovery verified; DATAHUB_TOKEN is absent so no live "
                    "writeback was attempted"
                ),
            ),
        )
    try:
        receipt = await writeback_and_verify(
            workflow.settings,
            run_id=run_id,
            mutation_port=mutation_port,
            context_port=context_port,
            persist_receipt=False,
        )
        receipt_path = workflow.persist_datahub_receipt(run_id, receipt)
    except (DataHubIntegrationError, ImmutableEvidenceError) as error:
        return workflow.record_datahub_outcome(
            run_id,
            DataHubOutcome(
                status="failed",
                detail=f"writeback failed closed: {type(error).__name__}",
            ),
        )
    return workflow.record_datahub_outcome(
        run_id,
        DataHubOutcome(
            status="verified",
            detail="supported globalTags writeback verified by immediate MCP reread",
            receipt_path=str(receipt_path),
            receipt_sha256=_sha256(receipt_path),
        ),
    )