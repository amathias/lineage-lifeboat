from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    """Base model for persisted and externally supplied contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AssetAvailability(StrEnum):
    HEALTHY = "healthy"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ArtifactType(StrEnum):
    DATASET = "dataset"
    FEATURE = "feature"
    MODEL = "model"
    DASHBOARD = "dashboard"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskMode(StrEnum):
    CONSERVATIVE = "conservative"
    DEMO = "demo"


class ValidationSpec(StrictModel):
    kind: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    required: bool = True


class AssetContext(StrictModel):
    urn: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    artifact_type: ArtifactType
    platform: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    tags: tuple[str, ...]
    availability: AssetAvailability = AssetAvailability.UNKNOWN
    owner: str | None = None
    adapter: str | None = None
    adapter_parameters: dict[str, Any] = Field(default_factory=dict)
    validations: tuple[ValidationSpec, ...] = ()
    risk: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False


class LineageEvidence(StrictModel):
    source: str = "datahub_mcp"
    tool: str = "get_lineage"
    upstream_urn: str
    downstream_urn: str


class LineageEdge(StrictModel):
    upstream_urn: str
    downstream_urn: str
    evidence: LineageEvidence

    @field_validator("evidence")
    @classmethod
    def evidence_matches_edge(
        cls, evidence: LineageEvidence, info: Any
    ) -> LineageEvidence:
        upstream = info.data.get("upstream_urn")
        downstream = info.data.get("downstream_urn")
        if upstream and evidence.upstream_urn != upstream:
            raise ValueError("evidence upstream_urn must match the lineage edge")
        if downstream and evidence.downstream_urn != downstream:
            raise ValueError("evidence downstream_urn must match the lineage edge")
        return evidence


class GraphSnapshot(StrictModel):
    source_instance: str = Field(min_length=1)
    captured_at: datetime
    assets: tuple[AssetContext, ...]
    edges: tuple[LineageEdge, ...]

    @field_validator("assets")
    @classmethod
    def asset_urns_are_unique(
        cls, assets: tuple[AssetContext, ...]
    ) -> tuple[AssetContext, ...]:
        urns = [asset.urn for asset in assets]
        if len(urns) != len(set(urns)):
            raise ValueError("asset URNs must be unique")
        return assets

    @property
    def fingerprint(self) -> str:
        """Hash stable graph content while excluding the retrieval timestamp."""

        payload = {
            "source_instance": self.source_instance,
            "assets": sorted(
                (asset.model_dump(mode="json") for asset in self.assets),
                key=lambda item: item["urn"],
            ),
            "edges": sorted(
                (edge.model_dump(mode="json") for edge in self.edges),
                key=lambda item: (item["upstream_urn"], item["downstream_urn"]),
            ),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RecoveryRequest(StrictModel):
    request_id: str = Field(min_length=1)
    incident_type: str = Field(min_length=1)
    unavailable_asset_urns: tuple[str, ...]
    target_recovery_point: datetime | None = None
    max_blast_radius_depth: int = Field(default=10, ge=0, le=25)
    risk_mode: RiskMode = RiskMode.CONSERVATIVE
    requester: str = Field(min_length=1)

    @field_validator("unavailable_asset_urns")
    @classmethod
    def normalize_unavailable_assets(cls, urns: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted(set(urns)))
        if not normalized:
            raise ValueError("at least one unavailable asset URN is required")
        return normalized


class SelectionDecision(StrEnum):
    RECOVERY_TARGET = "recovery_target"
    HEALTHY_PRECONDITION = "healthy_precondition"
    EXCLUDED = "excluded"


class AssetSelection(StrictModel):
    urn: str
    decision: SelectionDecision
    reason: str


class RecoveryStep(StrictModel):
    step_id: str
    target_urn: str
    dependency_step_ids: tuple[str, ...]
    healthy_precondition_urns: tuple[str, ...]
    adapter: str
    adapter_parameters: dict[str, Any]
    validations: tuple[ValidationSpec, ...]
    risk: RiskLevel
    requires_approval: bool


class RecoveryPlan(StrictModel):
    plan_id: str
    compiler_version: str
    request_id: str
    graph_fingerprint: str
    steps: tuple[RecoveryStep, ...]
    waves: tuple[tuple[str, ...], ...]
    selections: tuple[AssetSelection, ...]

    def step_for_urn(self, urn: str) -> RecoveryStep:
        for step in self.steps:
            if step.target_urn == urn:
                return step
        raise KeyError(urn)

class RecoveryRunStatus(StrEnum):
    PLANNED = "planned"
    APPROVED = "approved"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETED = "completed"


class StepExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    VERIFIED = "verified"


class ContextEvidence(StrictModel):
    mode: str
    graph_fingerprint: str
    receipt_path: str | None = None
    receipt_sha256: str | None = None
    detail: str


class ApprovalRecord(StrictModel):
    plan_id: str
    approved_by: str = Field(min_length=1)
    approved_at: datetime


class AdapterEvidence(StrictModel):
    adapter: str
    action: str
    executed: bool
    idempotency_key: str
    target: str
    output_sha256: str
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(StrictModel):
    kind: str
    required: bool
    passed: bool
    detail: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class StepExecution(StrictModel):
    step_id: str
    target_urn: str
    status: StepExecutionStatus = StepExecutionStatus.PENDING
    attempts: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    adapter_evidence: AdapterEvidence | None = None
    validations: tuple[ValidationResult, ...] = ()
    error_type: str | None = None
    error_detail: str | None = None


class DataHubOutcome(StrictModel):
    status: str
    detail: str
    receipt_path: str | None = None
    receipt_sha256: str | None = None


class RecoveryRun(StrictModel):
    schema_version: int = 1
    run_id: str
    created_at: datetime
    updated_at: datetime
    status: RecoveryRunStatus
    request: RecoveryRequest
    plan: RecoveryPlan
    context_evidence: ContextEvidence
    approval: ApprovalRecord | None = None
    steps: tuple[StepExecution, ...]
    datahub_outcome: DataHubOutcome
    report_json_path: str | None = None
    report_markdown_path: str | None = None
