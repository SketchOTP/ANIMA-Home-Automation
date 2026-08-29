# Phase 1 evidence — ANIMA-HA-P1-REALITY-SUBSTRATE-003

## Starting state

- Starting SHA: `e68fc6240e5ae922f4e289b9ccdb7ed9f9babfe0`.
- Starting branch: `main`, clean, tracking `origin/main`.
- Phase 0 acceptance and its CI checkpoint were independently verified before this directive.

## Prior-art and dependency decision

- PostgreSQL 16 + existing Psycopg boundary: ADOPT/WRAP.
- ANIMA event/observation contracts, journal, reducer, projection, retry, replay, and simulator scenarios: BUILD.
- Python `eventsourcing`: DEFER; BSD-3-Clause and PostgreSQL-capable, but aggregate abstractions do not fit ANIMA-owned external observation/truth semantics without coupling.
- NATS JetStream: DEFER; durable replay and at-least-once delivery are useful later, but a second persistence/delivery layer is not justified in Phase 1.
- KurrentDB/EventStoreDB: REJECT for prototype foundation; current Kurrent License v1 is not OSI-approved and a separate service is unnecessary here.

## Validation evidence

- Unit/static: PASSED — Ruff, strict mypy, and 11 pytest tests.
- Build: PASSED — package wheel and source distribution built with Python 3.12.3 on local filesystem.
- PostgreSQL integration: PASSED — migration `0002_phase1_reality_substrate`; 8 concurrent duplicate attempts produced one logical insert; source-id duplicate deduplicated; append-only trigger rejected update; sequence-aware out-of-order, stale, unknown, unavailable, and multi-source conflict cases resolved correctly; injected projection failure retained the event and succeeded on retry; rebuild matched live resolution.
- Restart/persistence: PASSED — PostgreSQL 16.15 container restarted and journal/truth rows remained; migration repeat applied zero migrations.
- Simulator: PASSED — synthetic `duplicate` scenario emitted one non-deduplicated and one deduplicated result; no external or physical-home interaction.
- Implementation checkpoint: `0ee72b736aa27e1b52d652eafb8e045e4b892148`.
- CI: PASSED — GitHub Actions run `33252987351` completed successfully for the implementation checkpoint.

## Evidence limitations

- PostgreSQL and simulator execution is synthetic and x86-64 only.
- ARM64 remains Phase 0 manifest/package metadata evidence; no native Raspberry Pi run is claimed.
- No real Home Assistant, household, physical-action, backup/restore, or cloud behavior is claimed.
