# Authority Project-State Index

## Project identity

- Project: ANIMA HA (Home Automation)
- Product identity: Anima
- Authority schema: 3.0
- Canonical Notion: https://app.notion.com/p/3c9833cb27ff81759597cdc69c59176c
- GitHub: https://github.com/SketchOTP/ANIMA-Home-Automation

## Current pointers

- Current stage: PHASE 11 UPCITEMDB PRODUCT PROVIDER — IMPLEMENTED, PENDING ARCHITECT ACCEPTANCE
- Active directive: ANIMA-HA-P11-UPCITEMDB-PRODUCT-PROVIDER-013R6 — no-signup/no-key product-provider qualification and cutover
- Active task packet: `.agent/tasks/completed/ANIMA-HA-P11-UPCITEMDB-PRODUCT-PROVIDER-013R6/`
- Last accepted outcome: Phase 10 durable-task integration (Architect accepted at `2c8f88f62c27a728b2bf0861dabaf7a3a3d03e56`)
- Last completed outcome: Phase 11 Walmart product provider implementation and live usefulness evidence; entitlement qualification is unresolved and recorded in the current completed packet and Notion
- Last state sync: 2026-09-01; UPCitemdb implementation/governance checkpoint and hosted CI are recorded in the current completed task packet and Notion after publication.

## Current qualification result

- Best Buy's official Products API and terms were rechecked. Products API is
  active, requires an ordinary API key, documents `50,000/day` and `5/sec`,
  and keeps Commerce API invite-only and out of scope.
- Best Buy terms limit Content storage/cache to 72 hours. ANIMA's current
  PostgreSQL agent tool-request table durably stores the full sanitized result
  with no expiry/purge mechanism. Best Buy therefore cannot be integrated
  under this bounded directive without an Architect-authorized retention
  change.
- Result: `BLOCKED — BEST_BUY_RETENTION_COMPLIANCE`. No implementation files,
  secrets, account settings, or live provider calls changed. Walmart remains
  preserved as `DEFER — ENTITLEMENT_CLARIFICATION`; no fallback is active.
- Phase 12 remains unauthorized.

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
