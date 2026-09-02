# Authority Project-State Index

## Project identity

- Project: ANIMA HA (Home Automation)
- Product identity: Anima
- Authority schema: 3.0
- Canonical Notion: https://app.notion.com/p/3c9833cb27ff81759597cdc69c59176c
- GitHub: https://github.com/SketchOTP/ANIMA-Home-Automation

## Current pointers

- Current stage: PHASE 12 CUSTOM WHOLE-HOME INTERFACE — INTEGRATED, VALIDATED, GOVERNANCE CLOSURE
- Active directive: ANIMA-HA-P12-CORE-INTEGRATION-PORTFOLIO-CLOSURE-014H — production Core composition, end-to-end evidence, and portfolio closure
- Active task packet: none; completed Phase 12 packet: `.agent/tasks/completed/ANIMA-HA-P12-CUSTOM-LOCAL-INTERFACE-014/`
- Last accepted outcome: Phase 11 external capabilities (Architect accepted at `918365ce7c6145780112a808411d750fb0e289eb`, CI `33562645002`)
- Last completed outcome: Phase 12 shell checkpoint `800c4cc4b1783e3f755cabff37c3db091b0c9ab1`; the current integration delta is locally validated and awaiting its implementation/publication checkpoint
- Last state sync: 2026-09-01; Phase 12 production integration and portfolio evidence are implemented locally, with Architect acceptance still pending.

## Current qualification result

- Best Buy's official Products API and terms were rechecked. Products API is
  active, requires an ordinary API key, documents `50,000/day` and `5/sec`,
  and keeps Commerce API invite-only and out of scope.
- Best Buy terms limit Content storage/cache to 72 hours. ANIMA's current
  PostgreSQL agent tool-request table durably stores the full sanitized result
  with no expiry/purge mechanism. Best Buy therefore cannot be integrated
  under this bounded directive without an Architect-authorized retention
  change.
- Result: Phase 11 is Architect accepted. Phase 12 is authorized; the current
  integration delta composes the production UI through the existing Journal,
  Attention, Context Broker, AgentRuntime, Tool Gateway, policy, task,
  calendar, and action-coordinator boundaries. Phase 12 remains pending
  Architect acceptance. Phase 13 remains unauthorized.

## Mandatory kernel

Read these before substantial work:

1. `PROJECT_GOAL.md`
2. `PROJECT_PROFILE.md`
3. `CURRENT.md`

Then read the active directive from `DIRECTIVES.md` and retrieve only the relevant entries from the historical ledgers below.

## Historical ledgers

- `DIRECTIVES.md` — issued work and acceptance boundaries.
- `OUTCOMES.md` — what happened and the evidence achieved.
- `LEARNINGS.md` — durable verified technical/project learnings.
- `RECORD.md` — major decisions, milestones, reversals, governance events.
- `REPO_MAP.md` — repository structure and important boundaries.
- `EXTERNAL.md` — relevant external prior art and dispositions.

Do not bulk-load entire growing ledgers unless the task genuinely requires it. Do not skip relevant history merely to save context.

## Update rule

`CURRENT.md` is the mutable current snapshot.

Historical ledgers are append-only after adoption. Correct mistakes with a new superseding entry; do not rewrite old evidence.
