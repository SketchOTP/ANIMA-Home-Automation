# CODEX DIRECTIVE — ANIMA-HA-P12-CONFIRMATION-CONTINUATION-FINAL-ACCEPTANCE-014H5U

## Disposition

`CONTINUE — FINAL PHASE 12 CORRECTNESS CLOSURE`.

## Objective

Implement safe durable exact-intent confirmation continuation using the
existing Phase 4 confirmation challenge, Phase 5 policy gateway, Phase 8
episode/runtime, Phase 9 action coordinator, and PostgreSQL persistence
boundaries. Close the known H5U task/calendar and governance drift without
starting Phase 13.

## Required boundary

- Preserve the exact action intent, authenticated principal, household,
  episode, trigger, tool version, idempotency identity, trusted preconditions,
  lock scopes, and bounded semantic request envelope.
- Keep pending approvals non-executable to model/UI callers; do not persist
  restricted content, secrets, credentials, or executable code in approval
  payloads.
- Approval and rejection must be authenticated, CSRF/origin protected,
  single-use, expiry-aware, household/principal-bound, and re-authorized with
  current policy/Truth before any Phase 9 dispatch.
- Preserve observation-first verification, Phase 9 terminal-result authority,
  and at-most-one dispatch.
- Keep Phase 13 unauthorized.

## Acceptance focus

Durable PostgreSQL approval, same-episode continuation, wrong-principal/
expiry/rejection/replay fail-closed behavior, task regression correction,
focused/full validation, exact-head hosted CI, and reconciled Authority/
Notion records.
