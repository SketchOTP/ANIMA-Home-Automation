# Plan

1. Add bounded provider/request/result contracts and repeat-safe PostgreSQL
   persistence with claim leases and fencing.
2. Add the authenticated local Core boundary and typed SENTRY MCP adapter.
3. Add Attention-to-request delivery and the host bridge contract.
4. Wire the normal composition root and UI/provider health without enabling a
   silent embedded-provider fallback.
5. Add deterministic integration and clean SENTRY-baseline compatibility
   evidence, then run the full existing regression boundary.

The implementation will preserve the accepted Journal, Truth, Graph, memory,
policy, Tool Gateway, Phase 9, durable-task, external-content, and UI
boundaries.

R1 completion emphasis: ANIMA owns the PostgreSQL/OPA/HA credentials and
serves SENTRY over a private authenticated socket; the SENTRY package remains
client-only. Provider-running requests are never blindly reclaimed, and every
SENTRY request uses the catalogue frozen at request creation. Device registry
normalization covers current HA child-device/config-entry records, while the
typed SenseGuard policy remains the only alert configuration surface.

## R2 continuation

1. Fence every SENTRY provider turn before model execution.
2. Separate direct interaction creation from autonomous queue claiming.
3. Enforce server-owned household/provider service principals and identity
   evidence translation.
4. Validate the client-only MCP boundary and request catalogue fencing.
5. Run shadow/live SENTRY, SenseGuard, and governed HA evidence when the
   protected host and physical resources are available; report explicit gates
   otherwise.
