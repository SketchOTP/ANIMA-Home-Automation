# Handoff

Phase 10 durable tasks are implemented as a bounded PostgreSQL-backed
declarative engine and remain pending Architect acceptance. Future task records
contain intent/provenance only. Due work emits deterministic guaranteed
`scheduled_reasoning_due` events, which re-enter the existing Attention,
Context, and AgentRuntime path. Phase 11 was not implemented.

Starting accepted SHA: `7f09b52f8773901ea73221f60b40414874809fda`.

Implementation SHA, implementation CI, final governed SHA, final governed CI,
and final clean-tree evidence must be filled with exact values after publication
and hosted CI verification. Notion must then be appended with the same values,
the dependency disposition, evidence limits, and Phase 11 prohibition.
