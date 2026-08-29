# ANIMA HA

ANIMA HA is an evidence-governed prototype of Anima, a local-first household intelligence layer built on Home Assistant. The repository contains the accepted Phase 0 runtime baseline, Phase 1 reality substrate, and Phase 2 deterministic Household Graph; cognition and household actions are intentionally not implemented yet.

## Phase 0, Phase 1, and Phase 2 baseline

This checkpoint provides:

- a `src/` Python package boundary for the future modular monolith;
- environment-only configuration with a committed, non-secret example;
- JSON structured application logging;
- a pinned `uv` project and lockfile;
- deterministic unit, lint, format, and type checks;
- a pgvector-ready PostgreSQL development service with a migration runner;
- a simulator framework entrypoint that reports readiness but does not process household events;
- an ANIMA-owned PostgreSQL event journal, truth observation model, deterministic reconciliation projection, failure tracking, and replay/rebuild path;
- an ANIMA-owned PostgreSQL canonical household graph with commissioned topology, recursive place traversal, aliases, provider references, Truth bindings, semantic queries, and journaled graph mutations;
- a single local validation command and a matching GitHub Actions workflow.

No memory, policy, agent cognition, Home Assistant adapter, plugin, UI, voice behavior, or external action capability is included.

## Supported baseline

- Python: CPython 3.12.x, constrained by `pyproject.toml` and `.python-version`.
- Host architectures: Linux ARM64 and x86-64 are the supported target shapes. This checkpoint is executed on x86-64; ARM64 support is established from image/package metadata and remains subject to native Pi execution in a later evidence pass.
- Infrastructure: Docker Engine with Compose v2 and a persistent Docker volume.
- Database: PostgreSQL 16.15 through the pinned pgvector image digest in `compose.yaml`. The image is extension-ready; Phase 0 does not create vector or household tables.

## Fresh-checkout workflow

Install `uv 0.12.7` using the official installer or package distribution, then run:

```bash
uv sync --locked --dev
cp .env.example .env
uv run --locked --group dev anima-validate
docker compose up -d db
uv run --locked --group dev anima-migrate
uv run --locked --group dev anima-sim --once
docker compose down
```

On filesystem mounts that cannot create virtual-environment symlinks (including the current SFTP-mounted workspace), set `UV_PROJECT_ENVIRONMENT` to a local-disk directory for the `uv sync` and `uv run` commands. This is a host filesystem limitation, not an application dependency.

The validation command runs format, lint, type, and unit checks. The database commands use only the local `.env` file and do not require household configuration.

For the full evidence workflow, see [`docs/PHASE-0-RUNTIME-BASELINE.md`](docs/PHASE-0-RUNTIME-BASELINE.md).
For the Phase 1 event/truth contracts and replay boundary, see [`docs/PHASE-1-REALITY-SUBSTRATE.md`](docs/PHASE-1-REALITY-SUBSTRATE.md).
For the Phase 2 graph contracts, prior-art decisions, commissioning, and evidence boundary, see [`docs/PHASE-2-HOUSEHOLD-GRAPH.md`](docs/PHASE-2-HOUSEHOLD-GRAPH.md).

## Authority

The adopted goal and operating workflow live in [`PROJECT_GOAL.md`](.agent/PROJECT_GOAL.md), [`AGENTS.md`](AGENTS.md), and `.agents/`. Product implementation remains bounded by the Authority records in `.agent/`.
