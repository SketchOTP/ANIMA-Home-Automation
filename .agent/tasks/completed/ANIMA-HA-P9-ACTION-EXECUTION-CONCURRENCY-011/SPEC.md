# Phase 9 bounded specification

The coordinator is the execution boundary for consequential agent-selected actions. It must:

- claim a durable idempotency key and reject parameter reuse;
- return immediately on canonical-resource contention without queuing stale work;
- obtain fresh provider truth after lock acquisition;
- reject stale Truth preconditions;
- perform final Phase 4 policy evaluation with current truth;
- persist `EXECUTING` before an external call without holding a database transaction across it;
- require connector idempotency metadata;
- preserve `UNKNOWN_RESULT` after an ambiguous call;
- record per-effect outcomes and classify mixed outcomes as `PARTIAL`;
- refresh and verify observed provider state after consequential success;
- reconcile abandoned plans as `RECOVERY_REQUIRED` and in-flight calls as `UNKNOWN_RESULT`.

The coordinator does not retry ambiguous side effects, automatically compensate partial effects, schedule future work, or provide UI/voice behavior.
