# Phase 2 evidence log

## Observed evidence

- Starting SHA/state: `8bb642ce5108a1bfab733e89f5928ef3e9d80f6a`, clean `main`,
  `origin/main` aligned.
- Prior-art qualification: PostgreSQL recursive CTEs ADOPT/WRAP; AGE REJECT;
  NetworkX REJECT as storage; Brick and Haystack REFERENCE/ADAPT; Graphiti
  DEFER. No new infrastructure service was introduced.
- Migration: `0003_household_graph` applied once, then repeated with
  `applied=[]`.
- Pure/unit: `16 passed`; contracts cover commissioned fixture, containment
  cycle, dangling references, alias collisions, and invalid entrance endpoints.
- PostgreSQL integration: `scripts/verify_phase2_postgres.py` passed semantic
  queries, recursive resource traversal, idempotent commissioning, Truth
  provenance, provider capability/many-to-one mapping and explicit remap,
  canonical rename/alias preservation, and journal mutation audit.
- Phase 1 regression: `scripts/verify_phase1_postgres.py` passed after graph
  events were present; existing truth statuses and rebuild remained green.
- Static/build: mypy passed for 17 source files; Ruff passed; pytest passed;
  source distribution and wheel built successfully.
- Simulator: `anima-sim --once --scenario graph` passed with 2 exterior
  entrances and 12 places.
- Restart: PostgreSQL restart preserved 27 graph nodes and 113 journal events.
- Resource: PostgreSQL container observed at approximately 0.37% CPU and
  25.27 MiB on this x86-64 host; not a Pi measurement.
- Public safety: diff check and repository scan found no credentials, tokens,
  private runtime state, or machine-specific household configuration.

## Evidence limits

Unit and static evidence are not runtime proof. PostgreSQL evidence is synthetic
and x86-64 only. Simulator evidence is not Home Assistant or physical-home
evidence. ARM64 remains the accepted Phase 0 manifest/package metadata level;
native Raspberry Pi execution is not claimed. No Phase 3 Memory Service or
later behavior was implemented.
