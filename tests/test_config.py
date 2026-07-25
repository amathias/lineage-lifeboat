from __future__ import annotations

import pytest

from lineage_lifeboat.config import ConfigurationError, Settings


def test_defaults_match_coordinator_allocation() -> None:
    settings = Settings.from_env({})

    assert settings.project_slug == "lineage-lifeboat"
    assert settings.app_port == 8101
    assert settings.datahub_domain == "Demo / Lineage Lifeboat"
    assert settings.datahub_project_tag == "project-lineage-lifeboat"
    assert settings.datahub_urn_prefix == "lifeboat."
    assert settings.demo_fixture_root.as_posix() == "demo/fixtures/lineage-lifeboat"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("PROJECT_SLUG", "another-project"),
        ("APP_PORT", "9999"),
        ("DATAHUB_DOMAIN", "Demo / Another Project"),
        ("DATAHUB_PROJECT_TAG", "project-another"),
        ("DATAHUB_URN_PREFIX", "another."),
        ("DEMO_FIXTURE_ROOT", "demo/fixtures/another"),
    ],
)
def test_shared_allocation_changes_fail_closed(name: str, value: str) -> None:
    with pytest.raises(ConfigurationError, match=name):
        Settings.from_env({name: value})