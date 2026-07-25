from __future__ import annotations

import argparse
import asyncio
import json

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
from lineage_lifeboat.safety import NamespaceViolationError


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
        help="Soft-delete only the canonical fixture and exact project controls.",
    )
    reset.add_argument("--confirm-project", required=True)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings.from_env()
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
        else:
            result = reset_datahub(settings, confirm_project=args.confirm_project)
    except (DataHubIntegrationError, NamespaceViolationError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
