# Lineage Lifeboat: Under-Three-Minute Demo Runbook

Target: **2 minutes 35 seconds**. Run `scripts/verify_judge_demo.py` immediately
before recording to prove the local workflow still completes within the limit.

## Preflight

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\ruff.exe check app tests scripts
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\verify_judge_demo.py
.\.venv\Scripts\python.exe -m lineage_lifeboat
```

Open `http://localhost:8101`. Keep DataHub open in a second tab only when a live
credential has already been injected out of band. Never show the token or AWS.

## Recording sequence

### 0:00-0:18 - Why recovery order matters

Show the headline and eight-asset graph.

> Backups restore systems. They do not prove when downstream data products are
> trustworthy. Lineage Lifeboat turns DataHub lineage into the recovery program.

Click **Initialize estate**. State that this creates real local DuckDB tables and
file artifacts; it does not simulate a successful action.

### 0:18-0:42 - Trigger the outage

Click **Trigger outage**. Six assets turn red while `raw.customers` stays healthy
and `inventory.forecast` remains excluded.

> This is an executed deletion against a disposable local estate. No cloud or
> production system is touched.

### 0:42-1:12 - Compile from DataHub context

Click **Compile plan**. Point to the graph context mode, five recovery waves,
healthy prerequisite, and unrelated excluded branch.

> The compiler is deterministic. It binds the plan to the DataHub graph
> fingerprint and refuses cycles, unknown dependencies, or unsupported adapters.

### 1:12-1:32 - Human approval

Click **Approve exact plan**.

> Execution cannot begin until the incident commander approves this exact plan
> ID. A stale or mismatched approval fails closed.

### 1:32-2:08 - Execute and validate

Click **Execute recovery**. Watch six timeline entries become verified.

Call out the real adapters: Parquet restore, two DuckDB SQL transforms, Python
feature/model builds, and dashboard refresh. Point to validations and attempts.

> A validation failure stops consumers. Resume skips already verified steps and
> reuses idempotency keys.

### 2:08-2:28 - Evidence and DataHub writeback

Show `6 / 6` verified and the DataHub outcome. With live credentials the outcome
must say `VERIFIED`; without them it must truthfully say `NOT_CONFIGURED`.

Open the final report or DataHub marker if recording the live environment.

> The run ledger, adapter hashes, validations, and supported DataHub writeback
> become evidence for the next engineer or agent.

### 2:28-2:35 - Close

> Lineage Lifeboat restores trust in dependency order.

## Failure/resume optional take

Only include this if timing remains under three minutes. Use the tested injected
failure scenario during development, show the run fail closed, then click
**Resume recovery**. Never stage an unreliable live failure for the submission.

## Claims

- Local DuckDB and artifact actions: **executed and verified**.
- DataHub MCP reads/writeback: **live only when the receipt says verified**.
- Cloud recovery: **not performed**.
- Production autonomy or RTO guarantee: **not claimed**.