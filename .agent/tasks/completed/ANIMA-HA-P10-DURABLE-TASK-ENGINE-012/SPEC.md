# ANIMA-HA-P10-DURABLE-TASK-ENGINE-012

Status: COMPLETE — PENDING ARCHITECT ACCEPTANCE

## Objective

Implement the bounded Phase 10 declarative durable-task engine authorized by
the Notion SSOT. Tasks create future cognition opportunities, not future
actions or executable work.

## Scope

One-shot, fixed-duration interval, and five-field cron schedules; timezone,
misfire, expiry, and DST policy; PostgreSQL task/run persistence; idempotent
creation; lease-based claims and bounded attempts; deterministic due events;
household-scoped lifecycle tools; and re-entry through Attention, Context, and
AgentRuntime.

## Exclusions

No Phase 11 behavior, durable workflow service, UI, voice, production external
connector, compensation, arbitrary executable payload, future tool call, or
stale authorization replay.

## Acceptance

Local static/tests/build/OPA and Phase 0–9 regressions pass; PostgreSQL
migration/repeat, concurrent claims, replay deduplication, and lease recovery
are evidenced; exact implementation and governed checkpoints pass hosted CI;
repository and Notion remain synchronized; Architect acceptance is still
pending.
