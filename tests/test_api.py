from __future__ import annotations

import asyncio
from dataclasses import replace

import httpx

from lineage_lifeboat.api import CheckResult, create_app
from lineage_lifeboat.config import Settings


def _get(app, path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(request())


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


def test_readiness_passes_only_when_local_state_and_datahub_are_ready(tmp_path) -> None:
    settings = replace(Settings.from_env({}), app_state_dir=tmp_path)
    app = create_app(
        settings,
        datahub_probe=lambda _: CheckResult(ready=True, detail="connected"),
    )

    response = _get(app, "/api/readiness")

    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["checks"]["fixture"]["ready"] is True
    assert response.json()["checks"]["datahub_gms"]["ready"] is True


def test_readiness_is_503_when_datahub_is_unavailable(tmp_path) -> None:
    settings = replace(Settings.from_env({}), app_state_dir=tmp_path)
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