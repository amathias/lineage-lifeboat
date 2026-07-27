# Lineage Lifeboat

> A DataHub-powered recovery compiler that turns live lineage into an approved,
> dependency-correct, executable recovery program.

## Public links

- Live application:
  <https://lifeboat.datahub-hackathon.aaronmathias.com>
- Public source repository:
  <https://github.com/amathias/lineage-lifeboat>
- Under-three-minute recording runbook:
  <https://github.com/amathias/lineage-lifeboat/blob/main/docs/DEMO_RUNBOOK.md>
- Generated recovery plan:
  <https://github.com/amathias/lineage-lifeboat/blob/main/examples/recovery-plan.json>
- Generated recovery report:
  <https://github.com/amathias/lineage-lifeboat/blob/main/examples/recovery-report.md>
- Coordinator-owned live evidence summary:
  <https://github.com/amathias/lineage-lifeboat/blob/main/COORDINATOR_HANDOFF.md>

## Devpost short description

Lineage Lifeboat uses DataHub lineage and metadata to compile a safe recovery
DAG, requires approval for the exact plan, executes and validates real local
recovery adapters, and writes the verified outcome back to DataHub.

## Challenge category

**Primary category: Agents That Do Real Work**

Lineage Lifeboat does more than answer a metadata question. It uses DataHub as
the dependency and governance authority for an incident, converts that context
into deterministic control flow, executes approved recovery work, validates the
results, and performs a supported metadata writeback followed by an immediate
MCP reread.

The project also demonstrates an ML recovery use case through the
`features.customer_value` and `models.churn_model` branch, but the submission's
primary fit is Agents That Do Real Work.

## Inspiration

Disaster-recovery runbooks are usually organized by platform:

- restore the warehouse;
- restart transformations;
- rebuild features;
- redeploy models;
- refresh dashboards.

That organization misses the cross-platform dependency order. A storage restore
does not prove that a transformation, feature, model, or dashboard is ready to
trust. Static runbooks also drift as lineage and ownership change.

DataHub already contains the graph needed to answer the harder question:
**what must recover first, what becomes affected next, and what evidence is
required before a consumer is ready?**

## What it does

Lineage Lifeboat gives an incident commander one continuous workflow:

1. Initialize a disposable commerce data estate.
2. Trigger an explicitly confirmed outage affecting six connected assets.
3. Bind the incident to verified DataHub MCP entity and lineage evidence.
4. Compile a deterministic recovery DAG in five topological waves.
5. Exclude an unrelated inventory branch and retain a healthy customer
   prerequisite.
6. Require a human to approve the exact persisted plan ID.
7. Execute real idempotent recovery adapters.
8. Validate each restored target before its consumers can run.
9. Persist a resumable run ledger, adapter evidence, validations, and reports.
10. Write a supported `globalTags` recovery marker to DataHub and immediately
    verify it through the DataHub MCP Server.

If a required validation fails, the run stops before downstream consumers
execute. Resuming the run skips steps already verified and reuses stable
idempotency keys.

## The demonstrated recovery graph

| Wave | Target | Real adapter | Required proof |
|---|---|---|---|
| 1 | `raw.orders` | Parquet snapshot restore | existence, schema, row count |
| 2 | `analytics.stg_orders` | DuckDB SQL transform | existence, schema, checksum |
| 3 | `analytics.customer_revenue` | DuckDB SQL transform | existence, schema, nonnegative revenue |
| 4 | `features.customer_value` | deterministic Python build | existence, freshness |
| 4 | `dashboards.executive_revenue` | report refresh | existence, input fingerprint |
| 5 | `models.churn_model` | deterministic Python build | artifact load, accuracy threshold |

`raw.customers` remains a healthy prerequisite.
`inventory.forecast` is deliberately unrelated and remains excluded.

## How we built it

