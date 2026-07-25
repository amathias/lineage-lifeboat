# Build Plan: Lineage Lifeboat

## Delivery strategy

Build one reliable vertical slice before improving visual polish or adding platforms. The critical proof is:

> A DataHub-derived graph changes the executable recovery order, the local actions really run, validation gates downstream readiness, and results return to DataHub.

## Recommended repository shape

```text
/
  app/                  # Python API and domain services
  web/                  # React UI
  adapters/             # DataHub, recovery, and validation adapters
  demo/                 # synthetic stack, ingestion, outage/reset scripts
  examples/             # generated plans and reports
  tests/
  docs/
  docker-compose.yml
  .env.example
  LICENSE
  README.md
```

Do not create empty architecture folders far ahead of working code.

## Phase 0: Prove DataHub connectivity

- Start a pinned, supported open-source DataHub version.
- Ingest a two-node lineage fixture.
- Read it through the DataHub MCP Server or Agent Context Kit.
- Perform one harmless supported metadata write and verify it in DataHub.
- Record exact versions and commands.

Exit condition: a single integration test proves both context retrieval and writeback.

## Phase 1: Build the recovery domain

- Define Pydantic schemas for request, graph snapshot, step, plan, approval, evidence, and report.
- Build a deterministic in-memory graph planner.
- Implement topological ordering, parallel waves, cycle detection, and missing-adapter errors.
- Unit-test all graph behavior without DataHub or an LLM.

Exit condition: a fixed graph compiles to the expected plan and unsafe graphs fail.

## Phase 2: Create the executable demo estate

- Build source, transformation, feature, model, and dashboard/report fixtures.
- Add snapshot/reset scripts.
- Implement at least three adapters with idempotency.
- Add validation checks for existence, schema, counts/checksums, freshness, and one business rule.
- Ensure a failed validation blocks its consumers.

Exit condition: a CLI command can break, recover, verify, and reset the local estate.

## Phase 3: Integrate DataHub context

- Ingest the full demo estate with lineage, schemas, owners, assertions, and sandbox markers.
- Implement a DataHub context adapter behind an interface.
- Capture a stable graph fingerprint or manifest with the plan.
- Make plan construction depend on live DataHub graph results.
- Add contract tests with saved fixtures and one live integration test.

Exit condition: changing lineage in DataHub changes recovery ordering or impact.

## Phase 4: Add agent behavior and safety

- Add optional natural-language incident intake and plan explanation.
- Require structured model output validated against schemas.
- Add dry-run and explicit approval.
- Add policy gates for destructive actions, stale snapshots, cycles, unsupported targets, and excessive blast radius.
- Ensure deterministic planning remains functional without the LLM.

Exit condition: bad or malformed model output cannot trigger execution.

## Phase 5: Build the judge-facing UI

Required screens:

1. Incident selection.
2. DataHub impact graph.
3. Recovery plan with dependency waves and risk.
4. Approval control.
5. Live execution and validation timeline.
6. Final report with DataHub writeback receipt.

Prioritize a single-screen story if time is limited.

Exit condition: the complete demo can be performed without using a terminal after setup.

## Phase 6: Submission hardening

- Add one-command or minimal-command startup.
- Add `examples/recovery-plan.json` and `examples/recovery-report.md`.
- Test from a clean checkout.
- Run unit, integration, and end-to-end demo tests.
- Add screenshots, architecture diagram, limitations, and threat/safety notes.
- Add Apache 2.0 `LICENSE` and configure the public repository About section.
- Record a demo under 2:45 to leave margin.

## Test plan

### Unit

- DAG ordering and parallel waves.
- Cycle and missing dependency behavior.
- Adapter selection.
- Approval and policy gates.
- Idempotency and retry transitions.
- Validation aggregation.

### Integration

- DataHub read and supported write.
- Snapshot, outage, recovery, and reset.
- Adapter failure followed by resume.
- Stale graph fingerprint rejection.

### End to end

- Seed DataHub.
- Trigger outage.
- Generate and approve plan.
- Execute recovery.
- Verify all expected assets.
- Confirm writeback and report.

## Scope cuts if behind

Cut in this order:

1. Natural-language intake.
2. Multiple optimization modes.
3. Real orchestration-framework export.
4. More than three adapters.
5. Authentication beyond a clear demo role.

Never cut DataHub writeback, real execution, verification, safety gates, or clean setup.

## Evidence to preserve

- Exact DataHub MCP/Agent Context Kit requests or tool traces.
- Before/after graph and health screenshots.
- Generated recovery plan.
- Execution receipts.
- Validation output.
- DataHub writeback screenshot and receipt.
- Test summary.

## Final engineering checklist

- [ ] Pinned dependency versions.
- [ ] No committed secrets.
- [ ] `.env.example` exists.
- [ ] Demo reset is reliable and non-destructive outside fixtures.
- [ ] Every action is labeled simulated, executed, or verified.
- [ ] CI runs core tests.
- [ ] Clean-checkout instructions are timed and tested.
- [ ] README maps features directly to judging criteria.
