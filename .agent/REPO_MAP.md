# Repository Map

Last verified against: IMPLEMENTATION PHASE 2 HOUSEHOLD GRAPH 2026-08-29

## Entry points

- `anima-validate` — deterministic local format/lint/type/unit gate.
- `anima-migrate` — runtime-only ordered SQL migration runner.
- `anima-sim` — synthetic reality-substrate and commissioned graph scenario entrypoint; no household behavior.

## Major modules / packages

- `src/anima_ha/config.py` — environment-backed runtime configuration.
- `src/anima_ha/logging_setup.py` — JSON structured logging boundary.
- `src/anima_ha/db/` — PostgreSQL connection and runtime migration boundary.
- `src/anima_ha/simulator.py` — future synthetic-input entrypoint without event semantics.
- `src/anima_ha/events.py` — immutable normalized event and observation contracts.
- `src/anima_ha/journal.py` — PostgreSQL journal, truth projection, failure tracking, and rebuild.
- `src/anima_ha/truth.py` — pure deterministic reconciliation and uncertainty statuses.
- `src/anima_ha/graph.py` — canonical graph contracts, validation, PostgreSQL repository, semantic queries, Truth bindings, aliases, provider references, and mutation audit.
- `src/anima_ha/fixtures.py` — deterministic synthetic commissioning topology.
- `tests/` — deterministic Phase 0/Phase 1/Phase 2 unit tests.

## Important interfaces / contracts

- `.agent/PROJECT_GOAL.md` — adopted ANIMA HA goal, scope, non-goals, constraints, and acceptance boundary.
- `.agent/INDEX.md` — mandatory project-state retrieval map.
- `.agents/skills/authority/SKILL.md` — reusable Codex operating workflow.
- `AGENTS.md` — root Authority router.

## Tests

- `uv run --locked --group dev pytest` — Phase 0/1/2 unit tests.
- `uv run --locked --group dev python scripts/verify_phase1_postgres.py` — synthetic PostgreSQL integration harness.
- `uv run --locked --group dev python scripts/verify_phase2_postgres.py` — synthetic PostgreSQL graph integration harness.

## Generated / cache / build areas

- `.gitignore` — excludes local/private runtime material, caches, build outputs, and secrets.

## Governance / agent files

- `AGENTS.md`
- `.agents/`
- `.agent/`
- `.gitignore`
- `LICENSE`

## Phase 0 infrastructure

- `compose.yaml` — isolated, health-checked pgvector/PostgreSQL service with named persistence volume.
- `docs/PHASE-0-RUNTIME-BASELINE.md` — setup, boundaries, and evidence limits.
- `docs/DEPENDENCY-QUALIFICATION.md` — dependency decisions, sources, licenses, and recheck triggers.
- `.github/workflows/ci.yml` — hosted CI invoking the same validation command.

The `src/anima_ha/db` area owns ordered migrations. Phase 1 journal/truth behavior is in `events.py`, `journal.py`, and `truth.py`; Phase 2 graph behavior is in `graph.py` and `fixtures.py`. Neither phase implements memory, policy, Home Assistant, or household-specific provider behavior.

- `docs/PHASE-2-HOUSEHOLD-GRAPH.md` — canonical graph architecture, prior art, commissioning, query surface, and evidence boundaries.

## Known sensitive/high-risk areas

- Future Home Assistant, household state, memory, identity/authority, credentials, external connectors, physical actions, and audit data require explicit boundaries and qualification.

GitHub baseline parent: `088b267467fff93bfd225b9a94a6f4999759fb9f`. This map is not exhaustive; update it when repository structure or understanding changes materially and is verified.
