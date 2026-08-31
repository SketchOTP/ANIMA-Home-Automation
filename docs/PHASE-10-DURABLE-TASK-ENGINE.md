# Phase 10 — Durable Task Engine

Status: implemented, tested, and pending Architect acceptance.

Phase 10 adds a bounded, declarative future-work substrate. A task stores a
human-readable objective, household-scoped references, schedule, provenance,
and creation idempotency key. It never stores a tool name, executable
arguments, callable, command, connector, or old authorization. A due task is
claimed once and emits one deterministic, guaranteed `scheduled_reasoning_due`
journal event. The existing Attention → Context → Policy → Agent boundaries
then decide whether and how cognition proceeds.

## Architecture

`DurableTask`, `TaskSchedule`, and `DurableTaskRun` live in
`src/anima_ha/tasks.py`. PostgreSQL migration `0011_durable_tasks.sql` stores
tasks and occurrence runs. Claiming uses short `FOR UPDATE SKIP LOCKED`
transactions and database time; no transaction spans event delivery,
cognition, or provider execution. A lease and bounded attempt count support
restart recovery. Run IDs and source event IDs are deterministic for
`(task_id, scheduled_for)`, so journal uniqueness deduplicates replay.

The small `anima-task-worker` entry point dispatches due events once by default
or polls with `--forever`. `ScheduledCognitionBridge` is an adapter into the
existing Attention, ContextBroker, and AgentRuntime layers; it does not grant
future policy or bypass fresh state and final authorization.

## Schedule contract

Supported schedule kinds are `ONCE`, fixed-duration `INTERVAL`, and five-field
`CRON`. Every schedule carries an IANA timezone, UTC-normalized start time,
optional expiry, bounded misfire grace, and explicit misfire policy:

- `FIRE_ONCE_NOW`: emit the overdue occurrence once;
- `SKIP`: mark a late recurring occurrence `MISSED`;
- `COALESCE_ONE`: collapse overdue recurring work into one occurrence.

Cron calculation is wrapped behind `RecurrenceCalculator` and currently uses
`croniter==6.2.4`. Spring-forward nonexistent wall times normalize to the
first valid instant returned by the recurrence engine. The selected policy
emits one wall-clock occurrence during fall-back rather than dispatching both
folds. This is a policy choice, not a claim that all calendars share the same
semantics.

## Lifecycle and safety

Task creation and lifecycle mutation are household-scoped, policy-gated
through the Phase 5 gateway, and classified by an ANIMA-owned execution
boundary as `POLICY_GATED_INTERNAL`. Only the Core allowlist can assign this
boundary to the built-in task tools; raw plugin metadata cannot create an
exemption from Phase 9. Listing and reads are `READ_ONLY`; physical/provider
side effects remain `COORDINATED_CONSEQUENTIAL`.

AgentRuntime injects a trusted invocation context containing the current
household, principal, episode, tool-request identity, ordinal, origin, and
system idempotency identity. Creator provenance and creation idempotency are
not model-controlled task arguments. Creation remains idempotent by that
system key plus parameter fingerprint. Listing and mutation re-check
household ownership. Pause, resume, cancel, expiry, missed occurrences,
leases, attempts, and run outcomes are durable and auditable. PostgreSQL and
in-memory lifecycle guards agree, and a dispatch transition requires the
current worker's live unexpired claim. Scheduled events contain only bounded
intent and provenance; arbitrary executable payloads are rejected recursively.

The task engine creates an opportunity for fresh cognition; it does not create
a future action. Due-time cognition uses a new ContextPacket and does not
reuse creation-time context or creator identity as future authentication. Any
later consequential action still passes through the Phase 9 coordinator,
including latest-state refresh, trusted preconditions, policy
reauthorization, idempotency, provider execution context, and
observation-first verification.

## Dependency decision

PostgreSQL/Psycopg remains the durable substrate and is wrapped by ANIMA-owned
store interfaces. `croniter==6.2.4` is the only Phase 10 dependency and is
wrapped narrowly for cron iteration. Hatchet and Temporal remain deferred
because they introduce separate durable workflow/server boundaries beyond this
bounded task model. APScheduler remains reference-only; its callable/job
orientation does not replace ANIMA's declarative payload and governance
boundary. Phase 11 scheduling, UI/voice, compensation, and production
connectors remain unauthorized.

## Evidence

The `ANIMA-HA-P10-TASK-POLICY-INTEGRATION-012H` continuation adds real
AgentRuntime task scheduling through Phase 5 and policy, ALLOW/DENY/
confirmation/stronger-auth coverage, trusted provenance/idempotency coverage,
in-memory/PostgreSQL lifecycle parity, stale-worker lease rejection,
cancellation cleanup, and a PostgreSQL scheduled-cognition chain proving a
fresh due-time ContextPacket. The exact implementation and governed
checkpoints and hosted CI runs are recorded in the completed Authority packet
and Notion SSOT.

## Evidence limits

Unit evidence covers schedule validation, DST policy, idempotent creation,
household scoping, concurrent claims, leases/reclaim, deterministic event
replay, misfire handling, and task lifecycle. PostgreSQL migration/repeat and
multi-worker evidence are provided by `scripts/verify_phase10_durable_tasks.py`
when run against the local pinned database. Hosted CI proves reproducibility
of the repository test/build checks, not native ARM64 execution, physical-home
behavior, or production-scale scheduler capacity. Those remain future evidence
items.
