from __future__ import annotations

import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from lineage_lifeboat.config import Settings
from lineage_lifeboat.workflow import RecoveryWorkflow

ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = datetime(2026, 7, 25, 15, 0, tzinfo=UTC)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="lineage-lifeboat-examples-") as temporary:
        settings = replace(
            Settings.from_env({}),
            app_state_dir=Path(temporary) / "lineage-lifeboat",
        )
        workflow = RecoveryWorkflow(settings, clock=lambda: FIXED_TIME)
        workflow.initialize_estate(settings.project_slug)
        workflow.trigger_outage(settings.project_slug)
        planned = workflow.compile_run(
            "judge-demo-001",
            requester="demo-incident-commander",
        )
        workflow.approve(
            planned.run_id,
            plan_id=planned.plan.plan_id,
            approved_by="demo-incident-commander",
        )
        completed = workflow.execute(planned.run_id)
        if completed.status != "completed":
            raise RuntimeError("example recovery did not complete")
        exported = workflow.export_examples(planned.run_id, ROOT / "examples")
        for path in exported:
            print(f"generated {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()