from __future__ import annotations

import argparse
import json

from lineage_lifeboat.config import Settings
from lineage_lifeboat.demo_state import reset_local, seed_local


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
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = Settings.from_env()
    if args.command == "seed-local":
        result: object = seed_local(settings)
    else:
        result = {"removed": reset_local(settings)}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()