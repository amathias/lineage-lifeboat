from __future__ import annotations

import re
from dataclasses import dataclass

from lineage_lifeboat.domain.models import AssetContext, GraphSnapshot


class NamespaceViolationError(ValueError):
    """Raised when DataHub context falls outside the project allocation."""


@dataclass(frozen=True, slots=True)
class DataHubScopePolicy:
    domain: str
    required_tag: str
    urn_prefix: str

    def assert_urn(self, urn: str) -> None:
        prefix_pattern = rf"[\(,]{re.escape(self.urn_prefix)}"
        if not re.search(prefix_pattern, urn):
            raise NamespaceViolationError(
                f"URN is outside the {self.urn_prefix!r} namespace: {urn}"
            )

    def assert_asset(self, asset: AssetContext) -> None:
        self.assert_urn(asset.urn)
        if asset.domain != self.domain:
            raise NamespaceViolationError(
                f"{asset.urn} has domain {asset.domain!r}; expected {self.domain!r}"
            )
        if self.required_tag not in asset.tags:
            raise NamespaceViolationError(
                f"{asset.urn} lacks required tag {self.required_tag!r}"
            )

    def assert_snapshot(self, snapshot: GraphSnapshot) -> None:
        for asset in snapshot.assets:
            self.assert_asset(asset)