```text
Judge console / CLI
        |
        v
FastAPI workflow controller
        |
        +--> DataHub MCP context adapter
        |      entity context + complete direct lineage
        |
        +--> deterministic graph compiler and safety policy
        |      fingerprint + topology + approval requirements
        |
        +--> persisted approval and resumable run ledger
        |
        +--> recovery adapter registry
        |      Parquet -> DuckDB -> Python artifacts -> report
        |
        +--> validation engine
        |      schema + counts + checksums + freshness + rules
        |
        +--> DataHub RestEmitter writeback
               globalTags UPSERT -> immediate MCP reread
```

The planning and safety path is deterministic. No LLM output is trusted as an
execution authority. The optional LLM layer was intentionally left out of the
MVP so the complete demo remains reproducible without a paid service.

### Built with

- Open-source DataHub 1.6.0
- DataHub MCP Server
- DataHub Python SDK / RestEmitter
- Python
- FastAPI
- Pydantic
- NetworkX
- DuckDB and Parquet
- HTML, CSS, and browser JavaScript
- pytest, pytest-cov, and Ruff

## DataHub integration

The project establishes eight exact `lifeboat.` dataset fixtures and six
dataset-to-dataset lineage edges. The fixture metadata includes platform,
ownership, domain, project tags, adapter parameters, risk, approval, and
validation context.

The live integration:

- reads all required entities through DataHub MCP `get_entities`;
- reads complete direct downstream lineage through MCP `get_lineage`;
- binds the deterministic plan to the verified graph fingerprint;
- rejects missing entities or missing expected edges;
- uses a supported DataHub `MetadataChangeProposal` for a `globalTags` UPSERT;
- immediately rereads the target through MCP and requires the recovery marker;
- retains a scrubbed, immutable receipt and SHA-256 for each recovery run.

Readiness is fail-closed. GMS health alone is not enough: the service requires
current, project-bound read/write/reread evidence. Reset invalidates readiness
before its first mutation, and only a fresh complete vertical slice restores it.

## Live proof and evidence boundaries

The deployed application is exact candidate
`a304df864a9eedff91862d0d4642484f0ab89984`.

Coordinator-verified public closeout established:

- public page, health, and readiness returned HTTP 200 before and after;
- two approved runs each completed all six recovery steps;
- both runs recorded
  `context_evidence.mode=verified_live_datahub_mcp`;
- both runs recorded `datahub_outcome.status=verified`;
- run A's immutable receipt and ledger hashes were unchanged after run B;
- the stable writeback component and vertical-slice aggregate also remained
  unchanged;
- exact receipt, ledger, archive, and rollback hashes are preserved in
  `COORDINATOR_HANDOFF.md`.

The boundaries are deliberate:

| Claim | Boundary |
|---|---|
| DuckDB, Parquet, Python, and report actions | executed and validated against a disposable local estate |
| DataHub entity and lineage context | live MCP proof only when the run records `verified_live_datahub_mcp` |
| DataHub writeback | supported `globalTags` update, verified by immediate MCP reread |
| Cloud recovery | not performed |
| Production autonomy | not claimed |
| RPO or RTO guarantee | not claimed |
| Runtime receipts | sanitized, coordinator-owned evidence; not committed to Git |

## What makes it original

Lineage Lifeboat is not another backup system. It addresses the orchestration
gap between backups and trusted data products.

Its core idea is to treat cross-platform lineage as executable recovery control
flow. The graph decides blast radius and ordering; policy decides what is safe;
approval decides what may execute; validation decides when a consumer is ready;
writeback makes the incident result available to the next engineer or agent.

## Challenges we ran into

### Making live MCP evidence complete

The live MCP tool schema exposed a bounded result-limit argument. Without
setting it, one source with multiple downstream edges could return only a
partial result. The integration now inspects the advertised schema, supplies a
bounded limit, and refuses to proceed unless every expected edge is proven.

### Reset behavior across DataHub entity types

DataHub 1.6.0 accepts the dataset `status` aspect for the eight fixtures but not
for the project Domain and Tag controls. Reset now soft-deletes only the exact
dataset allowlist, retains all three controls, invalidates readiness before
mutation, and supports idempotent reseeding after partial reset.

