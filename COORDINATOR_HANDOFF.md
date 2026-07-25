# Coordinator Handoff: Lineage Lifeboat

## Relationship to the portfolio coordinator

This project chat owns Lineage Lifeboat's product, code, tests, demo, evidence, and submission.
The portfolio coordinator at `../COORDINATOR_PLAN.md` owns the shared DataHub and AWS deployment
contracts.

Before changing a port, public route, shared environment variable, DataHub namespace, deployment
topology, or global reset behavior, submit the proposed change to the coordinator. Do not edit the
live EC2 host from this project chat.

## Fixed project allocation

| Setting | Value |
|---|---|
| Project slug | `lineage-lifeboat` |
| Internal port | `8101` |
| DataHub domain | `Demo / Lineage Lifeboat` |
| Required DataHub tag | `project-lineage-lifeboat` |
| Entity prefix | `lifeboat.` |
| Fixture root | `demo/fixtures/lineage-lifeboat` |
| State root | `/var/lib/datahub-hackathon/lineage-lifeboat` |

## Project-chat obligations

- Build only Lineage Lifeboat business behavior.
- Keep seed, outage, recovery, verification, and reset operations inside this allocation.
- Fail closed if an execution or reset target falls outside the `lifeboat.` namespace.
- Implement `GET /api/health` and `GET /api/readiness`.
- Keep the project independently runnable without the other four submissions.
- Update the milestone handoff below whenever deployment-facing behavior changes.

## Milestone handoff

| Field | Current value |
|---|---|
| Status | `in progress` |
| Milestone | Coordinator contract, namespace isolation, and service probes |
| Verified commit/artifact | Pending local baseline commit; coordinator records exact hash before promotion |
| Build command | `python -m pip install -e ".[dev]"` |
| Test command | `python -m pytest` |
| Seed command | `python -m lineage_lifeboat.cli seed-local` (local fixture only; does not mutate DataHub) |
| Reset command | `python -m lineage_lifeboat.cli reset-local` (removes only two allowlisted local fixture files) |
| Run command | `python -m lineage_lifeboat` |
| Health endpoint | `GET /api/health` verified HTTP 200 on port 8101 |
| Readiness endpoint | `GET /api/readiness` implemented; HTTP 503 until state is seeded and DataHub GMS is reachable |
| Persistent volumes | Deployment: `/var/lib/datahub-hackathon/lineage-lifeboat`; local default: `.data/lineage-lifeboat` |
| Long-running workers | None currently |
| DataHub read | Not yet verified |
| DataHub writeback | Not yet verified |
| Blockers | Shared DataHub deployment and live read/write receipts; use coordinator SSM tunnel when available |
| Evidence produced | 23 passing tests at 87% total coverage; deterministic graph fingerprint and seed receipt; process-level health/readiness smoke result |

## Required environment variables

No secret values belong in this file. `DATAHUB_TOKEN` is supplied only by the deployment secret
store or local environment.

```text
PROJECT_SLUG=lineage-lifeboat
APP_ENV=<development-or-deployment-environment>
APP_HOST=<bind-address>
APP_PORT=8101
APP_PUBLIC_URL=<coordinator-assigned-public-url>
APP_STATE_DIR=/var/lib/datahub-hackathon/lineage-lifeboat
DATAHUB_GMS_URL=<internal-GMS-url>
DATAHUB_MCP_URL=<internal-MCP-url>
DATAHUB_TOKEN=<secret-injected-at-runtime>
DATAHUB_DOMAIN=Demo / Lineage Lifeboat
DATAHUB_PROJECT_TAG=project-lineage-lifeboat
DATAHUB_URN_PREFIX=lifeboat.
DEMO_FIXTURE_ROOT=demo/fixtures/lineage-lifeboat
```

## Current probe behavior

- `health` is a liveness check and does not contact DataHub.
- `readiness` validates the coordinator allocation, parses and namespace-checks the fixture, checks
  local state-directory access, and performs a non-mutating DataHub GMS health request.
- After `seed-local`, every readiness check except DataHub connectivity passes in the current local
  environment.
- The local seed receipt explicitly records `datahub_seeded: false`; it is not evidence of the
  required live DataHub ingestion.

## Resource and deployment notes

- CPU, memory, startup time, and final job duration have not yet been measured.
- The app currently has no migrations and no long-running workers.
- Rollback is not yet assigned because there is no verified deployment artifact.
- Demo concurrency behavior is not yet tested.

## Required deployment handoff format

When requesting deployment, replace all remaining unverified values and include:

1. Exact commit or immutable artifact identifier.
2. Required environment variables without secret values.
3. Build, test, seed, reset, run, and rollback commands.
4. Health/readiness results.
5. DataHub entities, reads, writes, and receipts.
6. Filesystem volumes and disposable paths.
7. Expected CPU, memory, startup time, and job duration.
8. Known limitations and demo concurrency behavior.
