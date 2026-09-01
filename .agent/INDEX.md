# Authority Project-State Index

## Project identity

- Project: ANIMA HA (Home Automation)
- Product identity: Anima
- Authority schema: 3.0
- Canonical Notion: https://app.notion.com/p/3c9833cb27ff81759597cdc69c59176c
- GitHub: https://github.com/SketchOTP/ANIMA-Home-Automation

## Current pointers

- Current stage: PHASE 12 CUSTOM WHOLE-HOME INTERFACE — IMPLEMENTED LOCALLY, PENDING VALIDATION/PUBLICATION
- Active directive: ANIMA-HA-P12-CUSTOM-LOCAL-INTERFACE-014 — shared local interface, secure session/auth boundary, semantic API, and responsive browser evidence
- Active task packet: `.agent/tasks/active/ANIMA-HA-P12-CUSTOM-LOCAL-INTERFACE-014/`
- Last accepted outcome: Phase 11 external capabilities (Architect accepted at `918365ce7c6145780112a808411d750fb0e289eb`, CI `33562645002`)
- Last completed outcome: Phase 12 implementation checkpoint `8a8f798d5d2319e690572d69a323e10459924bce`; hosted CI `33572829176` passed on that exact SHA; governed closure remains open
- Last state sync: 2026-09-01; Phase 12 implementation is published, with final governance closure and Architect acceptance pending.

## Current qualification result

- Best Buy's official Products API and terms were rechecked. Products API is
  active, requires an ordinary API key, documents `50,000/day` and `5/sec`,
  and keeps Commerce API invite-only and out of scope.
- Best Buy terms limit Content storage/cache to 72 hours. ANIMA's current
  PostgreSQL agent tool-request table durably stores the full sanitized result
  with no expiry/purge mechanism. Best Buy therefore cannot be integrated
  under this bounded directive without an Architect-authorized retention
  change.
- Result: Phase 11 is Architect accepted. Phase 12 is authorized and currently
  implemented locally, with deterministic backend/frontend/Playwright evidence.
  The production conversation runtime bridge remains an explicit injection seam
  and is not claimed as live AgentRuntime evidence. Phase 13 remains unauthorized.

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
