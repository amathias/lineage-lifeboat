# Coordinator Handoff: Lineage Lifeboat

## 2026-07-29 anonymous mutation hardening — deployed and verified

- The published project slug is no longer an HTTP confirmation token.
- Hosted mutations now require short-lived, cryptographically random, one-time confirmations
  bound to the requesting client and exact operation.
- All hosted mutation routes share a process-local single-flight guard, one-second cooldown, and
  per-client/global sliding-window limits, with `429` and `Retry-After` on capacity rejection.
- CLI confirmation and approval semantics are unchanged. The controls protect the public judge
  surface without claiming to provide user authentication.
- Verification: 61 tests passed with the documented `D:\pt` Windows ACL workaround; Ruff,
  JavaScript syntax, and whitespace checks passed.
- Exact commit `76ecbe049efaa87516bbfa97fa663abc0897d333` passed GitHub Actions and was
  promoted by the coordinator.
- Public root, health, and strong readiness returned 200 after deployment and token refresh.
  A mutation without a fresh confirmation returned 403. Shared response headers and the 64 KiB
  proxy body limit were also verified from the public route.

## 2026-07-29 public-demo boundary closeout

| Field | Verified value |
|---|---|
| Exact deployed product | `1831d5ab86ba2c1278bc9dd12843c157d4afe84d` |
| Public endpoint | `https://lifeboat.datahub-hackathon.aaronmathias.com` |
| Public acceptance | Root, health, and strong readiness returned 200 |
| Browser acceptance | One prominent `PUBLIC DEMO` notice rendered above the workflow and identified the disposable estate, `lifeboat.*` allocation, no-production/no-personal-data boundary, and source/API/self-hosting link |
| Hosted API documentation | `/api/docs`, `/api/redoc`, and `/api/openapi.json` returned 404 in `APP_ENV=hackathon`; local/development/test documentation remains enabled |
| Verification | 57 tests passed, Ruff passed, GitHub Actions passed, exact `main` matched `origin/main` before promotion |

This release changes presentation and public attack surface only. It does not replace or broaden
the coordinator-owned live DataHub evidence below. The deployment seed was the documented local
disposable-estate seed (`datahub_seeded=false`); no shared DataHub fixture was reseeded.

## Scope and ownership

This project chat owns Lineage Lifeboat product code, tests, demo evidence, and submission behavior. The portfolio coordinator owns shared DataHub, AWS, promotion, secrets, tunnels, and live evidence capture. This milestone did not deploy, access EC2, or modify another workspace.

## 2026-07-27 release hardening

| Field | Value |
|---|---|
| Exact product candidate | `b1e89a518810ffb12eaad09b1fd15d2e7e9e87fc` |
| Deployed candidate | unchanged: `a304df864a9eedff91862d0d4642484f0ab89984` |
| Safety correction | dataset namespace validation now parses the DataHub dataset URN structurally and checks the dataset-name position; prefixes hidden in the platform, environment, or a foreign name fail closed |
| Judge entrypoint | live/source/public-video/runbook links, three-step journey, and Mermaid architecture are at the top of `README.md` |
| Continuous integration | `.github/workflows/ci.yml` runs Ruff plus the full test/coverage suite on pushes, pull requests, and manual dispatch |
| Verification | 56 tests passed; 85% coverage; Ruff clean |
| Exact-commit archive | strict UTF-8 README decode, wheel build, isolated install, and isolated import passed |
| Wheel SHA-256 | `b1bb9c6c652c7892674488c00ca649ec5e29a65d1579a6329d6bbd95ff3bd4fe` |
| Cloud/live activity | none; no AWS, EC2, token, DataHub mutation, or deployment |

This candidate is a fail-closed local safety and release-presentation improvement. It does not
invalidate or replace the coordinator-owned live evidence for the currently deployed candidate.
Promotion, if desired, remains a separate coordinator decision.

## Milestone C immutable-evidence live closeout

