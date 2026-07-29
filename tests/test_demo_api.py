from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import httpx
from lineage_lifeboat.api import CheckResult, create_app
from lineage_lifeboat.config import Settings


def _settings(tmp_path: Path) -> Settings:
    return replace(
        Settings.from_env({}),
        app_state_dir=tmp_path / "lineage-lifeboat",
    )


def test_judge_console_runs_complete_approved_recovery(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    app = create_app(
        settings,
        datahub_probe=lambda _: CheckResult(ready=False, detail="offline local demo"),
    )

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            page = await client.get("/")
            assert page.status_code == 200
            assert "Restore trust" in page.text
            assert "PUBLIC DEMO" in page.text
            assert "lifeboat.*" in page.text

            initialized = await client.post(
                "/api/demo/initialize",
                json={"confirm_project": "lineage-lifeboat"},
            )
            assert initialized.status_code == 200
            assert initialized.json()["asset_state"]["healthy_asset_count"] == 8

            outage = await client.post(
                "/api/demo/outage",
                json={"confirm_project": "lineage-lifeboat"},
            )
            assert outage.status_code == 200
            assert len(outage.json()["removed_asset_urns"]) == 6

            planned = await client.post(
                "/api/recovery/plan",
                json={"run_id": "api-demo-001", "requester": "api-commander"},
            )
            assert planned.status_code == 200
            plan = planned.json()
            assert plan["status"] == "planned"
            assert len(plan["plan"]["waves"]) == 5

            rejected = await client.post("/api/recovery/api-demo-001/execute")
            assert rejected.status_code == 409
            assert rejected.json()["error_type"] == "ApprovalRequiredError"

            approved = await client.post(
                "/api/recovery/api-demo-001/approve",
                json={
                    "plan_id": plan["plan"]["plan_id"],
                    "approved_by": "api-commander",
                },
            )
            assert approved.status_code == 200

            executed = await client.post("/api/recovery/api-demo-001/execute")
            assert executed.status_code == 200
            run = executed.json()
            assert run["status"] == "completed"
            assert all(step["status"] == "verified" for step in run["steps"])
            assert run["datahub_outcome"]["status"] == "not_configured"

            graph = await client.get("/api/demo/graph")
            assert graph.status_code == 200
            assert sum(node["available"] for node in graph.json()["nodes"]) == 8

    asyncio.run(scenario())
