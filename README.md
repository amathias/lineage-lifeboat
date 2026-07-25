# Lineage Lifeboat

## Submission title

**Lineage Lifeboat: Dependency-Aware Disaster Recovery with DataHub**

## Tagline

Turn the data lineage graph into an executable, dependency-correct recovery plan.

## One-sentence pitch

Lineage Lifeboat uses DataHub's context graph to generate, execute, verify, and document recovery plans across an organization's data stack after an outage or regional failure.

## Basic idea

Traditional disaster-recovery products replicate infrastructure or restore individual systems. They do not understand that a warehouse table must recover before a transformation, feature set, model, API, and executive dashboard can safely return to service.

Lineage Lifeboat reads schemas, ownership, health signals, platforms, and end-to-end lineage from DataHub. An agent converts that context into a topologically ordered recovery DAG, performs preflight checks, requests approval for risky actions, executes recovery adapters, validates every recovered asset, and writes the outcome back to DataHub.

## Why it can win

- **Meaningful DataHub usage:** DataHub is the dependency map, policy context, operational memory, and place where recovery results are recorded.
- **Obvious real-world value:** Large data estates have runbooks but rarely have dependency-aware, cross-platform recovery orchestration.
- **Strong live demo:** Trigger an outage, watch the blast radius appear, execute the generated recovery plan, then watch assets turn healthy in dependency order.
- **Measurable result:** Recovery-plan coverage, execution success, validation success, recovery time, and stale-runbook steps avoided.
- **Original positioning:** This is a recovery compiler, not another backup dashboard.

## Primary user

Data platform engineers, site-reliability engineers, analytics engineering leads, and incident commanders.

## Challenge category

Primary: **Agents That Do Real Work**  
Secondary: **Open / Wildcard**

## The memorable demo moment

A simulated warehouse-region outage disables six connected assets. Lineage Lifeboat discovers the complete impact graph, refuses to recover a model before its features, runs the correct dependency-ordered plan, validates the results, and writes a signed recovery report back to DataHub.

## Name rationale

“Lineage Lifeboat” is memorable, directly evokes recovery, and avoids sounding like an official DataHub product. The subtitle supplies the searchable, judge-friendly explanation.

## Workspace map

- [Project brief](./PROJECT_BRIEF.md)
- [Build plan](./BUILD_PLAN.md)
- [Demo and submission](./DEMO_AND_SUBMISSION.md)
- [Hackathon rules](./HACKATHON_RULES.md)
- [AI builder instructions](./AGENTS.md)

## First command for the builder

Read `AGENTS.md`, `HACKATHON_RULES.md`, and `PROJECT_BRIEF.md` completely before choosing the implementation stack or writing code.
## Current development workflow

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m lineage_lifeboat.cli seed-local
.\.venv\Scripts\python.exe -m lineage_lifeboat
```

The service listens on the coordinator-assigned internal port `8101` and exposes:

- `GET /api/health` for process liveness.
- `GET /api/readiness` for non-mutating fixture, state, namespace, and DataHub connectivity checks.

The current `seed-local` command creates deterministic local fixture state only and explicitly does
not claim DataHub ingestion. Live DataHub MCP reads and supported writeback remain the next
integration gate.
