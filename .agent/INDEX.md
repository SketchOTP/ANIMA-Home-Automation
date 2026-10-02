# Authority Project-State Index

## Project identity

- Project: ANIMA HA (Home Automation)
- Product identity: Anima
- Authority schema: 3.0
- Canonical Notion: https://app.notion.com/p/3c9833cb27ff81759597cdc69c59176c
- GitHub: https://github.com/SketchOTP/ANIMA-Home-Automation

## Current pointers — owner takeover 2026-10-01

- Development Architect: primary Codex session
  `01a052d8-2511-7382-a1ef-b0a080514788`; one native Coder, independent review.
- Integration continuation: existing `ANIMA-HA-GOAL-PHYSICAL-LATENCY-AND-RESIDUAL-CLOSURE-027A`
  / R5F. BASELINE/GOVERNANCE accepted by primary Architect; Stage1 source bundle
  and bounded controlled recovery are independently ACCEPTED, not whole Stage1
  or physical/full-goal acceptance. Both published-head CI runs passed.
  Stage2 accountable delivery/presence SOURCE is independently ACCEPTED FOR
  PUBLICATION / CONTROLLED DEPLOYMENT; hosted CI/deployment pending. See ANIMA 027A
  `NATIVE-ARCHITECT-REVIEWS.md`, `STAGE1-CODER-RESULT.md` and
  `STAGE2-CODER-RESULT.md`. Parent owns reviews/coverage/publication.
- Canonical packet: ANIMA `.agent/tasks/active/ANIMA-HA-GOAL-PHYSICAL-LATENCY-AND-RESIDUAL-CLOSURE-027A/`.
- ANIMA local/published: `main` / `949804dc9f07487868664d2b1508eceb9f44cc6c`.
- SENTRY local: `feature/v0.4-personal-continuity` /
  `23fb216250d646451c47e8d3ea8c63cd7f289d18` (parent-published).
- Parent owns ANIMA execution lock/state, generation/fence 4; Coder is delegate.
- Integration goal authority: ANIMA `.agent/PROJECT_GOAL.md` adopted 2026-08-28,
  [completion contract](https://app.notion.com/p/3d2833cb27ff8154a7b2dd259b4d5250),
  [integration authority](https://app.notion.com/p/3d1833cb27ff81629fdcdd8997323f7e).
  Parent owns full MO-01–15/A–O coverage reconciliation and GOAL-COVERAGE.md
  in 027A; Coder does not create or update that map in this assignment.
- Current evidence/gaps: CURRENT and 027A EVIDENCE/HANDOFF. Historical accepted
  stages and reboot evidence stand; current startup regression is separate.
- Governance and controlled recovery acceptance are bounded; full Stage1/goal completion is not
  established. Parent-owned review and GOAL-COVERAGE records remain authoritative.

Historical R5C/R5D pointers are superseded by owner takeover under 027A/R5F.
Prior R3 acceptance at `01cf05410727e8e38d04bc3025ebb8ed062f8ac8` and accepted
Phase 13/14 records remain evidence history; this amendment supplies no new
acceptance. `ARCHITECT_STARTUP_PROMPT.md` is the preserved historical ChatGPT
template, not current role routing. Use root AGENTS and Authority skill instead.

## Phase 14 historical initial state

- Starting ANIMA head f0456d24fa09ed6873e882c89a9dce759f73a619 matched origin/main
  and was clean. Existing pytest baseline passed 214 tests.
- The Phase 13 packet was moved into completed history without deleting its
  negative/resource-gate evidence.
- The Phase 14 packet was the active implementation pointer during resilience
  work. Its canonical scenario model, destructive qualification, replay, and
  restore evidence were accepted at the current gate above and the packet is
  now completed history.

## Mandatory kernel

Read these before substantial work:

1. `.agent/PROJECT_GOAL.md`
2. `.agent/PROJECT_PROFILE.md`
3. `.agent/CURRENT.md`

Then read the active directive from `.agent/DIRECTIVES.md` and retrieve only the relevant entries from the historical ledgers below.

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

## File responsibility and read/update triggers

Paths below are relative to this repository root. Coder maintains affected local
records; primary Architect reviews accuracy and supplies disposition. Integration
coverage lives only in ANIMA's existing 027A packet. Preserve detailed evidence
once and link it. Read relevant history, not every ledger on each task.

| File / directory | Responsibility and when to read | Update trigger |
| --- | --- | --- |
| `AGENTS.md` | Role routing, constraints, startup order and workflow; every startup | Durable working rules |
| `.agent/INDEX.md` | Navigation, ownership and source relationships; every startup | Structural/pointer changes |
| `.agent/PROJECT_GOAL.md` | Approved intent, exclusions, acceptance and provenance; startup kernel | Authorized goal changes only |
| `.agent/PROJECT_PROFILE.md` | Architecture, environment and integration boundaries; startup kernel | Material verified facts; label implemented/planned |
| `.agent/CURRENT.md` | Requirements/evidence/gaps, worker/task, both repo revisions, deployment, blockers, sync and next action; startup kernel | Meaningful checkpoints |
| `.agent/DIRECTIVES.md` | Assignment register and links; active assignment/revisions | Issuance, meaningful revision, closure; append |
| `.agent/OUTCOMES.md` | Reported results, independent findings and Architect disposition; results/review | Results and independent reviews; append |
| `.agent/LEARNINGS.md` | Evidence-backed lessons and labeled hypotheses; relevant discoveries | Discovery/correction; append |
| `.agent/RECORD.md` | Decisions, rationale, authority and supersessions; relevant role/scope decisions | Significant decisions; append |
| `.agent/REPO_MAP.md` | Important paths, components and verified commands; relevant area | Verified structure/operating changes |
| `.agent/EXTERNAL.md` | Source links, versions, access/coverage gaps, pending sync; relevant external source | External changes/qualification; no secrets |
| `.agent/tasks/README.md` | Minimal packet format and lifecycle; packet work | Conventions only |
| `.agent/tasks/active/` | Purpose, scope, baseline, criteria, progress, evidence, limitations, review and next action; assigned packet | Meaningful assignment checkpoints; blocked/review-pending stays active |
| `.agent/tasks/completed/` | Accepted/cancelled/superseded assignments with distinct disposition; relevant prior evidence | Independently disposed closure; preserve IDs/links |

Historical ledgers and task evidence are append-only. A Coder result does not
close the packet. The native loop and current lifecycle in
`.agents/skills/authority/` supersede historical ChatGPT relay/startup and
generic close-packet wording.
