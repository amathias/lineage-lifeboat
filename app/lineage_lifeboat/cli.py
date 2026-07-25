from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from lineage_lifeboat.config import Settings
from lineage_lifeboat.datahub_vertical_slice import (
    DEFAULT_WRITEBACK_TARGET,
    DataHubIntegrationError,
    read_datahub_context,
    reset_datahub,
    run_vertical_slice,
    seed_datahub,
    writeback_and_verify,
)
from lineage_lifeboat.demo_state import reset_local, seed_local
from lineage_lifeboat.estate import DemoEstateError
from lineage_lifeboat.safety import NamespaceViolationError
from lineage_lifeboat.workflow import (
    RecoveryWorkflow,
    RecoveryWorkflowError,
    execute_with_datahub_writeback,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lineage-lifeboat")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser(
        "seed-local",
        help="Seed deterministic local fixture state; does not mutate DataHub.",
    )
    subcommands.add_parser(
        "reset-local",
        help="Remove only the known local fixture-state files.",
    )
    subcommands.add_parser(
        "seed-datahub",
        help="Upsert only the canonical namespaced fixture and lineage into DataHub.",
    )
    subcommands.add_parser(
        "read-datahub",
        help="Read and verify fixture entities and lineage through DataHub MCP.",
    )
    writeback = subcommands.add_parser(
        "writeback-datahub",
        help="Write a guarded recovery marker and immediately reread it via MCP.",
    )
    writeback.add_argument("--run-id", required=True)
    writeback.add_argument("--target-urn", default=DEFAULT_WRITEBACK_TARGET)
    vertical = subcommands.add_parser(
        "datahub-vertical-slice",
        help="Seed, MCP-read, write back, reread, and preserve receipts.",
    )
    vertical.add_argument("--run-id", required=True)
    reset = subcommands.add_parser(
        "reset-datahub",
        help="Soft-delete only the eight canonical dataset fixtures.",
    )
    reset.add_argument("--confirm-project", required=True)

    initialize = subcommands.add_parser(
        "demo-initialize",
        help="Initialize the real disposable DuckDB and artifact estate.",
    )
    initialize.add_argument("--confirm-project", required=True)
    outage = subcommands.add_parser(
        "demo-outage",
        help="Remove only the six disposable recovery targets.",
    )
    outage.add_argument("--confirm-project", required=True)
    subcommands.add_parser("demo-state", help="Inspect the disposable estate.")
    plan = subcommands.add_parser(
        "demo-plan",
        help="Compile and persist a deterministic recovery plan.",
    )
    plan.add_argument("--run-id", required=True)
    plan.add_argument("--requester", default="incident-commander")
    approve = subcommands.add_parser(
        "demo-approve",
        help="Approve an exact persisted plan before execution.",
    )
    approve.add_argument("--run-id", required=True)
    approve.add_argument("--plan-id", required=True)
    approve.add_argument("--approved-by", required=True)
    execute = subcommands.add_parser(
        "demo-execute",
        help="Execute or resume the approved plan and verify evidence.",
    )
    execute.add_argument("--run-id", required=True)
    demo_run = subcommands.add_parser(
        "demo-run",
        help="Run the complete local initialize/outage/plan/approve/execute demo.",
    )
    demo_run.add_argument("--run-id", default="judge-demo-001")
    demo_run.add_argument("--approved-by", default="demo-incident-commander")
    demo_run.add_argument("--confirm-project", required=True)
    export = subcommands.add_parser(
        "demo-export",
        help="Export a persisted plan and report bundle.",
    )
    export.add_argument("--run-id", required=True)
    export.add_argument("--destination", type=Path, required=True)
    return parser


async def _run_complete_demo(
    workflow: RecoveryWorkflow,
    *,
    run_id: str,
    approved_by: str,
    confirm_project: str,
) -> object:
    workflow.initialize_estate(confirm_project)
    workflow.trigger_outage(confirm_project)
    planned = workflow.compile_run(run_id, requester=approved_by)
    workflow.approve(
        run_id,
        plan_id=planned.plan.plan_id,
        approved_by=approved_by,
    )
    return await execute_with_datahub_writeback(workflow, run_id)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings.from_env()
    workflow = RecoveryWorkflow(settings)
    try:
        if args.command == "seed-local":
            result: object = seed_local(settings)
        elif args.command == "reset-local":
            result = {"removed": reset_local(settings)}
        elif args.command == "seed-datahub":
            result = seed_datahub(settings)
        elif args.command == "read-datahub":
            result = asyncio.run(read_datahub_context(settings))
        elif args.command == "writeback-datahub":
            result = asyncio.run(
                writeback_and_verify(
                    settings,
                    run_id=args.run_id,
                    target_urn=args.target_urn,
                )
            )
        elif args.command == "datahub-vertical-slice":
            result = asyncio.run(run_vertical_slice(settings, run_id=args.run_id))
        elif args.command == "reset-datahub":
            result = reset_datahub(settings, confirm_project=args.confirm_project)
        elif args.command == "demo-initialize":
            result = workflow.initialize_estate(args.confirm_project)
        elif args.command == "demo-outage":
            result = workflow.trigger_outage(args.confirm_project)
        elif args.command == "demo-state":
            result = workflow.estate.inspect()
        elif args.command == "demo-plan":
            result = workflow.compile_run(
                args.run_id,
                requester=args.requester,
            )
        elif args.command == "demo-approve":
            result = workflow.approve(
                args.run_id,
                plan_id=args.plan_id,
                approved_by=args.approved_by,
            )
        elif args.command == "demo-execute":
            result = asyncio.run(
                execute_with_datahub_writeback(workflow, args.run_id)
            )
        elif args.command == "demo-export":
            paths = workflow.export_examples(args.run_id, args.destination)
            result = {"exported": [str(path) for path in paths]}
        else:
            result = asyncio.run(
                _run_complete_demo(
                    workflow,
                    run_id=args.run_id,
                    approved_by=args.approved_by,
                    confirm_project=args.confirm_project,
                )
            )
    except (
        DataHubIntegrationError,
        DemoEstateError,
        NamespaceViolationError,
        RecoveryWorkflowError,
    ) as error:
        parser.exit(2, f"error: {error}\n")
    if hasattr(result, "model_dump"):
        result = result.model_dump(mode="json")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
