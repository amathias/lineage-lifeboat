# Coordinator Handoff: Lineage Lifeboat

## Scope and ownership

This project chat owns Lineage Lifeboat product code, tests, demo evidence, and submission behavior. The portfolio coordinator owns shared DataHub, AWS, promotion, secrets, tunnels, and live evidence capture. This milestone did not deploy, access EC2, or modify another workspace.

## Milestone B result

| Field | Value |
|---|---|
| Status | `Milestone B complete; corrected live reset/restore/concurrency gate passed` |
| Exact deployment candidate | `f00c48362bcb6d09737c2809f89dea7675682075` |
| Candidate subject | `fix: make DataHub reset fail closed` |
| Superseded live candidate | `12ca7b9a10222a55cd79f24c72fd800ebe0b0d47` |
| Currently deployed candidate | `f00c48362bcb6d09737c2809f89dea7675682075` |
| Local test result | `42 passed` |
| Local coverage | `82% total` |
| Git-archive packaging smoke | `passed: strict UTF-8 README decode, wheel build, isolated install, isolated import` |
| Coordinator live evidence received | `reset, fail-closed readiness, restore, writeback, isolation, and two-demo concurrency passed` |
| Post-evidence snapshot | `snap-06d2125eaa1106558 mounted read-only; current aggregate receipt hash matched` |
| Live deployment performed here | `no` |
| Evidence ownership | `coordinator-captured hashes recorded below; no secret values included` |

The deployed candidate implements the smallest guarded real-DataHub slice: supported SDK upserts, MCP entity and complete direct-edge lineage reads, one tag writeback, immediate MCP reread, scrubbed receipts, deterministic namespace-scoped reset, and evidence-gated readiness.
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
python -m lineage_lifeboat.cli datahub-vertical-slice --run-id coordinator-milestone-b-restore-003
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

### Coordinator-owned live evidence hashes

Corrected reset:

| Artifact | SHA-256 |
|---|---|
| Completed reset receipt | `0d6d92b2ccafa60daa2bc54e0d56b041d942cb9584e95f3f1c55abe3f750bf` |
| Readiness invalidation tombstone | `e59057d2e0ae23d61fb59be7b3add8d9541689a3773d38a86fff5723f47bbc` |

Successful idempotent restore `coordinator-milestone-b-restore-003`:

| Artifact | SHA-256 |
|---|---|
| Seed receipt | `10598b32591b4b74ba3326d12271c4a6d7b527e7def31999e16f4a975a3c6e25` |
| Context receipt | `4eadde7c42688e4bf53015e1cdffcc91da324c51dd99eb1538efeaa7f3f0f261` |
| Writeback receipt | `39fdc50a77496fd6a759341a76a88f2c0a4ba36a7c965341945311b226cee684` |
| Aggregate receipt | `5eaf115b4064ee4c95db652779e4b8b3664c3960c165c5a856bb4a717d3769b1` |

Later two-demo concurrency run `coordinator-concurrency-live-002`:

| Artifact | SHA-256 |
|---|---|
| Seed receipt | `faafefe45ad14412f6e6af3381339395a58bf4880c26b92286d4f7c9bd63f89d` |
| Context receipt | `525a645fff707cd41107e386e3aad913c9207ab5dd46cf71fa4b625215ca8dd8` |
| Writeback receipt | `7b1ada1879cbd62eab71a9fa4cd1f3cb8c434f235622ece3c129af14b3defc70` |
| Aggregate receipt | `63d3e5f7245c9d1da9e239caf5321df8dcd6e95163f3685884557856ef461ba6` |

The post-evidence snapshot `snap-06d2125eaa1106558` was mounted read-only and its aggregate receipt SHA-256 matched `63d3e5f7...` exactly.

## Health and truthful readiness

- `GET /api/health` is liveness only and never claims DataHub readiness.
- Candidate `GET /api/readiness` requires all of: fixed allocation, valid namespaced fixture, readable/writable state directory, GMS health, configured `DATAHUB_TOKEN`, and a vertical-slice receipt bound to the current fixture fingerprint.
- The aggregate receipt must reference the three exact seed/context/writeback files inside the project receipt directory; missing, relocated, stale, or explicitly invalidated evidence fails closed.
- Fresh state returns HTTP 503 until a complete live slice succeeds.
- As soon as a confirmed reset begins, the candidate invalidates the aggregate success receipt before any GMS mutation. Completed, partial, and failed resets therefore hold readiness at HTTP 503 until a fresh complete live slice succeeds.
- The corrected live gate proved readiness changed HTTP 200 to 503 after the reset tombstone, then returned to 200 only after the successful fresh restore slice.

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
- The first immediate restore attempt failed closed before writeback on one transiently missing dashboard lineage edge after status restoration. Idempotent retry `coordinator-milestone-b-restore-003` succeeded after indexing settled; allow an index-settle retry in operations without weakening lineage validation.
- Run only one Lifeboat evidence-producing vertical slice at a time because its receipt filenames are intentionally stable. Cross-demo concurrency is safe through separate namespaces and state roots: `coordinator-concurrency-live-002` succeeded in parallel with Forget-Me-Graph.
- Persistent data is limited to the assigned project state root. No shared/global reset is implemented.

## Live gate closeout and remaining milestone

Milestone B is closed for exact deployed candidate `f00c48362bcb6d09737c2809f89dea7675682075`:

- reset completed with exactly eight dataset soft deletes and all three controls retained unchanged;
- readiness changed from HTTP 200 to 503 with the explicit tombstone;
- all 105 Forget-Me-Graph aspect rows were byte-for-byte unchanged by reset and remained unchanged through restore;
- all six Lifeboat Domain/Tag aspect rows were retained unchanged;
- the first immediate restore attempt failed closed before writeback on transient MCP index lag;
- retry `coordinator-milestone-b-restore-003` restored all eight datasets, verified every required MCP lineage edge, completed supported `globalTags` writeback/reread, and returned readiness to HTTP 200;
- `coordinator-concurrency-live-002` later succeeded alongside Forget-Me-Graph, and the read-only post-evidence snapshot reproduced the final aggregate receipt hash exactly.

There is no remaining shared-DataHub blocker. The remaining project milestone is the judge-facing executable recovery workflow:

1. build the disposable local outage/recovery estate and at least three real idempotent adapters;
2. connect live DataHub-derived context to the deterministic recovery planner;
3. add explicit approval, execution retry/resume, validation gates, and retained step evidence;
4. export judge-ready JSON/Markdown plan and report examples;
5. complete the incident/graph/plan/approval/execution/report UI and rehearse the under-three-minute demo.

This documentation-only update did not change product code, deploy, access AWS/EC2, open tunnels, or handle a token.

## Promotion and rollback

- Current deployed application code/image: exact candidate `f00c48362bcb6d09737c2809f89dea7675682075`; no Milestone B promotion remains pending.
- Roll back application code/image only if necessary: previous candidate `12ca7b9a10222a55cd79f24c72fd800ebe0b0d47`.
- DataHub fixture rollback: use the confirmed `reset-datahub` command from candidate `f00c48362bcb6d09737c2809f89dea7675682075`; do not use the reset implementation from `12ca7b9a...`, and never use a global DataHub reset.
