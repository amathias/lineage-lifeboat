from __future__ import annotations

import json
from dataclasses import replace

import pytest

from lineage_lifeboat.config import Settings
from lineage_lifeboat.demo_state import (
    SEEDED_SNAPSHOT,
    SEED_RECEIPT,
    UnsafeResetTargetError,
    reset_local,
    seed_local,
)


def test_local_seed_is_deterministic_and_namespaced(tmp_path) -> None:
    state_dir = tmp_path / "lineage-lifeboat"
    settings = replace(Settings.from_env({}), app_state_dir=state_dir)

    first = seed_local(settings)
    first_receipt = (state_dir / SEED_RECEIPT).read_bytes()
    second = seed_local(settings)
    second_receipt = (state_dir / SEED_RECEIPT).read_bytes()

    assert first == second
    assert first_receipt == second_receipt
    assert first["asset_count"] == 8
    assert first["datahub_seeded"] is False
    assert first["scope"] == "local_fixture_only"
    assert (state_dir / SEEDED_SNAPSHOT).is_file()


def test_local_reset_removes_only_known_fixture_files(tmp_path) -> None:
    state_dir = tmp_path / "lineage-lifeboat"
    settings = replace(Settings.from_env({}), app_state_dir=state_dir)
    seed_local(settings)
    evidence = state_dir / "preserve-evidence.json"
    evidence.write_text(json.dumps({"keep": True}), encoding="utf-8")

    removed = reset_local(settings)

    assert removed == (SEEDED_SNAPSHOT, SEED_RECEIPT)
    assert evidence.is_file()
    assert reset_local(settings) == ()


def test_local_reset_refuses_broad_or_foreign_directory(tmp_path) -> None:
    settings = replace(Settings.from_env({}), app_state_dir=tmp_path / "another-project")

    with pytest.raises(UnsafeResetTargetError, match="dedicated path"):
        reset_local(settings)