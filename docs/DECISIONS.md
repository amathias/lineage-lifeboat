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

## ADR-003: Pin the DataHub and MCP versions after a read/write spike

**Status:** Accepted  
**Date:** 2026-07-24

The project will use open-source DataHub Core and the self-hosted DataHub MCP
Server. Exact versions will be recorded only after an integration test proves:

- entity and lineage reads through MCP;
- at least one supported metadata mutation;
- read-after-write verification in DataHub.

No UI work depends on an unverified DataHub integration.

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
