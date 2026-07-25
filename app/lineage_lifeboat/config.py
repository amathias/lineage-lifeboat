from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when runtime configuration violates the coordinator allocation."""


@dataclass(frozen=True, slots=True)
class Settings:
    project_slug: str
    app_env: str
    app_host: str
    app_port: int
    app_public_url: str
    app_state_dir: Path
    datahub_gms_url: str
    datahub_mcp_url: str
    datahub_token: str | None
    datahub_domain: str
    datahub_project_tag: str
    datahub_urn_prefix: str
    demo_fixture_root: Path

    FIXED_PROJECT_SLUG = "lineage-lifeboat"
    FIXED_APP_PORT = 8101
    FIXED_DATAHUB_DOMAIN = "Demo / Lineage Lifeboat"
    FIXED_DATAHUB_PROJECT_TAG = "project-lineage-lifeboat"
    FIXED_DATAHUB_URN_PREFIX = "lifeboat."
    FIXED_FIXTURE_ROOT = Path("demo/fixtures/lineage-lifeboat")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        values = os.environ if env is None else env
        settings = cls(
            project_slug=values.get("PROJECT_SLUG", cls.FIXED_PROJECT_SLUG),
            app_env=values.get("APP_ENV", "development"),
            app_host=values.get("APP_HOST", "127.0.0.1"),
            app_port=int(values.get("APP_PORT", str(cls.FIXED_APP_PORT))),
            app_public_url=values.get(
                "APP_PUBLIC_URL", f"http://localhost:{cls.FIXED_APP_PORT}"
            ),
            app_state_dir=Path(
                values.get("APP_STATE_DIR", ".data/lineage-lifeboat")
            ),
            datahub_gms_url=values.get(
                "DATAHUB_GMS_URL", "http://127.0.0.1:8080"
            ).rstrip("/"),
            datahub_mcp_url=values.get(
                "DATAHUB_MCP_URL", "http://127.0.0.1:8000/mcp"
            ).rstrip("/"),
            datahub_token=values.get("DATAHUB_TOKEN") or None,
            datahub_domain=values.get(
                "DATAHUB_DOMAIN", cls.FIXED_DATAHUB_DOMAIN
            ),
            datahub_project_tag=values.get(
                "DATAHUB_PROJECT_TAG", cls.FIXED_DATAHUB_PROJECT_TAG
            ),
            datahub_urn_prefix=values.get(
                "DATAHUB_URN_PREFIX", cls.FIXED_DATAHUB_URN_PREFIX
            ),
            demo_fixture_root=Path(
                values.get("DEMO_FIXTURE_ROOT", str(cls.FIXED_FIXTURE_ROOT))
            ),
        )
        settings.assert_coordinator_allocation()
        return settings

    def assert_coordinator_allocation(self) -> None:
        fixed_values = {
            "PROJECT_SLUG": (self.project_slug, self.FIXED_PROJECT_SLUG),
            "APP_PORT": (self.app_port, self.FIXED_APP_PORT),
            "DATAHUB_DOMAIN": (self.datahub_domain, self.FIXED_DATAHUB_DOMAIN),
            "DATAHUB_PROJECT_TAG": (
                self.datahub_project_tag,
                self.FIXED_DATAHUB_PROJECT_TAG,
            ),
            "DATAHUB_URN_PREFIX": (
                self.datahub_urn_prefix,
                self.FIXED_DATAHUB_URN_PREFIX,
            ),
            "DEMO_FIXTURE_ROOT": (
                self.demo_fixture_root.as_posix(),
                self.FIXED_FIXTURE_ROOT.as_posix(),
            ),
        }
        violations = [
            f"{name} must be {expected!r}, got {actual!r}"
            for name, (actual, expected) in fixed_values.items()
            if actual != expected
        ]
        if violations:
            raise ConfigurationError("; ".join(violations))