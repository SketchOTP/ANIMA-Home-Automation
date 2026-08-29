# Phase 2 evidence — ANIMA-HA-P2-HOUSEHOLD-GRAPH-004

- Verdict: PASS / COMPLETE.
- Starting SHA/state: `8bb642ce5108a1bfab733e89f5928ef3e9d80f6a`, clean `main`,
  `origin/main` aligned.
- Resulting SHA: `ed261e8a3bc794ededdc3084f63b816152988820`; remote `main` contains
  this SHA. GitHub Actions run `33261359336` completed successfully against it.
- Prior art: PostgreSQL recursive CTEs ADOPT/WRAP; AGE REJECT; NetworkX REJECT
  as storage; Brick and Haystack REFERENCE/ADAPT; Graphiti DEFER.
- Migration `0003_household_graph` applied and repeat execution was a no-op.
- Unit/static/build: Ruff passed, strict mypy passed for 17 source files,
  `16 passed`, and wheel/source distribution built successfully.
- PostgreSQL integration: `scripts/verify_phase2_postgres.py` passed recursive
  topology, commissioning idempotency, Truth provenance, provider
  many-to-one/capability mapping and explicit remap, rename/alias preservation,
  and graph journal audit.
- Phase 1 regression: `scripts/verify_phase1_postgres.py` passed with graph
  events present; truth statuses and rebuild remained green.
- Simulator: `anima-sim --once --scenario graph` passed with 2 exterior
  entrances and 12 places.
- Restart: PostgreSQL restart preserved 27 graph nodes and 113 journal events.
- Resource: PostgreSQL observed at approximately 0.37% CPU and 25.27 MiB on
  the x86-64 host; this is not a Pi measurement.
- Public safety: repository scan and diff checks passed; no credentials,
  tokens, private runtime state, or machine-specific household configuration
  were published.

Evidence limits: unit/static checks are not runtime proof; integration and
simulator evidence is synthetic x86-64 only; ARM64 remains manifest/package
metadata evidence; no Home Assistant, physical-home, or native Pi claim is
made. Phase 3 Memory Service and later behavior were not implemented.
