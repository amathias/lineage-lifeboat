# Coordinator Handoff: Lineage Lifeboat

## Scope and ownership

This project chat owns Lineage Lifeboat product code, tests, demo evidence, and submission behavior. The portfolio coordinator owns shared DataHub, AWS, promotion, secrets, tunnels, and live evidence capture. This milestone did not deploy, access EC2, or modify another workspace.

## Milestone B result

| Field | Value |
|---|---|
| Status | `implementation complete; coordinator live promotion/evidence pending` |
| Exact deployment candidate | `12ca7b9a10222a55cd79f24c72fd800ebe0b0d47` |
| Candidate subject | `fix: request complete MCP lineage results` |
| Superseded live candidate | `bf9435d5b2a9ccecfff68c8995302e325031b8df` |
| Currently deployed baseline | `bf9435d5b2a9ccecfff68c8995302e325031b8df` |
| Local test result | `40 passed` |
| Local coverage | `81% total` |
| Git-archive packaging smoke | `passed: strict UTF-8 README decode, wheel build, isolated install, isolated import` |
| Live deployment performed here | `no` |
| Live DataHub receipt claimed here | `no` |

The candidate implements the smallest guarded real-DataHub slice: supported SDK upserts, MCP entity and direct-edge lineage reads, one tag writeback, immediate MCP reread, scrubbed receipts, deterministic soft reset, and evidence-gated readiness.
It also converts `README.md` from Windows-1252 smart-quote bytes to valid BOM-free UTF-8 without changing its decoded text. This revision requests up to 100 lineage results whenever the MCP tool advertises `max_results` or a compatible result-limit field, while honoring a smaller advertised schema maximum.

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

Verified locally on Python 3.13.2: 40 passed, 81% total coverage.

### Clean Git-archive packaging smoke

```powershell
.\.venv\Scripts\python.exe scripts\archive_package_smoke.py --revision 12ca7b9a10222a55cd79f24c72fd800ebe0b0d47
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

Reset is an explicit soft delete of only the eight canonical fixture URNs and three exact control URNs:

```bash
python -m lineage_lifeboat.cli reset-datahub --confirm-project lineage-lifeboat
```

Restore and capture a new read/write/reread receipt by rerunning:

```bash
python -m lineage_lifeboat.cli datahub-vertical-slice --run-id coordinator-milestone-b-restore-001
```

A missing or incorrect confirmation fails closed. Foreign URNs and namespaced-but-nonfixture writeback targets are rejected.

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

## Health and truthful readiness

- `GET /api/health` is liveness only and never claims DataHub readiness.
- Candidate `GET /api/readiness` requires all of: fixed allocation, valid namespaced fixture, readable/writable state directory, GMS health, configured `DATAHUB_TOKEN`, and a vertical-slice receipt bound to the current fixture fingerprint.
- The aggregate receipt must reference the three exact seed/context/writeback files inside the project receipt directory; missing, relocated, or stale evidence fails closed.
- Expected post-promotion behavior is HTTP 503 until the coordinator runs the live vertical-slice command successfully. HTTP 200 before that would be a defect.
- The public baseline at `d6a73a9...` previously returned readiness 200 based on GMS health alone; this candidate intentionally closes that gap.

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
- Seed and writeback use idempotent aspect UPSERTs. Reset uses reversible `status.removed=true` soft deletes; rerunning the vertical slice restores `status.removed=false`.
- Run only one evidence-producing vertical slice at a time because receipt filenames are intentionally stable; concurrent runs could overwrite each other's local receipt files even though DataHub aspect writes are idempotent.
- Persistent data is limited to the assigned project state root. No shared/global reset is implemented.

## Remaining live evidence and blockers

There is no known implementation or test blocker. Coordinator-owned live work remains:

1. promote exact candidate `12ca7b9a10222a55cd79f24c72fd800ebe0b0d47`;
2. confirm readiness is 503 before live evidence;
3. run the guarded vertical-slice command with the already injected service-account token;
4. capture seed, MCP entity/lineage read, writeback, immediate reread, and readiness 200 evidence;
5. run the confirmed soft reset, verify isolation, rerun the slice to restore, and retain both receipts.

The local workstation still has no `DATAHUB_TOKEN`, no AWS Session Manager plugin, and no listeners on ports 8080/8000. Per coordinator direction, this chat did not install the plugin, request a token, access EC2, or deploy. Those local conditions do not invalidate the clean candidate; they explain why no live receipt is claimed here.
The coordinator successfully deployed `bf9435d5...`. Its live command completed only the namespace-scoped idempotent fixture/control upserts, then failed closed while proving `lifeboat.analytics.customer_revenue -> lifeboat.dashboards.executive_revenue`; an indexing-settled retry failed identically. No `globalTags` writeback and no successful vertical-slice receipt occurred. Candidate `12ca7b9a...` is safe to retry without a global reset because the completed upserts are project-scoped and idempotent.

## Promotion and rollback

- Promote: exact candidate `12ca7b9a10222a55cd79f24c72fd800ebe0b0d47`.
- Roll back application code/image: currently deployed candidate `bf9435d5b2a9ccecfff68c8995302e325031b8df`.
- DataHub fixture rollback: run the candidate's confirmed `reset-datahub` command before application rollback if the coordinator wants the project fixture soft-deleted. Do not use a global DataHub reset.
