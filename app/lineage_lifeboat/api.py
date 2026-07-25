from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, Response, status
from pydantic import BaseModel, ConfigDict

from lineage_lifeboat.config import Settings
from lineage_lifeboat.domain.models import GraphSnapshot
from lineage_lifeboat.safety import DataHubScopePolicy, NamespaceViolationError


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


DataHubProbe = Callable[[Settings], CheckResult]


def probe_datahub_gms(settings: Settings) -> CheckResult:
    request = Request(f"{settings.datahub_gms_url}/health")
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
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

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
        }
        ready = all(check.ready for check in checks.values())
        if not ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(ready=ready, checks=checks)

    return application


app = create_app()