### Search-index settling without weakening proof

Immediately after restoring dataset status, one live read briefly lacked a
dashboard lineage edge. The workflow failed closed before writeback. An
idempotent retry after indexing settled succeeded; validation was not weakened
to hide the transient.

### Evidence that survives later runs

A stable writeback filename was suitable for vertical-slice readiness but not
for historical recovery reports. A later run could replace the file referenced
by an earlier report. Recovery evidence now lives under a validated per-run
directory, is written atomically, and cannot be replaced with different bytes.
The public two-run gate proved run A remained verifiable after run B.

## Accomplishments

- Built a working cross-platform recovery compiler rather than a static
  runbook.
- Executed four real adapter families across six dependency-ordered targets.
- Added exact-plan approval, fail-closed validation, idempotency, and resume.
- Proved real DataHub MCP entity/lineage reads and supported writeback/reread.
- Preserved immutable per-run evidence across consecutive public runs.
- Kept the unrelated branch untouched through outage and recovery.
- Reached 51 automated tests and 85% aggregate coverage for the deployed
  candidate.
- Verified clean Git-archive wheel build, isolated install, and import.
- Kept the local workflow free of paid infrastructure and well below the
  three-minute demo ceiling.

## What we learned

- Recovery readiness is a graph property, not a service-health property.
- A successful mutation is not proof until the read path observes it.
- Evidence paths are part of the product contract; historical evidence must be
  immutable, scoped, and independently hashable.
- Fail-closed behavior matters most during transient indexing and partial
  reset, not only during obvious failures.
- Deterministic planning makes safety policies and demo claims independently
  testable.

## Try it

### Public application

Open <https://lifeboat.datahub-hackathon.aaronmathias.com>.

The public console exposes estate initialization, confirmed outage, graph
impact, plan compilation, exact approval, execution, validation evidence, and
DataHub outcome status.

Use a new safe run ID for each complete live take so its immutable evidence path
is unique.

### Local adoption

The local workflow runs without paid infrastructure:

```powershell
git clone https://github.com/amathias/lineage-lifeboat.git
cd lineage-lifeboat
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m lineage_lifeboat.cli demo-run `
  --run-id judge-demo-001 `
  --approved-by demo-incident-commander `
  --confirm-project lineage-lifeboat
```

Start the console:

```powershell
.\.venv\Scripts\python.exe -m lineage_lifeboat
```

Then open <http://localhost:8101>.

To adopt the pattern for another estate:

1. Ingest the recovery-relevant entities, lineage, owners, domain, tags, and
   adapter/validation context into DataHub.
2. Implement idempotent adapters behind the registry interface.
3. Add deterministic validations that prove each target is trustworthy.
4. Configure a project-scoped state root and namespace policy.
5. Keep destructive actions approval-gated.
6. Keep live credentials out of configuration files and Git.

## Safety and limitations

- The demonstrated outage acts only on the disposable local estate.
- DataHub writes are namespace- and fixture-guarded.
- Reset is allowlisted and never global.
- Exact approval is required before execution.
- Required validation failure blocks consumers.
- Missing tokens or stale/missing proof fail honestly.
- The MVP supports the demonstrated adapters, not every data platform.
- It does not perform cloud failover or autonomous production recovery.
- It does not guarantee recovery time or recovery point.

## What's next

- Add organization-specific adapters for orchestrators, warehouses, feature
  stores, and BI systems.
- Add authentication and role-aware production approval.
- Notify owners discovered from DataHub when a manual action is required.
- Compare recovery plans optimized for safety, time, or service priority.
- Export approved plans to Airflow, Dagster, or Prefect.
- Package the context and policy conventions as a reusable DataHub integration.

## License

Apache-2.0. The repository includes the complete setup, deterministic fixtures,
generated examples, tests, architectural decisions, and evidence boundaries.
