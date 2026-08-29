# ANIMA-HA-P1-REALITY-SUBSTRATE-003

## Objective

Build the deterministic PostgreSQL-backed event journal and Truth/State substrate, with no AI reasoning, Home Assistant integration, Household Graph, memory, policy, or later behavior.

## Acceptance boundary

Normalized immutable events, source/event idempotency, append-only history, deterministic source ordering, explicit truth uncertainty/conflict/freshness, journal-first projection retry, restart persistence, side-effect-free replay/rebuild, and synthetic simulator evidence.
