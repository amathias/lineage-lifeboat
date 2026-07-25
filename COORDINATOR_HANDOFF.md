# Coordinator Handoff: Lineage Lifeboat

## Scope and ownership

This project chat owns Lineage Lifeboat product code, tests, demo evidence, and submission behavior. The portfolio coordinator owns shared DataHub, AWS, promotion, secrets, tunnels, and live evidence capture. This milestone did not deploy, access EC2, or modify another workspace.

## Milestone B result

| Field | Value |
|---|---|
| Status | `implementation complete; coordinator promotion and corrected live reset/restore evidence pending` |
| Exact deployment candidate | `f00c48362bcb6d09737c2809f89dea7675682075` |
| Candidate subject | `fix: make DataHub reset fail closed` |
| Superseded live candidate | `12ca7b9a10222a55cd79f24c72fd800ebe0b0d47` |
| Currently deployed baseline | `12ca7b9a10222a55cd79f24c72fd800ebe0b0d47` |
| Local test result | `42 passed` |
| Local coverage | `82% total` |
| Git-archive packaging smoke | `passed: strict UTF-8 README decode, wheel build, isolated install, isolated import` |
| Coordinator live evidence received | `12ca7b9a... slice verified; its reset failed after eight dataset soft deletes` |
| Live deployment performed here | `no` |
| Live DataHub receipt claimed here | `no` |

The candidate implements the smallest guarded real-DataHub slice: supported SDK upserts, MCP entity and complete direct-edge lineage reads, one tag writeback, immediate MCP reread, scrubbed receipts, deterministic namespace-scoped reset, and evidence-gated readiness.
It retains the valid BOM-free UTF-8 README and bounded 100-result MCP lineage request from `12ca7b9a...`. The new reset is compatible with DataHub 1.6.0: it applies `status.removed=true` only to the eight dataset fixtures, retains all three Domain/Tag controls, handles repeated or partial prior reset idempotently, records started/failed/completed reset state truthfully, and invalidates successful slice readiness before its first mutation.

## Exact commands

### Build

Windows workspace:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Deployment/container equivalent:

```bash
python -m pip install -e ".[dev]"
```

Pinned integration packages are `acryl-datahub==1.6.0.15` and `mcp==1.28.1`.

