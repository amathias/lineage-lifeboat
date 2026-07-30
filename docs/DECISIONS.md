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

**Status:** Accepted; live reset/restore/writeback gate passed

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

## ADR-008: Reset dataset status while retaining project controls

**Status:** Accepted

**Date:** 2026-07-25

DataHub 1.6.0 accepts the `status` aspect for the eight dataset fixtures but
rejects that aspect for the project Domain and Tag entities. The deterministic
reset therefore emits `status.removed=true` only for the exact allowlisted
dataset URNs and retains the three exact project controls. Repeated reset is
idempotent, and seed emits `status.removed=false` for every fixture dataset so a
partial prior reset is fully recoverable.

Reset replaces the aggregate vertical-slice success receipt with an explicit
invalidation receipt before its first DataHub mutation. A completed, partial,
or failed reset therefore closes readiness immediately, and only a fresh
complete read/write/reread slice can restore readiness. Reset also writes its
own `started` receipt before mutation, then replaces it with either a typed
failure receipt or completed evidence, so a stale successful reset receipt
cannot survive a newer failed attempt.
## ADR-009: Use embedded DuckDB and file artifacts for executable recovery

**Status:** Accepted

**Date:** 2026-07-25

The judge demo uses an embedded DuckDB database plus deterministic JSON feature,
model, and dashboard artifacts under the dedicated `APP_STATE_DIR`. This matches
the existing DuckDB/Parquet graph contract, needs no paid or long-running
infrastructure, and makes every outage and recovery action disposable and
independently inspectable.

Four adapters perform real work: Parquet snapshot restore, DuckDB SQL transform,
Python artifact build, and report refresh. Each produces an idempotency key,
content hash, action label, and validation evidence. A persisted run ledger binds
approval to the exact plan ID, skips verified steps on resume, and blocks
consumers after required validation failure. The optional post-recovery DataHub
writeback reuses the already live-validated supported `globalTags` contract and
fails honestly when credentials are absent.

## ADR-010: Package a no-build single-screen judge console

**Status:** Accepted

**Date:** 2026-07-25

The MVP UI is packaged HTML, CSS, and browser JavaScript served by FastAPI. It
requires no Node build chain and keeps the clean-checkout demo to one Python
installation and one service command. The console exposes the exact deterministic
API transitions; it does not introduce a second planning or execution authority.

## ADR-011: Retain DataHub writeback evidence per recovery run

**Status:** Accepted; live two-run retention gate passed

**Date:** 2026-07-25

The stable `APP_STATE_DIR/datahub-receipts/writeback-receipt.json` is a component
of the authoritative Milestone B vertical-slice readiness record. Judge recovery
runs must not overwrite it. After a recovery writeback and immediate MCP reread,
the workflow therefore requests the already scrubbed receipt payload without
stable-path persistence and atomically writes the exact bytes beneath the
validated run directory as `datahub-writeback-receipt.json`.

The run ledger stores that immutable path and SHA-256. A different run ID maps to
a different validated directory. Reusing an identical existing receipt is safe;
different existing bytes, an escaped directory, a retention I/O failure, or an
unsafe run ID fails closed without replacement. No-token runs create no receipt.
The vertical-slice command keeps its established stable component paths and
readiness contract unchanged.

Coordinator live closeout on exact deployed candidate `a304df864a9eedff91862d0d4642484f0ab89984`
completed two approved 6/6 recovery runs. Run A's receipt and ledger hashes were
unchanged after run B, and the stable writeback component plus vertical-slice
aggregate hashes were also unchanged. This independently verified the decision's
per-run immutability and readiness-isolation contract.

## ADR-012: Public mutations use one-time capabilities and bounded admission

**Status:** Accepted

**Date:** 2026-07-29

The project slug remains a CLI guard against operator error, but is no longer accepted as the
HTTP mutation confirmation. On hosted environments, the browser must first obtain a short-lived
cryptographic capability bound to its client identity and one exact operation. The capability is
consumed on first use and cannot authorize another operation or be replayed.

Every hosted mutation is also serialized through one process-local single-flight guard, followed
by a cooldown, with per-client and global sliding-window limits. Capacity responses are `429` with
`Retry-After`; missing, expired, mismatched, or replayed capabilities are `403`. Local and test
workflows retain the same API sequence without public admission limits. These controls resist
blind scanners, cross-site requests, accidental replay, overlapping outage/recovery actions, and
unbounded anonymous state creation; they are not represented as user authentication.
