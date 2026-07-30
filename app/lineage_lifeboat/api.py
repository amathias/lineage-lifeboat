from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from lineage_lifeboat.config import Settings
from lineage_lifeboat.demo_guard import (
    DemoCapacityError,
    DemoConfirmationError,
    DemoMutationGuard,
)
from lineage_lifeboat.domain.models import GraphSnapshot, RecoveryRun
from lineage_lifeboat.safety import DataHubScopePolicy, NamespaceViolationError
from lineage_lifeboat.workflow import (
    RecoveryWorkflow,
    RecoveryWorkflowError,
    execute_with_datahub_writeback,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiModel):
    status: str
    project: str
    version: str


class CheckResult(ApiModel):
    ready: bool
    detail: str


class ReadinessResponse(ApiModel):
    ready: bool
    checks: dict[str, CheckResult]


DemoOperation = Literal["initialize", "outage", "plan", "approve", "execute", "resume"]


class DemoConfirmationRequest(ApiModel):
    operation: DemoOperation


class DemoConfirmationResponse(ApiModel):
    confirmation: str
    operation: DemoOperation
    expires_in_seconds: int


class RecoveryPlanRequest(ApiModel):
    run_id: str
    requester: str = "incident-commander"


class RecoveryApprovalRequest(ApiModel):
    plan_id: str
    approved_by: str


DataHubProbe = Callable[[Settings], CheckResult]


def probe_datahub_gms(settings: Settings) -> CheckResult:
    request = UrlRequest(f"{settings.datahub_gms_url}/health")
    if settings.datahub_token:
        request.add_header("Authorization", f"Bearer {settings.datahub_token}")
    try:
        with urlopen(request, timeout=2) as response:  # noqa: S310 - configured URL
            code = response.getcode()
            if 200 <= code < 300:
                return CheckResult(ready=True, detail=f"GMS health returned HTTP {code}")
            return CheckResult(ready=False, detail=f"GMS health returned HTTP {code}")
    except HTTPError as exc:
        return CheckResult(ready=False, detail=f"GMS health returned HTTP {exc.code}")
    except (TimeoutError, URLError, OSError) as exc:
        return CheckResult(
            ready=False,
            detail=f"GMS health is unreachable: {type(exc).__name__}",
        )


def _fixture_check(settings: Settings) -> CheckResult:
    fixture_path = settings.demo_fixture_root / "graph_snapshot.json"
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        snapshot = GraphSnapshot.model_validate(payload)
        DataHubScopePolicy(
            domain=settings.datahub_domain,
            required_tag=settings.datahub_project_tag,
            urn_prefix=settings.datahub_urn_prefix,
        ).assert_snapshot(snapshot)
    except FileNotFoundError:
        return CheckResult(ready=False, detail=f"fixture is missing: {fixture_path}")
    except (ValueError, NamespaceViolationError) as exc:
        return CheckResult(
            ready=False,
            detail=f"fixture is invalid or out of scope: {type(exc).__name__}",
        )
    return CheckResult(
        ready=True,
        detail=f"validated {len(snapshot.assets)} namespaced fixture assets",
    )


def _state_directory_check(settings: Settings) -> CheckResult:
    state_dir = Path(settings.app_state_dir)
    if not state_dir.is_dir():
        return CheckResult(ready=False, detail=f"state directory is missing: {state_dir}")
    if not os.access(state_dir, os.R_OK | os.W_OK):
        return CheckResult(ready=False, detail=f"state directory is not readable/writable: {state_dir}")
    return CheckResult(ready=True, detail="state directory is readable and writable")


def _datahub_token_check(settings: Settings) -> CheckResult:
    if not settings.datahub_token:
        return CheckResult(
            ready=False,
            detail="DATAHUB_TOKEN is not configured for supported DataHub writes",
        )
    return CheckResult(
        ready=True,
        detail="DataHub write credential is configured without exposing its value",
    )


