# Handoff

Phase 10 durable tasks are implemented as a bounded PostgreSQL-backed
declarative engine and remain pending Architect acceptance under the
`CONTINUE` disposition. Task mutations now use an ANIMA-owned internal policy
boundary and trusted invocation provenance; physical/provider actions remain
Phase 9-coordinated. Future task records contain intent/provenance only. Due
work emits deterministic guaranteed `scheduled_reasoning_due` events, which
re-enter the existing Attention, Context, and AgentRuntime path with a fresh
ContextPacket. Phase 11 was not implemented.

Starting governed SHA: `21dde3cddc3ea4aa5af3e59e6a0334b62d37a7a2` (CI
`33418246958`).

Earlier implementation SHA: `27f7c3fb8ce53c4eb988d7de22c63672770998a8` (CI
`33425928381`).

Corrected implementation SHA: `945f89c13b67e52a9027d3f42cc3e2bccd5608d2`
(CI `33428295199`). The corrected harness explicitly proves that future
scheduled cognition routes a synthetic consequential action through the
existing Phase 9 coordinator with fresh observation and one dispatch.

Final governed SHA: `6e31ee3da18fecad3cb46c3cd4671ee20dae7345` (CI
`33428643340`). The final governed push and clean-tree proof are recorded in
this packet and the Notion SSOT. Evidence remains local
x86-64/isolated HA; native ARM64/Pi, physical-home, high-risk, and production
claims are not made. Phase 11 remains unauthorized.
