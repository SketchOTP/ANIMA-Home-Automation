# Authority Project-State Index

## Project identity

- Project: ANIMA HA (Home Automation)
- Product identity: Anima
- Authority schema: 3.0
- Canonical Notion: https://app.notion.com/p/3c9833cb27ff81759597cdc69c59176c
- GitHub: https://github.com/SketchOTP/ANIMA-Home-Automation

## Current pointers

- Current stage: PHASE 13 SENTRY-READY INTELLIGENCE PLATFORM — 015B-R3; CONTINUE
- Active directive: ANIMA-HA-P13-SENTRY-INTEGRATION-QUALIFICATION-015B-R3 — direct SENTRY identity scoping and normalized SenseGuard-to-Attention integration
- Active task packet: `.agent/tasks/active/ANIMA-HA-P13-SENTRY-READY-INTELLIGENCE-PLATFORM-015B/`
- Last accepted outcome: Phase 11 external capabilities (Architect accepted at `918365ce7c6145780112a808411d750fb0e289eb`, CI `33562645002`)
- Last completed outcome: H5U implementation checkpoint `dbb4720882b25ad1d840c2c270191227f0c4ea1d`; hosted CI `33746353829` passed on that exact SHA. Final governed closure checkpoint `b2049f306416a1d0cd4f61cd370d0686c5bec2d7`; hosted CI `33747181905` passed on that exact SHA.
- Last state sync: 2026-09-04; Phase 0–12 are Architect accepted. Phase 13 is
  the active bounded continuation; Phase 14/15 remain unauthorized.

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
  calendar, and action-coordinator boundaries. Phase 12 is Architect accepted;
  Phase 13 is the active bounded continuation and Phase 14/15 remain
  unauthorized.

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
