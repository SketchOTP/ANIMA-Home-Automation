# Phase 11 external gate-closure handoff

Verdict: `IMPLEMENTATION_COMPLETE — EXTERNAL_RESOURCE_GATE`.

Phase 11 remains `CONTINUE`, not accepted. The implementation checkpoint
`dde3e2bc42fc5004ddf06690ddbd9dc9941999f8` passed hosted CI `33445636772` on
the exact SHA. The evidence amendment checkpoint
`f069e5c0d1d42d0a74eba3267f8393f325509429` passed hosted CI `33446725375` on
the exact SHA. The final governed metadata synchronization checkpoint and its
hosted CI are recorded after publication.

The correction adds refreshable ANIMA-owned Calendar OAuth with the exact
owned-calendar scope `https://www.googleapis.com/auth/calendar.events.owned`,
same-request auth refresh, expanded independent Brave web/place/product and
Calendar list/create-readback gates, actual shared-catalogue AgentRuntime
selection, prompt-injection containment through the next cognition turn, and
a PostgreSQL-backed durable-task fresh external follow-up fixture. The accepted fixed-host,
external-untrusted, Phase 9 write, and Phase 10 durable-task boundaries are
preserved.

Brave web/place/product and Google Calendar list/create-readback remain
`EXTERNAL_RESOURCE_GATE` because no runtime credentials are available. The
synthetic Open-Meteo, TheMealDB, and ntfy checks pass. The new durable external
fixture uses deterministic MockTransport; the PostgreSQL harness now proves
task persistence/restart and fresh external value retrieval through the real
scheduled-cognition path.

Phase 12 was not implemented. Return control to the Architect for independent
Phase 11 acceptance.
