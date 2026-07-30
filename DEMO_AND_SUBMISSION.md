# Demo and Submission Guide: Lineage Lifeboat

## Devpost short description

Lineage Lifeboat is a DataHub-powered disaster-recovery agent. It reads live lineage, schemas, ownership, assertions, and platform context; compiles a dependency-correct recovery DAG; executes approved local recovery adapters; validates each restored artifact; and records the incident outcome back into DataHub.

## Three-minute demo target

Aim for **2 minutes 35 seconds to 2 minutes 45 seconds**. Do not rely on speed-ups that make the functioning app impossible to inspect.

### 0:00–0:18 — The problem

Show the healthy commerce graph and then activate the prepared warehouse-outage scenario.

Narration:

> Backups restore systems, but they do not know the order in which a cross-platform data estate becomes trustworthy. This outage affects transformations, features, a model, and a dashboard.

### 0:18–0:48 — DataHub context

Show the agent retrieving the live DataHub impact graph, including at least lineage, schemas, owners, and assertions. Highlight the unrelated branch that is correctly excluded.

Narration:

> Lineage Lifeboat uses DataHub as the current dependency and governance map—not a hard-coded runbook.

### 0:48–1:20 — Compile the plan

Generate the plan. Show dependency waves, prerequisites, validations, risk, and one action that cannot run before another. Briefly show the machine-readable plan.

Narration:

> The recovery compiler produces an auditable DAG. Deterministic safety checks validate ordering, supported adapters, graph freshness, and approval requirements.

### 1:20–2:05 — Approve and execute

Approve. Show real local restore, transformation, feature/model rebuild, and validations. Include one intentionally retried step if it is completely reliable.

Narration:

> Execution is idempotent and resumable. A consumer is not marked ready until its prerequisites and validations pass.

### 2:05–2:30 — Verification and writeback

Show the final report, metrics, and the visible DataHub writeback.

Narration:

> Every completed action has evidence. The recovery outcome returns to DataHub so the next engineer or agent inherits what happened.

### 2:30–2:42 — Close

Show title and architecture/result summary.

> Lineage Lifeboat turns DataHub lineage into an executable recovery program.

## Submission narrative

### Problem

Modern recovery plans are fragmented by platform and become stale as dependencies change. Restoring infrastructure does not prove that derived data products are trustworthy or that they returned in a valid order.

### Solution

Lineage Lifeboat compiles the current DataHub context graph into an executable recovery DAG, gates unsafe actions, validates restored assets, and writes evidence back to the graph.

### What makes it original

The project does not compete with storage backup. It addresses the orchestration gap across backups, transformations, features, models, and consumers by using lineage as executable control flow.

### DataHub usage to state explicitly

- Reads lineage, schema, ownership, platform, governance, and assertion context.
- Uses the graph to select assets and determine order.
- Uses DataHub's eligible agent integration in the live workflow.
- Writes supported recovery status/evidence references back to DataHub.

## Judging evidence map

| Criterion | What judges should see |
|---|---|
| Use of DataHub | Live graph retrieval changes impact and ordering; visible writeback |
| Technical execution | Real adapters, idempotency, approval, retry/resume, validations, tests |
| Originality | Cross-platform recovery compiler rather than backup replication |
| Real-world usefulness | Clear incident-commander workflow and measurable recovery evidence |
| Submission quality | Under-three-minute demo, clean README, one-command setup, examples |

## Required repository evidence

- `examples/recovery-plan.json`
- `examples/recovery-report.md`
- one graph snapshot or fixture manifest
- one adapter receipt bundle
- screenshots of DataHub before and after
- architecture diagram
- test output or CI badge
- documented limitations

## Claims to avoid

- “Replaces disaster-recovery infrastructure.”
- “Supports every data platform.”
- “Guarantees recovery time.”
- “Fully autonomous in production.”

Prefer: “Compiles and verifies cross-platform recovery actions from DataHub context in the demonstrated adapters.”

## Recording checklist

- [x] Video is public and under three minutes: <https://youtu.be/7UIM_Y9Uvg4> (2:05).
- [ ] Text is legible at normal playback speed.
- [ ] No secrets, notifications, private tabs, or copyrighted music appear.
- [ ] The app is shown functioning, not just slides.
- [ ] DataHub is visibly part of both input and output.
- [ ] The outage and reset are tested immediately before recording.
- [ ] Captions or narration state what is real versus simulated.
## Implemented judge workflow

The packaged console at `/` now implements the six required screens as one
continuous view: incident controls, DataHub impact graph, dependency waves,
approval, execution/validation timeline, and final evidence/writeback status.
The exact timed click path and truthful real/simulated labels are maintained in
`docs/DEMO_RUNBOOK.md`.

The local demo uses four real adapters against disposable DuckDB and JSON
artifacts. `scripts/verify_judge_demo.py` recreates the estate in a temporary
directory, executes all six recovery steps, verifies every required result, and
fails if runtime reaches three minutes. Sanitized example evidence is available under
`examples/` and can be regenerated with `scripts/generate_examples.py`.
