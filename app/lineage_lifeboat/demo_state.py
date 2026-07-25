from __future__ import annotations

import hashlib
import json
from pathlib import Path
from shutil import copyfile

from lineage_lifeboat.config import Settings
from lineage_lifeboat.domain.models import GraphSnapshot
from lineage_lifeboat.safety import DataHubScopePolicy

SEEDED_SNAPSHOT = "seeded-graph-snapshot.json"
SEED_RECEIPT = "seed-receipt.json"


class UnsafeResetTargetError(ValueError):
    """Raised when a local reset target is broader than the project allocation."""


def _scope_policy(settings: Settings) -> DataHubScopePolicy:
    return DataHubScopePolicy(
        domain=settings.datahub_domain,
        required_tag=settings.datahub_project_tag,
        urn_prefix=settings.datahub_urn_prefix,
    )


def _load_fixture(settings: Settings) -> tuple[GraphSnapshot, Path]:
    fixture_path = settings.demo_fixture_root / "graph_snapshot.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    snapshot = GraphSnapshot.model_validate(payload)
    _scope_policy(settings).assert_snapshot(snapshot)
    return snapshot, fixture_path


def _assert_safe_state_dir(state_dir: Path) -> Path:
    resolved = state_dir.resolve()
    forbidden = {Path(resolved.anchor), Path.cwd().resolve(), Path.home().resolve()}
    if resolved in forbidden or resolved.name != "lineage-lifeboat":
        raise UnsafeResetTargetError(
            "local demo state directory must be a dedicated path named 'lineage-lifeboat'"
        )
    return resolved


def seed_local(settings: Settings) -> dict[str, object]:
    settings.assert_coordinator_allocation()
    snapshot, fixture_path = _load_fixture(settings)
    state_dir = _assert_safe_state_dir(settings.app_state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)

    destination = state_dir / SEEDED_SNAPSHOT
    copyfile(fixture_path, destination)
    snapshot_sha256 = hashlib.sha256(destination.read_bytes()).hexdigest()
    receipt: dict[str, object] = {
        "project_slug": settings.project_slug,
        "datahub_domain": settings.datahub_domain,
        "datahub_project_tag": settings.datahub_project_tag,
        "datahub_urn_prefix": settings.datahub_urn_prefix,
        "graph_fingerprint": snapshot.fingerprint,
        "snapshot_sha256": snapshot_sha256,
        "asset_count": len(snapshot.assets),
        "edge_count": len(snapshot.edges),
        "datahub_seeded": False,
        "scope": "local_fixture_only",
    }
    receipt_path = state_dir / SEED_RECEIPT
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def reset_local(settings: Settings) -> tuple[str, ...]:
    settings.assert_coordinator_allocation()
    state_dir = _assert_safe_state_dir(settings.app_state_dir)
    removed: list[str] = []
    for filename in (SEEDED_SNAPSHOT, SEED_RECEIPT):
        target = state_dir / filename
        if target.is_file():
            target.unlink()
            removed.append(filename)
    return tuple(removed)