| Field | Value |
|---|---|
| Current deployed candidate | `a304df864a9eedff91862d0d4642484f0ab89984` |
| Deployment confirmation | coordinator confirmed `/etc/datahub-hackathon/app-versions.env` |
| Previous deployment / rollback | `c92488300023fc65660499b3406fd2e4db76fcbc` |
| Public endpoint checks | pre/post health, readiness, and page all HTTP 200 |
| Approved recovery runs | `coordinator-immutable-live-a-001`, `coordinator-immutable-live-b-001` |
| Per-run execution | `6/6 steps; context=verified_live_datahub_mcp; DataHub=verified` |
| Run A receipt SHA-256 | `c8039e899970ed3189eb0bd8537523b8858ef33528915d0a41f53dfa214a61b1` |
| Run A ledger SHA-256 | `8556bdced2c0189c42a9acc9b2eae6cc6c5bddb1abfef3196b960be398683bb1` |
| Run B receipt SHA-256 | `6d11b0d7f98c96e5b0f39fa986eab5058ffbb4cee22fc798b20aa01d6d75318d` |
| Run B ledger SHA-256 | `fea69f4ad304e6760041fe5712106619d4b6bd7f53dbee4d18b415a1fdec5715` |
| Stable writeback component | unchanged: `5d1141e5022d5d3de15eb17e0104a5482b0f70eb9a1325b2b03b6bbb600432be` |
| Stable vertical-slice aggregate | unchanged: `63d3e5f7245c9d1da9e239caf5321df8dcd6e95163f3685884557856ef461ba6` |
| Archived sanitized evidence | `s3://datahub-agent-hackathon-artifacts-499817841945-us-east-1/evidence/2026-07-25/lifeboat-immutable-live-001/` (10 objects) |
| Archive `SHA256SUMS` SHA-256 | `38aebf1c350efd83d9e0c8387771926d9b144834f4aae13fb00d329bbfa335bc` |

After run B, the coordinator rehashed run A's immutable receipt and ledger; both remained byte-for-byte unchanged. Per-run immutable path count checks passed. The stable Milestone B writeback component and vertical-slice aggregate also remained unchanged, proving judge recovery runs no longer replace readiness-authoritative evidence.

This chat received these coordinator-owned results only. It did not access AWS, inspect the host, deploy, rerun tests, or handle secrets.

## Milestone B result

| Field | Value |
|---|---|
| Status | `Milestone B complete; corrected live reset/restore/concurrency gate passed` |
| Exact deployment candidate | `f00c48362bcb6d09737c2809f89dea7675682075` |
| Candidate subject | `fix: make DataHub reset fail closed` |
| Superseded live candidate | `12ca7b9a10222a55cd79f24c72fd800ebe0b0d47` |
| Milestone B deployed candidate at closeout | `f00c48362bcb6d09737c2809f89dea7675682075` |
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

Immutable-evidence live closeout on deployed `a304df8...`:

| Evidence | Path | SHA-256 |
|---|---|---|
| Run A writeback receipt | `/var/lib/datahub-hackathon/lineagelifeboat/recovery-runs/coordinator-immutable-live-a-001/datahub-writeback-receipt.json` | `c8039e899970ed3189eb0bd8537523b8858ef33528915d0a41f53dfa214a61b1` |
| Run A ledger | `/var/lib/datahub-hackathon/lineagelifeboat/recovery-runs/coordinator-immutable-live-a-001/run.json` | `8556bdced2c0189c42a9acc9b2eae6cc6c5bddb1abfef3196b960be398683bb1` |
| Run B writeback receipt | `/var/lib/datahub-hackathon/lineagelifeboat/recovery-runs/coordinator-immutable-live-b-001/datahub-writeback-receipt.json` | `6d11b0d7f98c96e5b0f39fa986eab5058ffbb4cee22fc798b20aa01d6d75318d` |
| Run B ledger | `/var/lib/datahub-hackathon/lineagelifeboat/recovery-runs/coordinator-immutable-live-b-001/run.json` | `fea69f4ad304e6760041fe5712106619d4b6bd7f53dbee4d18b415a1fdec5715` |

Both approved public runs completed 6/6 steps with `context_evidence.mode=verified_live_datahub_mcp` and `datahub_outcome.status=verified`. After run B, both run A hashes matched their pre-run-B values. The stable component and aggregate hashes remained `5d1141e5...` and `63d3e5f7...` respectively. Immutable path count checks passed.

