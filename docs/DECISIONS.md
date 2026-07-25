# Architectural Decisions

## ADR-001: Deterministic planning is the execution authority

**Status:** Accepted

**Date:** 2026-07-24

Lineage Lifeboat compiles recovery plans with typed Python code and explicit
graph algorithms. An LLM may translate incident intake or explain a compiled
plan, but its output cannot determine dependency ordering or invoke an
execution adapter directly.

This keeps identical graph snapshots and requests reproducible, makes ordering
independently testable, and ensures malformed model output fails closed.

## ADR-002: Use a canonical six-target commerce recovery scenario

**Status:** Accepted

**Date:** 2026-07-24

The MVP restores six targets:

1. `raw.orders`
2. `analytics.stg_orders`
3. `analytics.customer_revenue`
4. `features.customer_value`
5. `models.churn_model`
6. `dashboards.executive_revenue`

`raw.customers` remains a healthy prerequisite. An unrelated inventory asset is
present and must be excluded. This fixture demonstrates dependency ordering,
safe parallel waves, healthy preconditions, and correct blast-radius selection.

## ADR-003: Pin the DataHub and MCP client contracts

**Status:** Accepted; live environment receipt pending

**Date:** 2026-07-25

The application pins `acryl-datahub==1.6.0.15` and `mcp==1.28.1`. Local contract tests validate MetadataChangeProposal construction, the official MCP `urns` batch argument, downstream `get_lineage` calls with `upstream=false`, writeback verification, and reset isolation. A deployment is not considered DataHub-ready until the live vertical-slice command produces its MCP read-after-write receipt; local contract tests do not substitute for that receipt.

## ADR-004: Python 3.12 and 3.13 compatibility

**Status:** Accepted

**Date:** 2026-07-24

The project targets Python 3.12 and 3.13. The current development machine has
Python 3.13, while the original project brief recommended Python 3.12.
## ADR-005: Enforce the portfolio allocation in application code

**Status:** Accepted

**Date:** 2026-07-24

The service validates its fixed project slug, port, DataHub domain, required tag, URN prefix, and
fixture root at startup. DataHub graph snapshots must contain only assets inside the `lifeboat.`
namespace with the allocated domain and tag. Local reset removes only explicitly allowlisted files
from a dedicated directory named `lineage-lifeboat`.

This makes accidental cross-project reads, writes, or resets fail closed. Any future change to these
values requires a coordinator decision before the constants and tests are updated.

## ADR-006: Catalog all recovery artifacts as platform-specific datasets

**Status:** Accepted

**Date:** 2026-07-25

The deterministic graph models the ML model and dashboard recovery artifacts as DataHub dataset entities on the `mlflow` and `looker` platforms, while retaining `lifeboat.artifact_type=model|dashboard` context. This keeps all six fixture edges within DataHub's documented Dataset-to-Dataset lineage combination, makes ordering independently verifiable, and avoids inventing unsupported Dataset-to-MLModel lineage.

## ADR-007: Require durable read-after-write evidence for readiness

**Status:** Accepted

**Date:** 2026-07-25

GMS health alone does not prove that fixture ingestion, MCP context retrieval, or writeback works. The live vertical-slice command therefore persists separate seed, context-read, writeback/reread, and aggregate receipts under `APP_STATE_DIR/datahub-receipts`. Readiness remains false until the aggregate receipt identifies this project and records a verified end-to-end run. Receipts reject credential keys and the configured token value before writing.
