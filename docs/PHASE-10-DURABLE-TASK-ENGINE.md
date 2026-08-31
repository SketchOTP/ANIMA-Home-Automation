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

Task creation is household-scoped, policy-gated through the trusted native
Phase 5 plugin manifest, and idempotent by creation key plus parameter
fingerprint. Listing and mutation re-check household ownership. Pause, resume,
cancel, expiry, missed occurrences, leases, attempts, and run outcomes are
durable and auditable. Scheduled events contain only bounded intent and
provenance; arbitrary executable payloads are rejected recursively.

The task engine creates an opportunity for fresh cognition; it does not create
a future action. Any later consequential action still passes through the
Phase 9 coordinator, including latest-state refresh, trusted preconditions,
policy reauthorization, idempotency, provider execution context, and
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

## Evidence limits

Unit evidence covers schedule validation, DST policy, idempotent creation,
household scoping, concurrent claims, leases/reclaim, deterministic event
replay, misfire handling, and task lifecycle. PostgreSQL migration/repeat and
multi-worker evidence are provided by `scripts/verify_phase10_durable_tasks.py`
when run against the local pinned database. Hosted CI proves reproducibility
of the repository test/build checks, not native ARM64 execution, physical-home
behavior, or production-scale scheduler capacity. Those remain future evidence
items.