### Full tests

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=lineage_lifeboat --cov-report=term-missing
```

Verified locally on Python 3.13.2: 42 passed, 82% total coverage.

### Clean Git-archive packaging smoke

```powershell
.\.venv\Scripts\python.exe scripts\archive_package_smoke.py --revision f00c48362bcb6d09737c2809f89dea7675682075
```

Verified against the exact immutable candidate: strict UTF-8 README decoding succeeded, setuptools built `lineage_lifeboat-0.1.0-py3-none-any.whl`, pip installed it into a temporary isolated target, and Python imported `lineage_lifeboat` from that target. The script uses `git archive`, not working-tree files.

### Run service

```powershell
.\.venv\Scripts\python.exe -m lineage_lifeboat
```

Container equivalent:

```bash
python -m lineage_lifeboat
```

Internal port remains `8101`.

### Preferred live seed/read/write/reread command

Run after candidate promotion with the coordinator-injected service-account token and live internal GMS/MCP URLs:

```bash
python -m lineage_lifeboat.cli datahub-vertical-slice --run-id coordinator-milestone-b-live-001
```

The command performs, in order:

1. guarded fixture/control upserts and deterministic lineage emission through DataHub `MetadataChangeProposal` APIs;
2. batch `get_entities` and five direct downstream `get_lineage` reads through the DataHub MCP Server;
3. a supported `globalTags` writeback to the canonical revenue entity;
4. an immediate MCP `get_entities` reread that must contain the marker tag;
5. durable scrubbed receipts under `APP_STATE_DIR/datahub-receipts`.

Separate diagnostic commands are also available:

```bash
python -m lineage_lifeboat.cli seed-datahub
python -m lineage_lifeboat.cli read-datahub
python -m lineage_lifeboat.cli writeback-datahub --run-id coordinator-milestone-b-live-001
```

All GMS mutations fail before network access when `DATAHUB_TOKEN` is absent. No command prints or persists the token.

### Reset and restore

Reset emits `status.removed=true` only for the eight canonical dataset fixture URNs. It intentionally retains the exact project Domain and two Tag controls because DataHub 1.6.0 rejects the dataset `status` aspect for those entity types:

```bash
python -m lineage_lifeboat.cli reset-datahub --confirm-project lineage-lifeboat
```

Before the first DataHub mutation, reset replaces `vertical-slice-receipt.json` with a project-bound invalidation tombstone and writes `datahub-reset-receipt.json` with `status=started` and `completed=false`. A mutation failure leaves readiness closed and overwrites the reset receipt with `status=failed`, `partial_mutation_possible=true`, and only the exception type. Success records `status=completed`, `completed=true`, exactly eight soft-deleted asset URNs, and exactly three retained control URNs.

Repeated reset is idempotent. Seed always emits `status.removed=false` for all eight datasets, so rerunning the complete slice recovers a partial or completed prior reset and captures new read/write/reread evidence:

```bash
python -m lineage_lifeboat.cli datahub-vertical-slice --run-id coordinator-milestone-b-restore-001
```

A missing or incorrect confirmation fails closed before receipt invalidation or mutation. Foreign URNs and namespaced-but-nonfixture writeback targets are rejected. No global delete or global reset exists.

## Canonical fixture and namespace

Fixed allocation:

| Setting | Value |
|---|---|
| Project slug | `lineage-lifeboat` |
| DataHub domain | `Demo / Lineage Lifeboat` |
| Required project tag | `project-lineage-lifeboat` |
| Entity name prefix | `lifeboat.` |
| Fixture path | `demo/fixtures/lineage-lifeboat/graph_snapshot.json` |
| Persistent state | `/var/lib/datahub-hackathon/lineage-lifeboat` |

The eight canonical asset URNs are:

```text
urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.raw.orders,PROD)
urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.raw.customers,PROD)
urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.analytics.stg_orders,PROD)
urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.analytics.customer_revenue,PROD)
urn:li:dataset:(urn:li:dataPlatform:featurestore,lifeboat.features.customer_value,PROD)
urn:li:dataset:(urn:li:dataPlatform:mlflow,lifeboat.models.churn_model,PROD)
urn:li:dataset:(urn:li:dataPlatform:looker,lifeboat.dashboards.executive_revenue,PROD)
urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.inventory.forecast,PROD)
```

The ML model and dashboard remain semantically typed through `lifeboat.artifact_type` custom properties but are cataloged as platform-specific datasets so every edge uses DataHub's documented Dataset-to-Dataset lineage contract.

Exact project controls:

```text
urn:li:domain:lifeboat
urn:li:tag:project-lineage-lifeboat
urn:li:tag:lifeboat-recovery-verified
```

Seed emits 48 aspect proposals: status, dataset properties/custom recovery context, required tag, domain, ownership, five grouped upstream-lineage aspects, and the three control definitions. Six deterministic edges are represented.

## Read, writeback, and receipt details

MCP read contract:

- `get_entities` receives all eight fixture URNs in one batch when the advertised schema supports `urns`.
- `get_lineage` is called at one hop with `upstream=false` for each of the five fixture assets that has downstream edges.
- When advertised by the live schema, `max_results` or a compatible result-limit argument is set to a bounded 100, or to a smaller advertised maximum.
- Evidence validation requires every requested entity and every exact upstream/downstream fixture edge to appear in the corresponding MCP results, including both direct consumers of `lifeboat.analytics.customer_revenue`.

Writeback contract:

| Field | Value |
|---|---|
| Supported write API | DataHub RestEmitter `MetadataChangeProposal` |
| Aspect | `globalTags` UPSERT |
| Target | `urn:li:dataset:(urn:li:dataPlatform:duckdb,lifeboat.analytics.customer_revenue,PROD)` |
| Preserved isolation tag | `urn:li:tag:project-lineage-lifeboat` |
| Receipt marker | `urn:li:tag:lifeboat-recovery-verified` |
| Verification | immediate DataHub MCP `get_entities` reread |

Deployment receipt paths:

```text
/var/lib/datahub-hackathon/lineage-lifeboat/datahub-receipts/datahub-seed-receipt.json
/var/lib/datahub-hackathon/lineage-lifeboat/datahub-receipts/context-read-receipt.json
/var/lib/datahub-hackathon/lineage-lifeboat/datahub-receipts/writeback-receipt.json
/var/lib/datahub-hackathon/lineage-lifeboat/datahub-receipts/vertical-slice-receipt.json
/var/lib/datahub-hackathon/lineage-lifeboat/datahub-receipts/datahub-reset-receipt.json
```

Receipts contain the exact MCP tool results and SHA-256 evidence hashes. Before persistence, credential key names and the configured token value are rejected. Generated receipts remain runtime evidence and are ignored by Git.

`vertical-slice-receipt.json` is the readiness authority. Reset overwrites it before mutation with `operation=datahub_vertical_slice_invalidated`, `verified=false`, and `reason=datahub_reset_started`; only a fresh complete vertical slice can replace it with verified evidence. `datahub-reset-receipt.json` independently distinguishes started, failed/possibly partial, and completed reset attempts so an older successful reset receipt cannot survive a newer failure.

## Health and truthful readiness

- `GET /api/health` is liveness only and never claims DataHub readiness.
- Candidate `GET /api/readiness` requires all of: fixed allocation, valid namespaced fixture, readable/writable state directory, GMS health, configured `DATAHUB_TOKEN`, and a vertical-slice receipt bound to the current fixture fingerprint.
- The aggregate receipt must reference the three exact seed/context/writeback files inside the project receipt directory; missing, relocated, stale, or explicitly invalidated evidence fails closed.
- Fresh state returns HTTP 503 until a complete live slice succeeds. Promotion over persistent verified `12ca7b9a...` evidence may initially remain 200 because the fixture and proof contract are unchanged.
- As soon as a confirmed reset begins, the candidate invalidates the aggregate success receipt before any GMS mutation. Completed, partial, and failed resets therefore hold readiness at HTTP 503 until a fresh complete live slice succeeds.
- The deployed `12ca7b9a...` baseline exposed the stale-evidence defect by remaining HTTP 200 after all eight datasets had been soft-deleted and the reset then failed on the Domain control. This candidate closes that exact gap.

## Environment contract

No values for secrets belong in Git or this handoff.

```text
PROJECT_SLUG=lineage-lifeboat
APP_ENV=<deployment-environment>
APP_HOST=<bind-address>
APP_PORT=8101
APP_PUBLIC_URL=https://lifeboat.datahub-hackathon.aaronmathias.com
APP_STATE_DIR=/var/lib/datahub-hackathon/lineage-lifeboat
DATAHUB_GMS_URL=<coordinator live internal GMS URL>
DATAHUB_MCP_URL=<coordinator live internal MCP URL ending in /mcp>
DATAHUB_TOKEN=<AWS SecureString injected at runtime>
DATAHUB_DOMAIN=Demo / Lineage Lifeboat
DATAHUB_PROJECT_TAG=project-lineage-lifeboat
DATAHUB_URN_PREFIX=lifeboat.
DEMO_FIXTURE_ROOT=demo/fixtures/lineage-lifeboat
```

Local tunnel defaults remain canonical:

```text
DATAHUB_GMS_URL=http://127.0.0.1:8080
DATAHUB_MCP_URL=http://127.0.0.1:8000/mcp
```

## Resource and operations notes

- Local Windows cold smoke: health HTTP 200 in approximately 9.9 seconds; listener working set approximately 62.6 MiB.
- Candidate readiness returned HTTP 503 locally because live token/evidence were intentionally absent.
- No migrations, queues, schedulers, or long-running workers were added.
- The DataHub vertical-slice command is a finite foreground job; live duration and peak memory must be captured by the coordinator after promotion.
- Seed and writeback use idempotent aspect UPSERTs. Reset uses reversible `status.removed=true` only for the eight datasets, retains the three controls, and rerunning the vertical slice restores `status.removed=false` for every dataset.
- Run only one evidence-producing vertical slice at a time because receipt filenames are intentionally stable; concurrent runs could overwrite each other's local receipt files even though DataHub aspect writes are idempotent.
- Persistent data is limited to the assigned project state root. No shared/global reset is implemented.

## Remaining live evidence and blockers

There is no known local implementation, test, or packaging blocker. Coordinator-provided live evidence for deployed `12ca7b9a10222a55cd79f24c72fd800ebe0b0d47` is:

- the full vertical slice succeeded: all MCP entity/lineage reads, supported `globalTags` writeback, immediate reread, aggregate receipt, and readiness HTTP 200;
- confirmed reset successfully soft-deleted all eight dataset fixtures, then GMS returned HTTP 422 `Unknown aspect status for entity domain` on `urn:li:domain:lifeboat`;
- the failed reset produced no successful reset receipt, but readiness incorrectly remained HTTP 200 against the older verified slice receipt;
- no global deletion occurred, and the coordinator began a project-scoped reseed/restore. This handoff does not claim the outcome of that coordinator-owned restore.

Coordinator-owned live work remains:

1. promote exact candidate `f00c48362bcb6d09737c2809f89dea7675682075`;
2. run the confirmed reset and verify readiness becomes HTTP 503 before the first GMS proposal;
3. verify `datahub-reset-receipt.json` records `status=completed`, `completed=true`, eight soft-deleted dataset URNs, and three retained controls, with no control `status` proposal;
4. verify the Domain and Tags remain and no foreign/global entity was changed;
5. rerun the guarded vertical slice with a new run ID, confirm all eight datasets are restored, and capture new MCP read/write/reread evidence plus readiness HTTP 200;
6. retain both reset and restore receipts/screenshots for the judge evidence bundle.

The local workstation still has no `DATAHUB_TOKEN`, no AWS Session Manager plugin, and no listeners on ports 8080/8000. Per coordinator direction, this chat did not install the plugin, request a token, access EC2/AWS, or deploy. Those local conditions do not invalidate the clean candidate; they explain why no new live receipt is claimed here.

## Promotion and rollback

- Promote: exact candidate `f00c48362bcb6d09737c2809f89dea7675682075`.
- Roll back application code/image: currently deployed candidate `12ca7b9a10222a55cd79f24c72fd800ebe0b0d47`.
- DataHub fixture rollback: use the confirmed `reset-datahub` command from candidate `f00c48362bcb6d09737c2809f89dea7675682075`; do not use the reset implementation from `12ca7b9a...`, and never use a global DataHub reset.
