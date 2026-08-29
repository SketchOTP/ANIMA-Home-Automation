# Major Project Record

Use this ledger for major architecture decisions, strategic reversals, project milestones, important failures, governance migrations, and other events a future Architect/Coder must understand.

---

## ANIMA-HA-P0-RUNTIME-BASELINE-002 — Phase 0 runtime baseline

- Date: 2026-08-28/29
- Decision: Adopt Python 3.12.x, uv lockfiles, pinned Ruff/pytest/mypy tooling, Psycopg behind an ANIMA database boundary, and a pinned pgvector PostgreSQL 16 image for runtime-only persistence proof.
- Boundary: Phase 0 infrastructure only; no household intelligence or Phase 1 product semantics.
- Evidence: Full checks/build pass on an allowlisted local-filesystem reproduction; x86-64 database health/restart/persistence pass; ARM64 is manifest/wheel evidence only.
- Recheck: Before native Pi acceptance, image refresh, or Phase 1 schema/service expansion.

---

## AUTHORITY-BOOTSTRAP-001 — Authority 3.0 adopted for ANIMA HA

- Date: 2026-08-28
- Type: GOVERNANCE
- Related directive/outcome: AUTHORITY-BOOTSTRAP-001

### Context

ANIMA HA is a new project with an adopted working-prototype goal and no existing implementation state. A durable Architect → Codex → evidence → Architect loop is required before implementation begins.

### Decision / event

Applied Authority 3.0 as the project governance contract. Installed the root router, reusable Codex workflow, project-state/history ledgers, evidence/safety contracts, external-discovery workflow, and a project-specific Architect startup prompt.

### Evidence

Authority 3.0 Complete Installation Package retrieved from the connected Notion Authority documentation; initial project directory inspection found no pre-existing files or repository state.

### Consequence

Future work must begin by reading the mandatory state kernel, resolving one bounded directive, preserving append-only evidence, qualifying significant dependencies, and reporting the canonical Codex result. The adopted project goal may not be silently narrowed.

---

## ANIMA-HA-P0-GOVERNANCE-BASELINE-001 — Public governed repository baseline reconciled

- Date: 2026-08-28
- Type: MILESTONE
- Related directive/outcome: ANIMA-HA-P0-GOVERNANCE-BASELINE-001

### Context

The local Authority bootstrap predated discovery of the existing public GitHub repository and incorrectly recorded Git/GitHub as not created.

### Decision / event

Adopted the existing remote `main` history as the local parent, corrected the local repository/profile/checkpoint state, and published the reviewed Authority governance baseline without product implementation.

### Evidence

Remote `main` was observed at `088b267467fff93bfd225b9a94a6f4999759fb9f` with a clean two-file tree. Governance baseline commit `6fbabc892f53876fd94614ccc531dc7478a80288` preserves that parent. SSH fetch and public-safety review passed; the machine-specific local GVFS path was removed from the publishable profile, and no secrets or runtime data were found.

### Consequence

`main` now has one coherent governance history through `6fbabc892f53876fd94614ccc531dc7478a80288`. Product implementation remains deferred until the Architect reviews this checkpoint and issues a separate bounded directive.

## ANIMA-HA-P1-REALITY-SUBSTRATE-003 — Phase 1 reality substrate

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Related directive/outcome: `ANIMA-HA-P1-REALITY-SUBSTRATE-003`

### Decision / event

Adopted PostgreSQL 16 through the existing Psycopg boundary as the canonical Phase 1 event journal and derived truth substrate. Built the ANIMA event/observation contracts, deterministic reconciliation, projection retry boundary, and replay/rebuild. Deferred NATS/JetStream and aggregate event-sourcing frameworks; rejected KurrentDB/EventStoreDB as the prototype foundation.

### Evidence

Unit/static/build validation and synthetic x86-64 PostgreSQL integration passed for concurrent deduplication, append-only enforcement, source ordering, uncertainty/conflict semantics, journal-first projection retry, restart persistence, and rebuild equivalence. Full checkpoint details are in the completed task packet.

### Consequence

Phase 2 can consume a stable provider-independent reality substrate. No Household Graph, memory, policy, Home Assistant, Luna, or later behavior is included.
