# Current Project State

Last updated: 2026-08-29

## Current stage

IMPLEMENTATION PHASE 1 — REALITY SUBSTRATE COMPLETE

## Current objective

Complete the deterministic PostgreSQL-backed event journal and Truth/State substrate required before Household Graph and cognition phases.

## Active directive

NONE

## Current verified state

- The project directory was empty before this bootstrap.
- Phase 0 now contains only runtime/engineering baseline code; no household intelligence or product behavior is implemented.
- The local project is a Git repository on `main`, configured with the required identity and connected to `git@github.com:SketchOTP/ANIMA-Home-Automation.git`.
- The existing GitHub baseline commit is `088b267467fff93bfd225b9a94a6f4999759fb9f` and contains `.gitignore` and `LICENSE`.
- The requested ANIMA HA goal is adopted at the prototype boundary `ANIMA_HA_PROTOTYPE_GOAL_COMPLETE`.
- The canonical Notion SSOT is the ANIMA HA Authority, Product Specification & Cold-Start Handoff page.
- Authority 3.0 governance files are installed and published in governance baseline commit `6fbabc892f53876fd94614ccc531dc7478a80288`.
- Python 3.12.x, uv 0.12.7, pinned development tooling, PostgreSQL 16.15/pgvector 0.8.6, migrations, structured logging, simulator scenarios, normalized event/observation contracts, append-only journal, deterministic truth projection, failure tracking, rebuild, tests, and CI are implemented in the current working tree.
- Phase 1 event identity, source deduplication, journal position, event/record time, source sequence, provenance, freshness, explicit unknown/unavailable/conflict states, projection retry, and replay/rebuild are covered by unit and x86-64 PostgreSQL integration evidence.

## Current hypotheses / unknowns

- Native Raspberry Pi execution has not yet been performed; ARM64 support is evidenced by image manifest and wheel metadata only.
- This SFTP-mounted workspace cannot reliably create a `.venv` symlink or complete mypy traversal; an allowlisted local-filesystem copy passes the full validation and build gate.
- No native Raspberry Pi run has been performed; ARM64 remains manifest/package evidence only.
- The canonical journal and truth projection are PostgreSQL/Psycopg implementations behind ANIMA-owned interfaces. NATS/JetStream and aggregate event-sourcing frameworks remain deferred.

## Current blockers

- NONE currently known for Phase 1.
- Household Graph, memory, policy, Home Assistant, Luna, plugins, action execution, durable tasks, UI, and voice remain explicitly out of scope.

## Latest accepted evidence

- `AUTHORITY-BOOTSTRAP-001`: governance package installed and inspected; `E2_REPRODUCED` for the bootstrap artifact set only. This is not implementation or prototype acceptance evidence.
- Remote baseline `088b267467fff93bfd225b9a94a6f4999759fb9f`: observed and preserved as the Git history parent.
- Phase 0 acceptance checkpoint is `e68fc6240e5ae922f4e289b9ccdb7ed9f9babfe0`; GitHub Actions run `33232686789` passed.
- Phase 1 implementation checkpoint is `0ee72b736aa27e1b52d652eafb8e045e4b892148`; GitHub Actions run `33252987351` passed for that exact SHA.
- Phase 1 evidence is recorded in `.agent/tasks/completed/ANIMA-HA-P1-REALITY-SUBSTRATE-003/EVIDENCE.md`.

## Current risks

- Native Raspberry Pi runtime/resource qualification and backup/restore remain future evidence items.
- Truth projection semantics will need extension when Household Graph, memory, and Home Assistant source adapters arrive.
- Public-repository publication requires continued exclusion of secrets, credentials, and runtime state.

## Next Architect decision point

Architect review of the Phase 1 evidence is required before a separate Phase 2 directive. No Phase 2 or later behavior is authorized by this directive.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.