Historical Milestone C recovery `coordinator-milestone-c-live-001` on deployed `c924883...`:

| Artifact | SHA-256 |
|---|---|
| Verified recovery writeback receipt | `5d1141e5022d5d3de15eb17e0104a5482b0f70eb9a1325b2b03b6bbb600432be` |

The run completed 6/6 recovery steps, recorded `datahub_outcome.status=verified`, and left readiness at HTTP 200.

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

## Live gate closeout

Milestone B remains closed for exact deployed candidate `f00c48362bcb6d09737c2809f89dea7675682075`:

- reset completed with exactly eight dataset soft deletes and all three controls retained unchanged;
- readiness changed from HTTP 200 to 503 with the explicit tombstone;
- all 105 Forget-Me-Graph aspect rows were byte-for-byte unchanged by reset and remained unchanged through restore;
- all six Lifeboat Domain/Tag aspect rows were retained unchanged;
- the first immediate restore attempt failed closed before writeback on transient MCP index lag;
- retry `coordinator-milestone-b-restore-003` restored all eight datasets, verified every required MCP lineage edge, completed supported `globalTags` writeback/reread, and returned readiness to HTTP 200;
- `coordinator-concurrency-live-002` later succeeded alongside Forget-Me-Graph, and the read-only post-evidence snapshot reproduced the final aggregate receipt hash exactly.

Exact immutable-evidence candidate `a304df864a9eedff91862d0d4642484f0ab89984` is now deployed and independently passed the two-run public live gate recorded above. All earlier Milestone B and Milestone C receipts and hashes remain authoritative. Exact candidate `c92488300023fc65660499b3406fd2e4db76fcbc` is retained only as the application rollback target.

### Judge workflow delivered

- A confirmed disposable outage removes only six recovery targets from a project-scoped DuckDB/file estate. `raw.customers` remains a healthy prerequisite and the unrelated `inventory.forecast` branch remains present and excluded.
- The existing deterministic compiler produces six steps in five dependency waves, bound to the unchanged fixture fingerprint `72accff2049653af2a7134d41559d3bb0e8ad9a27edefe2ed986155b85dc524b`.
- Execution is disabled until an incident commander approves the exact persisted `plan_id`; mismatched and absent approvals fail closed.
- Four real local adapter families execute: Parquet snapshot restore, DuckDB SQL transforms, deterministic Python feature/model builds, and a report refresh.
- Required existence, schema, row-count, checksum, business-rule, freshness, artifact-load, metric-threshold, and input-fingerprint validations block consumers on failure.
- The file-backed run ledger persists before and after every step. Resume reuses stable idempotency keys and skips steps already marked verified.
- A no-build single-page recovery console is served at `/`; CLI and JSON APIs expose the same initialize, outage, plan, approval, execute/resume, state, and report flow.
- Deterministic judge examples are committed under `examples/`, and `docs/DEMO_RUNBOOK.md` gives a timed 2:35 recording path.

DataHub behavior remains truthful:

- when the current project state contains a verified live vertical-slice receipt for the exact graph fingerprint, new recovery plans record `context_evidence.mode=verified_live_datahub_mcp` and bind the receipt path/hash;
- otherwise local runs clearly record `captured_datahub_fixture` and do not claim a fresh live read;
- after all local steps verify, a configured live run uses the existing supported `globalTags` UPSERT plus immediate MCP reread and attaches the resulting receipt hash;
- with no `DATAHUB_TOKEN`, the local workflow stays runnable and records `datahub_outcome.status=not_configured`; no write is claimed.

### Exact local commands

```powershell
python -m pip install -e ".[dev]"
python scripts/generate_demo_snapshot.py
python scripts/generate_examples.py
python -m lineage_lifeboat.cli demo-run --run-id judge-demo-001 --approved-by demo-incident-commander --confirm-project lineage-lifeboat
python -m lineage_lifeboat
```

Open `http://127.0.0.1:8101/` for the judge console. The separate approval/resume CLI path is:

```powershell
python -m lineage_lifeboat.cli demo-initialize --confirm-project lineage-lifeboat
python -m lineage_lifeboat.cli demo-outage --confirm-project lineage-lifeboat
python -m lineage_lifeboat.cli demo-plan --run-id judge-demo-001
python -m lineage_lifeboat.cli demo-approve --run-id judge-demo-001 --plan-id <plan-id-from-previous-command> --approved-by demo-incident-commander
python -m lineage_lifeboat.cli demo-execute --run-id judge-demo-001
```

