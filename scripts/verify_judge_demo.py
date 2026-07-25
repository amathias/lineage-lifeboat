from __future__ import annotations

import tempfile
import time
from dataclasses import replace
from pathlib import Path

from lineage_lifeboat.config import Settings
from lineage_lifeboat.domain.models import RecoveryRunStatus, StepExecutionStatus
from lineage_lifeboat.workflow import RecoveryWorkflow


def main() -> None:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="lineage-lifeboat-demo-") as temporary:
        settings = replace(
            Settings.from_env({}),
            app_state_dir=Path(temporary) / "lineage-lifeboat",
        )
        workflow = RecoveryWorkflow(settings)
        workflow.initialize_estate(settings.project_slug)
        workflow.trigger_outage(settings.project_slug)
        planned = workflow.compile_run("clean-demo-001", requester="demo-verifier")
        workflow.approve(
            planned.run_id,
            plan_id=planned.plan.plan_id,
            approved_by="demo-verifier",
        )
        completed = workflow.execute(planned.run_id)
        assert completed.status == RecoveryRunStatus.COMPLETED
        assert all(
            step.status == StepExecutionStatus.VERIFIED for step in completed.steps
        )
        assert workflow.estate.inspect()["healthy_asset_count"] == 8
    elapsed = time.perf_counter() - started
    assert elapsed < 180, f"demo exceeded three minutes: {elapsed:.2f}s"
    print(f"judge-demo-ok: 6/6 steps verified in {elapsed:.2f}s")


if __name__ == "__main__":
    main()