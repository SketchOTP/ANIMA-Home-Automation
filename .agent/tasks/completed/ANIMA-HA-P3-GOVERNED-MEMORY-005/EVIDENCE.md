# Evidence — ANIMA-HA-P3-GOVERNED-MEMORY-005

## Starting state

- Starting checkpoint: `2b2d3613487dea2facc808c1313864a319af1607`
- Starting branch: `main`, tracking `origin/main`; working tree clean.
- Phase 2 was independently accepted. No active task packet or uncommitted user work was present.

## Dependency decisions

- BUILD: ANIMA memory contracts, lifecycle, precedence, retrieval, audit, and routine model.
- ADOPT/WRAP: existing PostgreSQL 16/Psycopg and PostgreSQL full-text search as a disposable local lexical index.
- DEFER/WRAP candidate: Mem0 OSS 2.0.19; not installed, not canonical, and no LLM extraction enabled.
- DEFER: FastEmbed 0.8.0, direct pgvector embeddings, LangGraph, Letta, Graphiti, and River.
- See `docs/PHASE-3-GOVERNED-MEMORY.md` and `.agent/EXTERNAL.md` for current primary-source qualification.

## Implemented

- `0004_governed_memory.sql`: canonical memory, derived search index, and versioned routine tables.
- `anima_ha.memory`: immutable typed records, provenance, confidence, deterministic precedence, lifecycle transitions, correction/supersession, expiry, retraction, household isolation, bounded filtering, index rebuild, and degraded lexical fallback.
- `anima_ha.routines`: journal-derived bucket probabilities with confidence, sample/time provenance, versioning, and deterministic rebuild/update.
- `anima-sim --once --scenario memory`: synthetic memory/routine demonstration with `authority_surface=none`.
- `scripts/verify_phase3_postgres.py`: integration evidence harness.

## Validation evidence

- Migration initialization: PASSED — `0004_governed_memory` applied once.
- Migration repeat: PASSED — no additional migrations applied.
- Unit tests: PASSED — `19 passed`.
- Ruff format/lint: PASSED.
- Strict mypy: PASSED — no issues in 21 source files including Phase 3 integration script.
- Package build: PASSED — wheel and sdist built from an isolated local-disk checkout. Direct SFTP build was BLOCKED by the known `.venv` symlink canonicalization limitation (`os error 38`).
- PostgreSQL integration: PASSED — canonical records, provenance, explicit-over-inferred precedence, active temporary context, correction/supersession, automatic/manual expiration, retraction, subject/graph filters, cross-household isolation, index clear/rebuild, fallback, Truth boundary, journal audit, routine rebuild/update.
- Phase 1 regression: PASSED — existing PostgreSQL reality harness.
- Phase 2 regression: PASSED — existing PostgreSQL graph harness.
- Simulator: PASSED — memory and graph scenarios.
- Restart: PASSED — `pg_isready` accepted connections; counts before/after restart were `40` memories and `4` routines.
- Public safety: PASSED — credential-like scan found no committed secret material; `git diff --check` passed. `.env.example` remains a documented non-secret development placeholder.
- Network/privacy: PASSED at static/local evidence level — Phase 3 runtime imports only local ANIMA code plus Psycopg; no Mem0/FastEmbed/PostHog/HTTP client was adopted. Integration connections observed only the local PostgreSQL endpoint. Native network-egress tracing for unadopted dependencies is NOT APPLICABLE.

## Evidence boundary

- E4 regression-protected: unit/static/build and Phase 1/2 regression checks.
- E3 target-tested: synthetic PostgreSQL memory/routine integration on x86-64.
- E2 reproduced: synthetic simulator scenarios.
- E1 observed: ARM64 remains prior manifest/package metadata evidence only; no native Raspberry Pi execution or resource measurement.
- No real-home, Home Assistant, Luna, external-service, physical-device, agent cognition, or policy/permission claim is made.

## Final checkpoint

- Implementation checkpoint: recorded in the final Git history after the implementation commit.
- Final governed checkpoint: recorded here and in Notion after the Authority/documentation update and push.
- Phase 4 Identity/Policy and later behavior were not implemented.
