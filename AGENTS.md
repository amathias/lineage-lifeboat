# Builder Instructions: Lineage Lifeboat

## Mission

Build a working, judge-ready vertical slice of Lineage Lifeboat: a DataHub-powered agent that compiles, executes, verifies, and records dependency-correct disaster-recovery plans.

## Read first

Before modifying code, read these files completely:

1. `HACKATHON_RULES.md`
2. `PROJECT_BRIEF.md`
3. `BUILD_PLAN.md`
4. `DEMO_AND_SUBMISSION.md`

## Non-negotiable product behavior

- Read real lineage and context from a running open-source DataHub instance through an eligible integration such as the DataHub MCP Server or Agent Context Kit.
- Demonstrate at least one real writeback to DataHub through a supported API or SDK.
- Generate a deterministic recovery DAG whose ordering can be independently verified.
- Execute real local recovery adapters against disposable demo systems; clearly label simulated cloud actions.
- Validate every recovered step and retain evidence.
- Require human approval before any destructive or production-like action.
- Keep the core demo runnable without paid infrastructure.

## Engineering principles

- Ship the smallest end-to-end story before adding integrations.
- Separate deterministic graph planning and safety checks from LLM explanation.
- Treat all LLM output as a proposal that must pass schema validation and policy checks.
- Make retries idempotent and make execution state resumable.
- Never claim an action occurred unless the adapter produced verifiable evidence.
- Keep secrets in environment variables and provide `.env.example`.
- Add unit tests for graph ordering, cycle handling, policy gates, idempotency, and validation failures.
- Maintain `docs/DECISIONS.md` as architectural decisions are made.

## Definition of done

The project is not done until a new reviewer can follow the README, start DataHub and the app, ingest the demo graph, trigger the outage, generate and approve a plan, execute it, see validation results, confirm DataHub writeback, run automated tests, and reproduce the under-three-minute demo.

## Submission guardrails

- The repository must be public and contain an Apache 2.0 `LICENSE`.
- The work must be newly built during the submission period.
- Disclose any meaningful pre-existing code or assets.
- Keep the title independent: “Lineage Lifeboat,” described as DataHub-powered.
