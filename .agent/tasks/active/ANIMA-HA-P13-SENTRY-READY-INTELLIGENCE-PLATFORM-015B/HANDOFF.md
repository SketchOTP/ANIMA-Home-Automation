# Handoff — ANIMA-HA-P13-SENTRY-READY-INTELLIGENCE-PLATFORM-015B

## R2 status

R2 is an implementation continuation, not an acceptance declaration. The
ANIMA-side corrections add pre-model provider fencing, direct interaction
creation, request-specific claiming, household/provider service-principal
binding, and non-escalating SENTRY identity evidence. Real/shadow SENTRY host,
physical SenseGuard, voice, and live household action evidence remain gates for
Architect review.

## Current disposition

`CONTINUE — IMPLEMENTATION/EVIDENCE IN PROGRESS`

ANIMA now exposes the durable, policy-enforcing boundary required for SENTRY
to become the sole production household intelligence layer. The Home
Assistant adapter remains the only HA integration and continues to normalize
events into Truth and the Event Journal.

## Operator commissioning sequence

1. Apply ANIMA migrations.
2. Set the commissioned non-secret environment values documented in
   `docs/SENTRY-ANIMA-INTEGRATION.md`; inject the HA token only through the
   existing secret boundary.
3. Run `anima-sentry-bridge` for Attention-to-request delivery.
4. Load `integrations/sentry/anima-household/.mcp.json` in the SENTRY host and set a
   host-owned `ANIMA_SENTRY_WORKER_ID`.
5. Validate SenseGuard event → Truth/Journal → Attention → SENTRY claim →
   semantic read/action → policy/Phase 9 → observed result.

SENTRY must not connect directly to HA, PostgreSQL, arbitrary HTTP, shell, or
the provider credentials. The checked-in ANIMA MCP tools are the only intended
cross-project surface.

## Acceptance limit

This handoff does not claim live SENTRY voice, restart/resilience, or full
household demonstration. Those are the next bounded validation work, not an
authorization for Phase 14/15 or a second intelligence engine.

## R1 current handoff

The bounded ANIMA-side implementation now includes the credential-isolated
Core service/client split, server-issued direct-interaction bindings,
provider-scoped request claiming, no-blind-replay handling for possible
provider dispatch, request-scoped catalogue enforcement, current Home
Assistant child-device registry metadata, and a typed SenseGuard overnight
alert policy. Local focused/full validation is green. The remaining evidence
limits are the protected SENTRY host turn, physical SenseGuard trigger and
voice delivery, live HA execution, and hosted exact-head publication. Phase
14/15 remain unauthorized and Phase 13 is not self-accepted.

## R3 qualification handoff

R3 adds household/client-scoped direct SENTRY idempotency, actual persisted
identity-evidence references, server-owned profile mapping with Graph
membership checks, consistent direct/provider origin enforcement, and the
normalized HA SenseGuard event router. Focused and full local validation are
green. The protected SENTRY V0.4 tree remains untouched.

Current verdict: `PARTIAL — ANIMA-SIDE INTEGRATION HARDENED; PENDING ARCHITECT
ACCEPTANCE`. Live/shadow SENTRY, physical SenseGuard, voice, and live HA
evidence remain unclaimed resource/commissioning gates.

## R3 exact-head publication

Implementation/final governed head: `da9b6de2aceb34e36a51c400dcf8b090e010115d`.
Exact hosted CI `33933037033` passed on that head. Artifact `9959297861` was
published as `phase12-h5-evidence-da9b6de2aceb34e36a51c400dcf8b090e010115d`.
This remains a partial Phase 13 result and does not self-accept the phase.
