# Handoff — ANIMA-HA-P13-SENTRY-READY-INTELLIGENCE-PLATFORM-015B

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
4. Load `integrations/sentry/anima-core/.mcp.json` in the SENTRY host and set a
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
