# Evidence packet

## Status

Complete — pending Architect acceptance. Architect disposition remains
`CONTINUE` under `ANIMA-HA-P10-TASK-POLICY-INTEGRATION-012H`.

- Starting governed checkpoint: `21dde3cddc3ea4aa5af3e59e6a0334b62d37a7a2`;
  hosted CI `33418246958` passed.
- Implementation checkpoint: `27f7c3fb8ce53c4eb988d7de22c63672770998a8`;
  hosted CI `33425928381` passed on that exact SHA.
- Final governed checkpoint: this subsequent evidence-closure commit; exact
  SHA and hosted CI are recorded in the Notion SSOT after publication.

## Architecture evidence

- `src/anima_ha/tasks.py` implements typed declarative task, schedule, and run
  contracts; recursive executable-key rejection; deterministic IDs; in-memory
  and PostgreSQL stores; leases/attempts; due-event dispatch; lifecycle tools;
  and the scheduled cognition bridge.
- `src/anima_ha/db/migrations/0011_durable_tasks.sql` persists task definitions
  and occurrence runs with uniqueness, status checks, indexes, and leases.
- `src/anima_ha/plugins.py` normalizes the ANIMA-owned execution boundary and
  forwards trusted household/provenance/idempotency context to native task
  capabilities while preserving provider execution-context forwarding.
- `src/anima_ha/agent.py` routes policy-gated task mutations through the Phase 5
  gateway and preserves the Phase 9 consequential-tool path; scheduled
  cognition still re-enters fresh existing boundaries.
- `src/anima_ha/tasks.py` enforces equivalent in-memory/PostgreSQL lifecycle
  guards, live claimant leases, and cancellation cleanup for dispatching runs.

## Required scenarios

`tests/test_tasks.py` covers declarative schedule validation, DST spring-forward
and fall-back policy, trusted AgentRuntime task routing, policy outcomes,
provenance/idempotency replay, lifecycle parity, deterministic guaranteed
events, concurrent worker claims, lease reclaim/replay, cancellation races,
misfire, pause/resume/cancel, and household isolation. Existing Phase 9 tests
cover observation-first action verification and ambiguous dispatch. The
PostgreSQL script covers migration/repeat, real AgentRuntime scheduling,
scheduled cognition with a fresh ContextPacket, lifecycle parity, stale-worker
and cancellation races, two-worker claim race, journal event deduplication,
and lease recovery.

### 012H validation

- Real AgentRuntime schedule/lifecycle path and policy matrix: PASSED; task
  mutations persisted only on ALLOW and no Phase 9 physical action record was
  created for task persistence.
- Trusted provenance/idempotency replay and creator-identity non-authority:
  PASSED.
- PostgreSQL lifecycle parity, stale-worker rejection, cancellation cleanup,
  no-orphan check, deterministic due-event replay, and fresh scheduled
  cognition chain: PASSED.
- Full local regression and isolated HA evidence: PASSED; exact implementation
  CI is recorded above.

## Limits

Evidence is local x86-64 and isolated. No native ARM64/Pi, physical-home,
production-scale scheduler, production connector, high-risk action, or Phase 11
evidence is claimed. Phase 10 remains pending Architect acceptance.
