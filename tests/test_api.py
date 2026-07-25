from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import httpx
import pytest

from lineage_lifeboat.api import CheckResult, create_app
from lineage_lifeboat.config import Settings
from lineage_lifeboat.datahub_vertical_slice import reset_datahub
from lineage_lifeboat.domain.models import GraphSnapshot


def _get(app, path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(request())


def _write_vertical_slice_receipt(
    settings: Settings, *, fingerprint: str | None = None
) -> None:
    receipt_dir = (settings.app_state_dir / "datahub-receipts").resolve()
    receipt_dir.mkdir(parents=True, exist_ok=True)
    components = {
        "seed_receipt_path": receipt_dir / "datahub-seed-receipt.json",
        "context_receipt_path": receipt_dir / "context-read-receipt.json",
        "writeback_receipt_path": receipt_dir / "writeback-receipt.json",
    }
    for path in components.values():
        path.write_text(json.dumps({"project_slug": settings.project_slug}), encoding="utf-8")
    fixture = GraphSnapshot.model_validate_json(
        (settings.demo_fixture_root / "graph_snapshot.json").read_text(encoding="utf-8")
    )
    (receipt_dir / "vertical-slice-receipt.json").write_text(
        json.dumps(
            {
                "operation": "judge_ready_datahub_vertical_slice",
                "project_slug": settings.project_slug,
                "verified": True,
                "fixture_fingerprint": fingerprint or fixture.fingerprint,
                **{key: str(path) for key, path in components.items()},
            }
        ),
        encoding="utf-8",
    )


def _ready_settings(tmp_path) -> Settings:
    return replace(
        Settings.from_env({}),
        app_state_dir=tmp_path,
        datahub_token="test-only-token",
    )


class PartiallyFailingResetPort:
    def __init__(self) -> None:
        self.mutated_asset_urns: list[str] = []

    def reset(self, snapshot: GraphSnapshot) -> dict[str, object]:
        first_urn = sorted(asset.urn for asset in snapshot.assets)[0]
        self.mutated_asset_urns.append(first_urn)
        raise RuntimeError("simulated failure after one dataset mutation")


def test_health_is_liveness_only() -> None:
    app = create_app(
        Settings.from_env({}),
        datahub_probe=lambda _: CheckResult(ready=False, detail="offline"),
    )

    response = _get(app, "/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "project": "lineage-lifeboat",
        "version": "0.1.0",
    }


def test_readiness_passes_only_with_token_and_bound_live_evidence(tmp_path) -> None:
    settings = _ready_settings(tmp_path)
    _write_vertical_slice_receipt(settings)
    app = create_app(
        settings,
        datahub_probe=lambda _: CheckResult(ready=True, detail="connected"),
    )

    response = _get(app, "/api/readiness")

    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["checks"]["fixture"]["ready"] is True
    assert response.json()["checks"]["datahub_gms"]["ready"] is True
    assert response.json()["checks"]["datahub_token"]["ready"] is True
    assert response.json()["checks"]["datahub_vertical_slice"]["ready"] is True


def test_readiness_is_503_when_datahub_is_unavailable(tmp_path) -> None:
    settings = _ready_settings(tmp_path)
    _write_vertical_slice_receipt(settings)
    app = create_app(
        settings,
        datahub_probe=lambda _: CheckResult(ready=False, detail="offline"),
    )

    response = _get(app, "/api/readiness")

    assert response.status_code == 503
    assert response.json()["ready"] is False
    assert response.json()["checks"]["datahub_gms"] == {
        "ready": False,
        "detail": "offline",
    }


def test_readiness_is_503_until_vertical_slice_is_verified(tmp_path) -> None:
    settings = _ready_settings(tmp_path)
    app = create_app(
        settings,
        datahub_probe=lambda _: CheckResult(ready=True, detail="connected"),
    )

    response = _get(app, "/api/readiness")

    assert response.status_code == 503
    assert response.json()["checks"]["datahub_vertical_slice"] == {
        "ready": False,
        "detail": "verified DataHub vertical-slice receipt is missing",
    }


def test_readiness_is_503_when_write_token_is_removed(tmp_path) -> None:
    settings = replace(Settings.from_env({}), app_state_dir=tmp_path)
    _write_vertical_slice_receipt(settings)
    app = create_app(
        settings,
        datahub_probe=lambda _: CheckResult(ready=True, detail="connected"),
    )

    response = _get(app, "/api/readiness")

    assert response.status_code == 503
    assert response.json()["checks"]["datahub_token"] == {
        "ready": False,
        "detail": "DATAHUB_TOKEN is not configured for supported DataHub writes",
    }


def test_readiness_is_503_for_stale_fixture_evidence(tmp_path) -> None:
    settings = _ready_settings(tmp_path)
    _write_vertical_slice_receipt(settings, fingerprint="stale")
    app = create_app(
        settings,
        datahub_probe=lambda _: CheckResult(ready=True, detail="connected"),
    )

    response = _get(app, "/api/readiness")

    assert response.status_code == 503
    assert response.json()["checks"]["datahub_vertical_slice"] == {
        "ready": False,
        "detail": "DataHub vertical-slice receipt is stale for the current fixture",
    }


def test_partial_reset_invalidates_stale_readiness_until_fresh_slice(tmp_path) -> None:
    settings = replace(
        _ready_settings(tmp_path),
        app_state_dir=tmp_path / "lineage-lifeboat",
    )
    _write_vertical_slice_receipt(settings)
    app = create_app(
        settings,
        datahub_probe=lambda _: CheckResult(ready=True, detail="connected"),
    )
    assert _get(app, "/api/readiness").status_code == 200
    mutation = PartiallyFailingResetPort()

    with pytest.raises(RuntimeError, match="after one dataset mutation"):
        reset_datahub(settings, settings.project_slug, mutation)  # type: ignore[arg-type]

    assert len(mutation.mutated_asset_urns) == 1
    response = _get(app, "/api/readiness")
    assert response.status_code == 503
    assert response.json()["checks"]["datahub_vertical_slice"] == {
        "ready": False,
        "detail": (
            "DataHub vertical-slice evidence was invalidated by reset; "
            "run a fresh complete vertical slice"
        ),
    }
    reset_receipt = json.loads(
        (
            settings.app_state_dir
            / "datahub-receipts"
            / "datahub-reset-receipt.json"
        ).read_text()
    )
    assert reset_receipt["status"] == "failed"
    assert reset_receipt["completed"] is False
    assert reset_receipt["partial_mutation_possible"] is True
    assert reset_receipt["error_type"] == "RuntimeError"
    assert len(reset_receipt["target_asset_urns"]) == 8

    _write_vertical_slice_receipt(settings)
    assert _get(app, "/api/readiness").status_code == 200
