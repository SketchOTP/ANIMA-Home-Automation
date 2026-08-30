# Phase 9 execution plan

Directive: `ANIMA-HA-P9-ACTION-EXECUTION-CONCURRENCY-011`

1. Reuse the Phase 4 policy, Phase 5 gateway, Phase 6 refresh/verification, and Phase 8 bridge.
2. Add durable action/effect records and parameter-bound idempotency claims.
3. Serialize canonical-resource actions with non-blocking PostgreSQL session advisory locks.
4. Refresh state after locking, validate preconditions, reauthorize policy, execute once, and verify observed post-state.
5. Represent ambiguous, partial, and restart outcomes without blind retry or compensation.
6. Validate with focused tests, PostgreSQL, and the isolated pinned Home Assistant harness.

Phase 10 scheduling, UI, voice, production connectors, and physical-home qualification remain excluded.
