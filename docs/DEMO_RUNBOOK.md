# Lineage Lifeboat: Under-Three-Minute Recording Runbook

Target finished video: **2 minutes 42 seconds**.
Hard ceiling: **2 minutes 59 seconds**.

Public application:
<https://lifeboat.datahub-hackathon.aaronmathias.com>

Public repository:
<https://github.com/amathias/lineage-lifeboat>

This is the canonical recording artifact. The main take uses only the public
application and public repository. Do not open AWS, EC2, a tunnel, a terminal
containing environment variables, or raw runtime receipts while recording.

## One-time recording setup

- Use a 1920x1080 or larger capture area.
- Set browser zoom so the graph, recovery waves, and evidence scorecard are
  legible without scrolling during execution.
- Disable desktop notifications, password-manager overlays, bookmarks
  containing private names, and unrelated browser extensions.
- Open only these tabs:
  1. <https://lifeboat.datahub-hackathon.aaronmathias.com>
  2. <https://github.com/amathias/lineage-lifeboat>
- Use no copyrighted music or third-party footage.
- Record in English or add accurate English captions.

## Public preflight

Perform this immediately before the take:

1. Confirm the page loads:
   <https://lifeboat.datahub-hackathon.aaronmathias.com>
2. Confirm liveness is HTTP 200:
   <https://lifeboat.datahub-hackathon.aaronmathias.com/api/health>
3. Confirm readiness is HTTP 200:
   <https://lifeboat.datahub-hackathon.aaronmathias.com/api/readiness>
4. Return to the main page and refresh once.
5. Choose a run ID that has never been used. Use `devpost-final-001` for the
   first take; increment the numeric suffix for every retake.
6. Enter the chosen run ID before triggering the outage.

If readiness is not HTTP 200, the graph context does not show
`verified live datahub mcp`, or the final DataHub status does not become
`VERIFIED`, stop the take. Do not edit the video to imply live proof that the
application did not produce.

## Exact recording sequence

### 0:00-0:14 — Establish the problem

**On screen**

- Show the Lineage Lifeboat title and the eight-asset commerce graph.

**Narration**

> Backups restore infrastructure. They do not prove when downstream data
> products are trustworthy. Lineage Lifeboat turns live DataHub lineage into an
> approved, dependency-correct recovery program.

### 0:14-0:29 — Initialize the disposable estate

**On screen**

- Click **Initialize estate**.
- Point briefly to the eight healthy assets.

**Narration**

> This creates a real disposable DuckDB and artifact estate. No cloud or
> production system is touched.

### 0:29-0:45 — Execute the outage

**On screen**

- Click **Trigger outage**.
- Show six assets change to outage state.
- Point to healthy `raw.customers` and excluded `inventory.forecast`.

**Narration**

> The confirmed outage removes six connected recovery targets, preserves the
> healthy customer prerequisite, and leaves the unrelated inventory branch
> untouched.

### 0:45-1:10 — Compile from verified DataHub context

**On screen**

- Confirm the unique run ID is present.
- Click **Compile plan**.
- Point to `verified live datahub mcp`.
- Show five dependency waves and the parallel fourth wave.

**Narration**

> Live MCP evidence proves the project entities and complete direct lineage.
> The deterministic compiler binds that graph fingerprint to five topological
> waves. Missing edges, cycles, unsupported adapters, or stale proof fail closed.

### 1:10-1:27 — Human approval

**On screen**

- Pause on the compiled waves.
- Click **Approve exact plan**.
- Show that execution becomes enabled only after approval.

**Narration**

> Execution is locked until an incident commander approves this exact persisted
> plan ID. A missing or mismatched approval cannot execute.

### 1:27-2:03 — Execute and validate

**On screen**

- Click **Execute recovery**.
- Watch the six timeline entries become verified.
- Point to adapter actions, validation counts, and attempt numbers.

**Narration**

> Four real adapter families restore Parquet into DuckDB, run two SQL
> transformations, build the feature and model artifacts, and refresh the
> report. Required schema, count, checksum, freshness, business-rule, model, and
> input-fingerprint checks block consumers until they pass.

### 2:03-2:27 — Show evidence and DataHub writeback

**On screen**

- Show `6 / 6` verified.
- Show the final DataHub status `VERIFIED`.
- Point to the execution timeline and evidence scorecard.

**Narration**

> All six targets are verified. The supported DataHub global-tags writeback was
> immediately reread through MCP. The scrubbed receipt and run ledger are stored
> under this run's immutable evidence path, so a later run cannot replace them.

### 2:27-2:42 — Close with adoption

**On screen**

- Switch to <https://github.com/amathias/lineage-lifeboat>.
- Show the README, examples, and Apache-2.0 license.

**Narration**

> The public repository includes the adapters, tests, generated plan and report,
> and a local demo that needs no paid infrastructure. Lineage Lifeboat restores
> trust in dependency order.

Stop recording by **2:42**. Do not fill unused time.

## On-screen proof checklist

The main take must visibly show:

- [ ] the public Lineage Lifeboat application;
- [ ] eight catalog assets;
- [ ] six unavailable recovery targets after the outage;
- [ ] healthy `raw.customers`;
- [ ] excluded `inventory.forecast`;
- [ ] context mode `verified live datahub mcp`;
- [ ] five recovery waves;
- [ ] exact-plan approval;
- [ ] six verified execution steps;
- [ ] DataHub status `VERIFIED`;
- [ ] the public GitHub repository.

## Truthful claims card

| What is shown | Allowed claim |
|---|---|
| DuckDB and artifact recovery | executed and validated against a disposable local estate |
| DataHub context | live only when the run shows `verified live datahub mcp` |
| DataHub writeback | supported `globalTags` update verified by immediate MCP reread |
| Approval | exact persisted plan ID approved before execution |
| Resume | tested and implemented; verified steps are not rerun |
| Cloud failover | not performed |
| Production autonomy | not claimed |
| RPO/RTO | not guaranteed |

## Retake procedure

For every retake:

1. Stop the previous recording.
2. Increment the run ID suffix, for example from `devpost-final-001` to
   `devpost-final-002`.
3. Refresh the public application.
4. Click **Initialize estate** before triggering another outage.
5. Repeat the public preflight.

Never reuse a completed live run ID. Per-run DataHub evidence is immutable by
design, and a new take should receive a new evidence directory.

## Failure handling

- If a step fails, keep the failure only for a separate optional engineering
  clip. Do not include an unreliable failure injection in the main take.
- If the UI offers **Resume recovery**, a retake may demonstrate it only after
  the primary under-three-minute video is complete.
- If DataHub status is `NOT_CONFIGURED` or `FAILED`, state that result honestly;
  do not narrate a verified live writeback.
- Do not open raw receipt storage or copy hashes from a private runtime during
  recording. Public evidence boundaries are documented in the repository.

## Post-recording review

- [ ] Runtime is below 2:59.
- [ ] Text is legible at normal playback speed.
- [ ] The app performs the workflow; the video is not a slide-only presentation.
- [ ] DataHub is visibly part of both input and output.
- [ ] Real local execution is distinguished from unperformed cloud recovery.
- [ ] No secret, token, environment variable, notification, private tab, or AWS
      identifier is visible.
- [ ] No copyrighted music or third-party footage is present.
- [ ] Captions and narration say “DataHub-powered,” not “built by DataHub.”
- [ ] The final uploaded video is public and playable while signed out.
- [ ] The Devpost project URL is
      <https://lifeboat.datahub-hackathon.aaronmathias.com>.
- [ ] The Devpost repository URL is
      <https://github.com/amathias/lineage-lifeboat>.
