from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import httpx
from lineage_lifeboat.api import CheckResult, create_app
from lineage_lifeboat.config import Settings


def test_hosted_mutation_needs_fresh_operation_bound_confirmation(tmp_path: Path) -> None:
    settings = replace(
        Settings.from_env({}),
        app_env="hackathon",
        app_state_dir=tmp_path / "lineage-lifeboat",
    )
    app = create_app(
        settings,
        datahub_probe=lambda _: CheckResult(ready=False, detail="offline test"),
    )

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            published_slug = await client.post(
                "/api/demo/outage",
                json={"confirm_project": "lineage-lifeboat"},
            )
            assert published_slug.status_code == 403

            issued = await client.post(
                "/api/demo/confirmation",
                json={"operation": "initialize"},
            )
            assert issued.status_code == 200
            token = issued.json()["confirmation"]
            headers = {"X-Demo-Confirmation": token}

            initialized = await client.post(
                "/api/demo/initialize",
                json={},
                headers=headers,
            )
            assert initialized.status_code == 200

            replayed = await client.post(
                "/api/demo/initialize",
                json={},
                headers=headers,
            )
            assert replayed.status_code == 403

    asyncio.run(scenario())
