# ANIMA-HA-P14-RESILIENCE-REPLAY-BACKUP-RECOVERY-016A

Status: ACTIVE - Phase 14 only.

## Objective

Prove that the accepted ANIMA household-authority platform preserves authority,
verification, privacy, and deterministic recovery across failure, duplication,
concurrency, outage, replay, and backup/restore boundaries.

Phases 0-13 are Architect accepted. Phase 15 is not authorized and must not be
implemented.

## Boundary

SENTRY remains the production intelligence provider and ANIMA remains the
household authority. ANIMA policy, Truth, identity, Phase 5, Phase 9, durable
tasks, provider trust, and restricted-content rules are preserved. No new
broker, database, workflow engine, provider, raw HA/SQL/shell capability, or
embedded-intelligence fallback is permitted.

## Evidence contract

Every destructive scenario uses the canonical bounded machine-readable model in
src/anima_ha/resilience.py. Required fields include durable state, Truth
versions, identity and policy, ordering, request/provider lifecycle, fault
point, action state, observations, availability, terminal state, side-effect
count, and recovery behavior.

Required evidence labels are PASSED, FAILED, NOT RUN, NOT APPLICABLE, and
BLOCKED. A scenario cannot be promoted from NOT RUN or BLOCKED by inference.

## Required scenario families

Provider ambiguity and fencing; approval and action exactly-once behavior;
duplicate and out-of-order HA/SenseGuard events; concurrency and manual-change
conflicts; HA/OPA/plugin/SENTRY outages; hostile external content; restricted
content; large task/calendar history; process restart; backup/restore; replay
regression detection; and ARM64 portability.

## Acceptance

Phase 14 may return COMPLETE - PENDING ARCHITECT ACCEPTANCE only after the
scenario ledger, focused tests, replay and restore evidence, static/build
validation, exact-head CI, governance records, and clean pushed state agree.

## Stop boundary

Return NEEDS_ARCHITECT_DECISION only if correctness requires replaying an
ambiguous effect, weakening authority or verification, storing prohibited
secrets/content, or adding a foundational broker/database/workflow service.
