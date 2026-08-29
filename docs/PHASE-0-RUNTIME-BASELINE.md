# Implementation Phase 0 — Runtime Baseline

This document defines the reproducible developer workflow for the Phase 0 checkpoint. It does not define household behavior.

## Repository boundaries

```text
src/anima_ha/          ANIMA-owned Python package boundary
src/anima_ha/config.py environment configuration, no household values
src/anima_ha/logging_setup.py JSON application logging boundary
src/anima_ha/db/       runtime-only database connection and migration boundary
src/anima_ha/simulator.py future synthetic-input entrypoint, no event semantics
tests/                 deterministic unit tests
scripts/               documented local validation wrapper
compose.yaml           isolated PostgreSQL development service
.github/workflows/     CI for the same validation command
```

Future Phase 1 modules must be added behind ANIMA-owned interfaces and may not turn this baseline migration into a product schema without a new directive.

## Fresh checkout

1. Install `uv 0.12.7` from the official uv distribution.
2. Run `uv sync --locked --dev`.
3. Copy `.env.example` to `.env`. The example password is local-development-only and is not a secret.
4. Run `uv run --locked --group dev anima-validate`.
5. Start the isolated database with `docker compose up -d db`.
6. Wait for `docker compose ps` to report `healthy`.
7. Run `uv run --locked --group dev anima-migrate` twice. The first invocation applies `0001_runtime_baseline`; the second applies zero migrations.
8. Run `uv run --locked --group dev anima-sim --once` and confirm the JSON readiness record.
9. Stop with `docker compose down`; retain the named volume when testing persistence, or use `docker compose down -v` only when intentionally resetting local development state.

For the current SFTP-mounted development workspace, use for example `UV_PROJECT_ENVIRONMENT=/tmp/anima-ha-venv uv sync --locked --dev` and prefix the `uv run` commands with the same variable. A normal local checkout uses the default `.venv`.

## Configuration and secrets

Runtime settings are read from environment variables. `.env` is ignored. No credentials, tokens, household identifiers, or machine paths belong in the repository. Deployment-specific secret storage is deferred until the service boundaries requiring it are authorized.

## Database boundary

The image is pinned by digest and provides PostgreSQL 16 plus the pgvector extension package for future memory work. Phase 0 uses only two runtime metadata tables required to prove migration bookkeeping and version continuity. It does not enable vector search and does not create Event Journal, Truth/State, graph, memory, policy, or household tables.

The named Docker volume is the persistence boundary. A controlled `docker compose restart db` must leave the migration marker and runtime metadata present. Backup/restore of prototype-critical state is a later phase concern; this checkpoint documents the volume boundary but does not claim a backup implementation.

## Evidence limits

- Local execution evidence in this checkpoint is x86-64 only.
- Image manifest metadata establishes an ARM64 path; it is not native Raspberry Pi execution evidence.
- CI configuration is committed workflow evidence until GitHub runs it.
- The development password in `.env.example` is intentionally non-secret example material; real deployments must inject secrets out of band.
