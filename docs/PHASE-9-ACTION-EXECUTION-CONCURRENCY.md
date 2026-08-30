# Phase 9 action execution, verification, and concurrency

Checked: 2026-08-30. This phase adds the deterministic execution boundary for
consequential agent-selected tools. It does not add scheduling, UI, voice, or
production external capabilities.

## Boundary

`ActionExecutionCoordinator` owns the lifecycle after Luna proposes a
consequential tool request. It claims a durable idempotency key, acquires
short-lived non-blocking locks for sorted canonical resource UUIDs, refreshes
provider-backed state, validates caller-supplied truth preconditions, and
reauthorizes through the Phase 4 policy service immediately before execution.
The PostgreSQL transaction is committed before the connector call; no database
transaction is held across an external side effect.

Resource contention returns `RESOURCE_BUSY` immediately. A conflicting request
is never queued behind a possibly stale intent. A committed `EXECUTING` record
means that a process restart must treat the outcome as `UNKNOWN_RESULT`, not
blindly retry it. Reusing an idempotency key with different parameters is an
explicit conflict, while replaying the same key returns the original record.

After the connector returns, consequential actions perform a second provider
refresh and invoke the supplied verifier. The coordinator recognizes explicit
provider verification, failure, timeout/ambiguous results, and mixed multi-effect
results. Partial outcomes are durable and do not trigger compensation. A
connector acknowledgement alone is never promoted to verified success.

The coordinator is provider-neutral. Home Assistant remains behind the Phase 6
adapter and Phase 5 gateway; callers supply the refresh/verifier functions that
use the provider's current-state and verification contracts.

## Persistence

Migration `0010_action_execution.sql` adds `anima_actions` and
`anima_action_effects`. Action requests, preconditions, resource scope, status,
latest truth, connector result, and per-effect outcomes are durable. Startup
reconciliation changes abandoned plans to `RECOVERY_REQUIRED` and actions that
had entered external execution to `UNKNOWN_RESULT`.

## Dependency decision

| Candidate | Disposition | Finding |
| --- | --- | --- |
| ANIMA action coordinator and durable records | BUILD | Required to keep freshness, policy, verification, and ambiguity semantics under ANIMA authority. |
| PostgreSQL session-level advisory locks | ADOPT / WRAP | Existing PostgreSQL capability; `pg_try_advisory_lock` gives immediate conflict without holding a transaction open. |
| Stripe-style idempotency pattern | REFERENCE | Same key returns the original result and parameter mismatch is rejected; ANIMA retains stricter unknown-side-effect handling. |
| Redis/Redlock | REJECT for foundational action locking | Expiring leases cannot fence ordinary Home Assistant/device side effects. |
| Temporal/Hatchet | DEFER | Durable future work belongs to Phase 10 and is outside this action boundary. |

Primary sources checked 2026-08-30: [PostgreSQL explicit locking](https://www.postgresql.org/docs/16/explicit-locking.html), [PostgreSQL advisory-lock functions](https://www.postgresql.org/docs/17/functions-admin.html), and [Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests?lang=curl).

## Evidence and limits

Focused tests cover stale preconditions, distinct-resource progress, provider refresh before and after
execution, non-queued resource conflicts, duplicate and mismatched idempotency
keys, policy denial, ambiguous connector timeout, verification failure, mixed
effects, and restart recovery. The durable PostgreSQL harness confirmed
migration/repeat behavior, one execution for an idempotent replay, and a real
non-blocking advisory-lock conflict. Full existing unit/static evidence remains
green on an x86-64 local-filesystem reproduction.

This checkpoint has no native ARM64/Raspberry Pi or physical-home evidence. The
durable database harness uses the real PostgreSQL store and advisory-lock
sessions. `scripts/verify_phase9_action_execution.py` additionally exercises
the coordinator through the pinned isolated Home Assistant 2026.8.2 virtual
entity, including a real same-resource race and post-action provider refresh.
This remains isolated x86-64 evidence and makes no physical-home or general
production-provider claim. Phase 9 remains implementation-complete pending
independent Architect review.
