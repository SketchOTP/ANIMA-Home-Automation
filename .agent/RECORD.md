# Major Project Record

Use this ledger for major architecture decisions, strategic reversals, project milestones, important failures, governance migrations, and other events a future Architect/Coder must understand.

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

Remote `main` was observed at `088b267467fff93bfd225b9a94a6f4999759fb9f` with a clean two-file tree. SSH fetch and final remote verification passed. Public-safety review found and removed the machine-specific local GVFS path from the publishable profile; no secrets or runtime data were found.

### Consequence

`main` now has one coherent governance history. Product implementation remains deferred until the Architect reviews this checkpoint and issues a separate bounded directive.
