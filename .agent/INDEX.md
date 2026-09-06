# Authority Project-State Index

## Project identity

- Project: ANIMA HA (Home Automation)
- Product identity: Anima
- Authority schema: 3.0
- Canonical Notion: https://app.notion.com/p/3c9833cb27ff81759597cdc69c59176c
- GitHub: https://github.com/SketchOTP/ANIMA-Home-Automation

## Current pointers

- Current stage: PHASE 14 RESILIENCE, REPLAY, BACKUP AND RECOVERY - 016A; ACTIVE
- Active directive: ANIMA-HA-P14-RESILIENCE-REPLAY-BACKUP-RECOVERY-016A
- Active task packet: .agent/tasks/active/ANIMA-HA-P14-RESILIENCE-REPLAY-BACKUP-RECOVERY-016A/
- Last accepted outcome: Phase 13 SENTRY-ready household authority platform,
  ANIMA f0456d24fa09ed6873e882c89a9dce759f73a619, CI 33938497635; isolated
  SENTRY launcher compatibility patch 00aa9ac3a35b7b012581160b961e01a9480bbbdf,
  CI 33939908542
- Last completed outcome: Phase 13 SENTRY-ready platform; Phase 14 is the only
  active ANIMA scope and Phase 15 remains unauthorized.
- Last state sync: 2026-09-06; Phases 0-13 are Architect accepted. Phase 14
  has a complete bounded implementation/evidence candidate pending Architect
  acceptance; Phase 15 remains unauthorized.

## Phase 14 initial state

- Starting ANIMA head f0456d24fa09ed6873e882c89a9dce759f73a619 matched origin/main
  and was clean. Existing pytest baseline passed 214 tests.
- The Phase 13 packet was moved into completed history without deleting its
  negative/resource-gate evidence.
- The Phase 14 packet is the only current implementation pointer. The
  canonical scenario model and deterministic replay/restore safety metadata
  are complete for the bounded closure contract; final Phase 14 acceptance is
  not claimed.

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