def _vertical_slice_evidence_check(settings: Settings) -> CheckResult:
    receipt_path = settings.app_state_dir / "datahub-receipts" / "vertical-slice-receipt.json"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return CheckResult(
            ready=False,
            detail="verified DataHub vertical-slice receipt is missing",
        )
    except (OSError, ValueError):
        return CheckResult(
            ready=False,
            detail="DataHub vertical-slice receipt is unreadable or invalid",
        )
    if (
        receipt.get("operation") == "datahub_vertical_slice_invalidated"
        and receipt.get("project_slug") == settings.project_slug
    ):
        return CheckResult(
            ready=False,
            detail=(
                "DataHub vertical-slice evidence was invalidated by reset; "
                "run a fresh complete vertical slice"
            ),
        )
    expected = {
        "operation": "judge_ready_datahub_vertical_slice",
        "project_slug": settings.project_slug,
        "verified": True,
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        return CheckResult(
            ready=False,
            detail="DataHub vertical-slice receipt does not prove this project",
        )
    try:
        fixture_path = settings.demo_fixture_root / "graph_snapshot.json"
        snapshot = GraphSnapshot.model_validate_json(
            fixture_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return CheckResult(
            ready=False,
            detail="current fixture cannot be fingerprinted for evidence binding",
        )
    if receipt.get("fixture_fingerprint") != snapshot.fingerprint:
        return CheckResult(
            ready=False,
            detail="DataHub vertical-slice receipt is stale for the current fixture",
        )
    receipt_dir = receipt_path.parent.resolve()
    components = {
        "seed_receipt_path": "datahub-seed-receipt.json",
        "context_receipt_path": "context-read-receipt.json",
        "writeback_receipt_path": "writeback-receipt.json",
    }
    for key, filename in components.items():
        value = receipt.get(key)
        expected_path = (receipt_dir / filename).resolve()
        if not isinstance(value, str) or Path(value).resolve() != expected_path:
            return CheckResult(
                ready=False,
                detail="DataHub vertical-slice receipt has invalid component paths",
            )
        if not expected_path.is_file():
            return CheckResult(
                ready=False,
                detail=f"DataHub evidence component is missing: {filename}",
            )
    return CheckResult(
        ready=True,
        detail="seed, MCP context read, writeback, and reread receipt verified",
    )


def create_app(
    settings: Settings | None = None,
    datahub_probe: DataHubProbe = probe_datahub_gms,
) -> FastAPI:
    runtime_settings = Settings.from_env() if settings is None else settings
    runtime_settings.assert_coordinator_allocation()
    application = FastAPI(
        title="Lineage Lifeboat",
        version="0.1.0",
        docs_url="/api/docs" if runtime_settings.app_env in {"development", "local", "test"} else None,
        redoc_url="/api/redoc" if runtime_settings.app_env in {"development", "local", "test"} else None,
        openapi_url="/api/openapi.json"
        if runtime_settings.app_env in {"development", "local", "test"}
        else None,
    )
    demo_guard = DemoMutationGuard()
    public_mutation_controls = runtime_settings.app_env in {"hackathon", "production"}

    def client_key(request: Request) -> str:
        return request.client.host if request.client else "unknown-client"

    def capacity_error(error: DemoCapacityError) -> HTTPException:
        return HTTPException(
            status_code=429,
            detail="the public demo is busy; retry after the indicated delay",
            headers={"Retry-After": str(error.retry_after_seconds)},
        )

    def guarded_mutation(operation: DemoOperation) -> Callable[..., object]:
        async def dependency(
            request: Request,
            confirmation: Annotated[
                str | None,
                Header(alias="X-Demo-Confirmation", max_length=128),
            ] = None,
        ):
            try:
                if public_mutation_controls:
                    demo_guard.begin_public(
                        client_key(request),
                        operation,
                        confirmation or "",
                    )
                else:
                    demo_guard.begin_unrestricted()
            except DemoConfirmationError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except DemoCapacityError as exc:
                raise capacity_error(exc) from exc
            try:
                yield
            finally:
                demo_guard.finish()

        return dependency

    @application.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            project=runtime_settings.project_slug,
            version=application.version,
        )

    @application.get("/api/readiness", response_model=ReadinessResponse)
    def readiness(response: Response) -> ReadinessResponse:
        checks = {
            "coordinator_allocation": CheckResult(
                ready=True,
                detail="fixed project slug, port, namespace, tag, and fixture root accepted",
            ),
            "fixture": _fixture_check(runtime_settings),
            "state_directory": _state_directory_check(runtime_settings),
            "datahub_gms": datahub_probe(runtime_settings),
            "datahub_token": _datahub_token_check(runtime_settings),
            "datahub_vertical_slice": _vertical_slice_evidence_check(runtime_settings),
            "public_mutation_controls": CheckResult(
                ready=True,
                detail=(
                    "one-time operation-bound confirmations, single-flight execution, "
                    "cooldown, and request-rate limits are active"
                    if public_mutation_controls
                    else "public mutation controls are disabled in this trusted local environment"
                ),
            ),
        }
        ready = all(check.ready for check in checks.values())
        if not ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(ready=ready, checks=checks)

    static_root = Path(__file__).resolve().parent / "static"
    application.mount("/static", StaticFiles(directory=static_root), name="static")

    def recovery_workflow() -> RecoveryWorkflow:
        return RecoveryWorkflow(runtime_settings)

    @application.exception_handler(RecoveryWorkflowError)
    async def recovery_error_handler(
        _request: Request, error: RecoveryWorkflowError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(error), "error_type": type(error).__name__},
        )

    @application.get("/", response_class=HTMLResponse)
    def recovery_console() -> HTMLResponse:
        return HTMLResponse(
            (static_root / "index.html").read_text(encoding="utf-8")
        )

    @application.get("/api/demo/state")
    def demo_state() -> dict[str, object]:
        return recovery_workflow().estate.inspect()

    @application.get("/api/demo/graph")
    def demo_graph() -> dict[str, object]:
        snapshot = GraphSnapshot.model_validate_json(
            (runtime_settings.demo_fixture_root / "graph_snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        estate_state = recovery_workflow().estate.inspect()["assets"]
        return {
            "fingerprint": snapshot.fingerprint,
            "nodes": [
                {
                    "urn": asset.urn,
                    "name": asset.display_name,
                    "type": asset.artifact_type,
                    "owner": asset.owner,
                    "available": estate_state.get(asset.urn, False),
                }
                for asset in snapshot.assets
            ],
            "edges": [edge.model_dump(mode="json") for edge in snapshot.edges],
        }

    @application.post(
        "/api/demo/confirmation",
        response_model=DemoConfirmationResponse,
    )
    def issue_demo_confirmation(
        payload: DemoConfirmationRequest,
        request: Request,
    ) -> DemoConfirmationResponse:
        try:
            confirmation, ttl = demo_guard.issue_confirmation(
                client_key(request),
                payload.operation,
            )
        except DemoCapacityError as exc:
            raise capacity_error(exc) from exc
        return DemoConfirmationResponse(
            confirmation=confirmation,
            operation=payload.operation,
            expires_in_seconds=ttl,
        )

    @application.post(
        "/api/demo/initialize",
        dependencies=[Depends(guarded_mutation("initialize"))],
    )
    def initialize_demo() -> dict[str, object]:
        return recovery_workflow().initialize_estate(runtime_settings.project_slug)

    @application.post(
        "/api/demo/outage",
        dependencies=[Depends(guarded_mutation("outage"))],
    )
    def trigger_demo_outage() -> dict[str, object]:
        return recovery_workflow().trigger_outage(runtime_settings.project_slug)

    @application.post(
        "/api/recovery/plan",
        response_model=RecoveryRun,
        dependencies=[Depends(guarded_mutation("plan"))],
    )
    def compile_recovery(payload: RecoveryPlanRequest) -> RecoveryRun:
        return recovery_workflow().compile_run(
            payload.run_id,
            requester=payload.requester,
        )

    @application.get("/api/recovery/{run_id}", response_model=RecoveryRun)
    def get_recovery(run_id: str) -> RecoveryRun:
        return recovery_workflow().get_run(run_id)

    @application.post(
        "/api/recovery/{run_id}/approve",
        response_model=RecoveryRun,
        dependencies=[Depends(guarded_mutation("approve"))],
    )
    def approve_recovery(
        run_id: str,
        payload: RecoveryApprovalRequest,
    ) -> RecoveryRun:
        return recovery_workflow().approve(
            run_id,
            plan_id=payload.plan_id,
            approved_by=payload.approved_by,
        )

    @application.post(
        "/api/recovery/{run_id}/execute",
        response_model=RecoveryRun,
        dependencies=[Depends(guarded_mutation("execute"))],
    )
    async def execute_recovery(run_id: str) -> RecoveryRun:
        return await execute_with_datahub_writeback(
            recovery_workflow(),
            run_id,
        )

    @application.post(
        "/api/recovery/{run_id}/resume",
        response_model=RecoveryRun,
        dependencies=[Depends(guarded_mutation("resume"))],
    )
    async def resume_recovery(run_id: str) -> RecoveryRun:
        return await execute_with_datahub_writeback(
            recovery_workflow(),
            run_id,
        )

    return application


app = create_app()