Verification commands and exact results for successor `a304df864a9eedff91862d0d4642484f0ab89984`:

```powershell
ruff check app tests scripts
python -m compileall -q app scripts
python -m pytest --cov=lineage_lifeboat --cov-report=term-missing
python scripts/verify_judge_demo.py
```

- Ruff: passed.
- Compileall: passed.
- Pytest: 51 passed in 51.41 seconds; 85% aggregate coverage, including 90% workflow, 94% estate/adapters, and 83% DataHub integration coverage.
- Judge verifier: 6/6 steps verified in 5.12 seconds, below the three-minute ceiling.
- The multi-run regression reloads run A after run B and verifies run A's immutable receipt bytes/path/SHA-256 while the stable vertical-slice record and component bytes remain unchanged.
- Traversal, conflicting immutable bytes, retention failure, and no-token paths all fail closed as specified.
- Exact `git archive a304df8...` packaging smoke: wheel built, installed into an isolated target, and imported from that target successfully.
- Served-page probe: `/` and `/api/demo/state` returned HTTP 200; the ASGI browser-journey regression completes initialization through verified recovery. Screenshot-level in-app browser QA could not run because the host browser runtime twice exited on `windows sandbox helper_unknown_error`; this is a local Codex tooling limitation, not an application failure.

Deterministic committed example hashes:

| Artifact | SHA-256 |
|---|---|
| `examples/recovery-plan.json` | `cbd3c58fb553bb3a3f3d145462152b870535395d4cc335811837727762e34c0a` |
| `examples/recovery-report.json` | `ad9807428bcf171bac45b09532b19001431235a7c91df0311713ba29e5eb589e` |
| `examples/recovery-report.md` | `bf12c075667e5b9ae4f28317e44df2c720f1e7446132ab1e316d0f096c8937aa` |

Runtime evidence remains ignored by Git and is written only under the project state root:

```text
<APP_STATE_DIR>/demo-estate/receipts/demo-initialize-receipt.json
<APP_STATE_DIR>/demo-estate/receipts/demo-outage-receipt.json
<APP_STATE_DIR>/recovery-runs/<run-id>/run.json
<APP_STATE_DIR>/recovery-runs/<run-id>/recovery-report.json
<APP_STATE_DIR>/recovery-runs/<run-id>/recovery-report.md
<APP_STATE_DIR>/recovery-runs/<run-id>/datahub-writeback-receipt.json
<APP_STATE_DIR>/datahub-receipts/writeback-receipt.json  # vertical-slice component only
```

Immutable evidence retention is live-closed with two public verified runs. Remaining portfolio work is final submission recording and packaging. This documentation-only update did not deploy, access AWS/EC2, open a tunnel, rerun tests, or handle a token.

## Promotion and rollback

- Current deployed application code/image: exact immutable-evidence candidate `a304df864a9eedff91862d0d4642484f0ab89984`.
- Application rollback: return to `c92488300023fc65660499b3406fd2e4db76fcbc`.
- DataHub fixture rollback remains the confirmed `reset-datahub` command inherited from candidate `f00c48362bcb6d09737c2809f89dea7675682075`; never use the reset implementation from `12ca7b9a...`, and never use a global DataHub reset.

## Final submission assets

- `SUBMISSION.md` contains judge-ready Devpost copy with the actual public
  application and repository URLs, category fit, architecture, setup/adoption,
  challenges, accomplishments, limitations, and coordinator-verified live
  evidence boundaries.
- `docs/DEMO_RUNBOOK.md` is the canonical 2:42 public-app recording sequence,
  including preflight, exact narration, visible proof, retake rules, and
  public-safety review.
- No product code, tests, dependencies, runtime configuration, deployment, or
  existing evidence changed in this documentation-only milestone.
- The public 2:23 demo is available at <https://youtu.be/suA7xEgZmqw> with published English
  captions. Remaining submission work is to paste the reviewed copy and video URL into Devpost
  and perform the final signed-out link check.
