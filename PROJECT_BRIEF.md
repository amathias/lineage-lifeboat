# Project Brief: Lineage Lifeboat

## Product thesis

Recovery order is a graph problem. DataHub already knows the cross-platform dependency graph, operational ownership, schemas, and governance signals. Lineage Lifeboat turns that context into a safe executable recovery program and leaves the graph more useful after every incident.

## Problem

Disaster-recovery runbooks are usually organized by platform or team:

- Restore the warehouse.
- Restart transformations.
- Rebuild features.
- Redeploy models.
- Refresh dashboards.

This loses cross-platform dependency order, hidden consumers, validation requirements, and current ownership. Static runbooks also drift as the data stack changes.

## MVP scenario

Create a local “commerce intelligence” estate:

1. `raw.orders` and `raw.customers` in a local source database.
2. `analytics.stg_orders` and `analytics.customer_revenue` transformations.
3. `features.customer_value`.
4. `models.churn_model`.
5. `dashboards.executive_revenue`.
6. One unrelated asset that should not be included in the plan.

Ingest these entities, schemas, owners, assertions, platforms, and lineage into DataHub. Simulate loss of the analytics system or selected assets. The agent must discover the affected subgraph and recover it in valid order.

## Core user journey

1. Incident commander selects an outage scope and recovery objective.
2. Agent queries DataHub for affected entities and relevant context.
3. Planner expands downstream impact and required upstream prerequisites.
4. Policy engine identifies unsupported assets, cycles, missing owners, and destructive operations.
5. Agent produces a recovery DAG with evidence for every edge and action.
6. User reviews risk, estimated duration, and validation plan.
7. User approves execution.
8. Orchestrator runs idempotent adapters in topological waves.
9. Validator checks schema, row counts, freshness, checksums, and selected business assertions.
10. Agent records status, evidence, timestamps, and a human-readable incident summary in DataHub using supported write APIs.

## Functional requirements

### Graph discovery

- Resolve selected DataHub URNs.
- Traverse upstream prerequisites and downstream consumers with bounded depth.
- Fetch schema, platform, owner, domain, tags, glossary terms, assertions, and relevant status where available.
- Preserve the DataHub evidence behind every inferred dependency.
- Detect cycles and unresolved external dependencies.

### Plan compilation

- Produce a typed JSON recovery plan with a stable schema.
- Topologically order steps and group safe parallel steps.
- Attach an adapter, preconditions, validation checks, timeout, retry policy, rollback notes, owner, and risk level to each step.
- Refuse automatic execution when no supported adapter exists.
- Make the plan reproducible from a DataHub graph snapshot identifier or captured manifest.

### Execution

- Implement at least three real local adapters, for example:
  - restore a DuckDB or PostgreSQL table from a snapshot;
  - rerun a SQL transformation;
  - rebuild a toy model or derived artifact.
- Expose dry-run, approve, execute, retry, resume, and abort.
- Use idempotency keys per plan and step.
- Do not execute high-risk actions without explicit approval.

### Verification and writeback

- Check that restored artifacts exist and meet declared schema.
- Run row-count, checksum/freshness, and business-rule validations.
- Mark a consumer ready only when required prerequisites pass.
- Write supported status, structured properties, tags, notes, incidents, or other appropriate metadata to DataHub.
- Do not invent unsupported DataHub entity types; document the supported API/aspect used.
- Export a JSON and Markdown recovery report in `examples/`.

## Suggested architecture

```text
Web UI
  -> API / job controller
      -> DataHub context adapter (MCP or Agent Context Kit for reads)
      -> graph snapshot + recovery compiler
      -> deterministic policy and approval engine
      -> execution adapter registry
      -> verification engine
      -> DataHub writeback adapter (supported SDK/API)
      -> local evidence store
```

Suggested implementation stack:

- Python 3.12, FastAPI, Pydantic, NetworkX, pytest.
- React, TypeScript, Vite, and a graph visualization library.
- SQLite for local job/evidence state.
- DuckDB or PostgreSQL plus local transformation scripts for executable fixtures.
- Docker Compose for repeatable setup.
- An optional LLM adapter for plan explanation and runbook drafting; deterministic fallback for the demo.

The builder may change this stack after recording the reason in `docs/DECISIONS.md`.

## Core data contracts

### Recovery request

- request ID
- incident type
- unavailable platforms or asset URNs
- target recovery point
- maximum blast-radius depth
- risk mode
- requester identity

### Recovery step

- stable step ID
- target URN
- dependency step IDs
- adapter and typed parameters
- preconditions
- validations
- risk and required approval
- state and timestamps
- retry and idempotency data
- evidence references

### Recovery report

- graph snapshot
- discovered impact
- selected and excluded assets with reasons
- plan and execution timeline
- validation evidence
- failures or manual gaps
- DataHub writeback receipts

## Safety model

- Default to dry-run.
- Require approval for any destructive or external action.
- Allow real execution only against targets explicitly marked as demo/sandbox.
- Redact credentials and secrets from prompts, logs, reports, and UI.
- Fail closed on graph cycles, missing required prerequisites, stale plan versions, or unsupported adapters.
- Separate “simulated,” “executed,” and “verified” states.

## Must-have scope

- One ingested DataHub demo graph.
- One outage type with at least five affected assets across three artifact types.
- Real DataHub context retrieval.
- Deterministic recovery DAG and visualization.
- Approval gate.
- Three real local execution adapters.
- Verification and resumable execution.
- Real DataHub writeback.
- Automated tests and reproducible setup.

## Stretch scope

- Natural-language incident intake.
- Alternative recovery plans optimized for speed versus safety.
- Critical-path duration estimates.
- Human escalation to owners discovered from DataHub.
- Export to Airflow, Dagster, or Prefect.
- A reusable DataHub Skill or documentation contribution.

## Out of scope for the MVP

- Real multi-region cloud failover.
- Supporting every DataHub entity or storage platform.
- Fully autonomous destructive production actions.
- Claiming recovery-point or recovery-time guarantees.

## Acceptance criteria

- [ ] A clean setup creates the demo stack and ingests its graph into DataHub.
- [ ] The outage selection produces the correct affected subgraph.
- [ ] The plan is a valid DAG and never schedules a child before a required parent.
- [ ] A cycle or missing adapter produces a clear safe failure.
- [ ] Approval is required before execution.
- [ ] At least three local adapters genuinely execute.
- [ ] A failed step can retry or resume without corrupting completed work.
- [ ] Every completed step has validation evidence.
- [ ] At least one supported write is visible in DataHub after the run.
- [ ] Tests cover planning, safety, execution, verification, and writeback contracts.

## Competitive positioning

Closest alternatives replicate a particular platform or provide static runbooks. Lineage Lifeboat's defensible claim is narrower and stronger:

> It compiles the current, cross-platform DataHub lineage graph into an executable and verified recovery program.

Do not claim that backup or disaster-recovery tools do not exist. Claim that dependency-aware cross-platform recovery compilation and evidence writeback are the differentiators.
