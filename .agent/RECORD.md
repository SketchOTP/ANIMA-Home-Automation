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

## ANIMA-HA-P2-HOUSEHOLD-GRAPH-004 — Canonical semantic household graph

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Related directive/outcome: `ANIMA-HA-P2-HOUSEHOLD-GRAPH-004`

### Decision / event

Adopted an ANIMA-owned relational canonical graph on PostgreSQL 16 with
recursive CTE traversal, typed semantic relationships, commissioned UUID
identity, separate provider references, aliases, Truth bindings, and Phase 1
journal mutation audit. Brick/Haystack are reference material only; AGE and
NetworkX are not canonical persistence; Graphiti is deferred.

### Evidence

Pure validation and x86-64 PostgreSQL integration cover the synthetic topology,
cycle/reference/entrance validation, recursive resources, aliases, provider
mapping/remap, Truth provenance, idempotent commissioning, audit, and restart.
No Home Assistant or physical-home evidence is claimed.

### Consequence

Phase 3 may consume semantic household identity after Architect review. Memory,
policy, Home Assistant, Luna, plugins, actions, durable tasks, UI, and voice
remain out of scope until separately authorized.

## ANIMA-HA-P3-GOVERNED-MEMORY-005 — Governed local memory

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Related directive/outcome: `ANIMA-HA-P3-GOVERNED-MEMORY-005`

### Decision / event

Built canonical ANIMA memory on the existing PostgreSQL/Psycopg boundary with
typed provenance, deterministic precedence, append-oriented lifecycle, and a
disposable local lexical index. Added a deterministic journal-derived routine
model. Mem0, local embeddings, LangGraph, Letta, Graphiti, and River remain
deferred; no new service was introduced.

### Evidence

Contract/unit checks and synthetic x86-64 PostgreSQL integration passed for
memory lifecycle, explicit/inferred precedence, temporary expiry, retraction,
cross-household isolation, index rebuild/fallback, Truth separation, journal
audit, routine rebuild/update, and restart persistence. Phase 1/2 regressions,
full validation, package build, simulator, and public-safety checks passed.

### Consequence

Phase 4 may consume relevant governed memory after Architect review. Identity,
policy, permissions, Home Assistant, Luna, plugins, actions, durable tasks,
UI, and voice remain out of scope.

## ANIMA-HA-P4-IDENTITY-POLICY-006 — Deterministic identity and policy milestone

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Decision: Adopt and wrap local OPA/Rego 1.20.1 behind ANIMA-owned identity, intent, risk, confirmation, audit, and fail-closed contracts.
- Evidence: OPA policy tests, x86-64 PostgreSQL integration, restart persistence, simulator, Phase 1–3 regressions, static validation, package validation, and public-safety scan passed.
- Boundary: No policy-write runtime API, memory authority, Home Assistant, Luna, plugin, action-execution, physical identity, or real-home behavior was introduced.
- Consequence: Phase 5 Plugin Runtime remains gated on independent Architect review of this checkpoint.

## ANIMA-HA-P5-PLUGIN-CAPABILITY-RUNTIME-007 — Governed capability boundary

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Decision: Build an ANIMA-owned plugin/capability registry and adopt/wrap MCP Python SDK `2.1.1` plus `jsonschema 4.26.0`; keep plugin metadata subordinate to Phase 4 policy.
- Evidence: x86-64 unit/integration/simulator evidence, PostgreSQL migration/restart/persistence, real local MCP stdio exchange, OPA-gated invocation, CI `33277823326`, fresh-checkout build/validation, and public-safety scan passed at implementation checkpoint `c186c34bcf93e9ff03d39c3e966fcb540583d478`.
- Boundary: Native plugins are trusted in-process; optional MCP plugins are supervised out-of-process. No runtime package installation, policy/permission mutation, raw secrets, Home Assistant, Luna, physical actions, or later behavior were introduced. Subprocess is not a malicious-code sandbox.
- Consequence: Phase 6 Home Assistant Adapter remains pending Architect review.
## ANIMA-HA-P6-HOME-ASSISTANT-ADAPTER-008 — Governed Home Assistant substrate boundary

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Decision: Adopt/wrap `hass-client==1.2.3` behind an ANIMA-owned adapter and test against pinned Home Assistant Core `2026.8.2`; retain HA IDs as scoped provider references and require Phase 4/5 policy plus observed-state verification for low-risk control.
- Evidence: real isolated x86-64 HA WebSocket/registry/service runtime, PostgreSQL Truth/Journal/mapping persistence, OPA gating, restart/gap behavior, 43 tests, strict static/build validation, and CI `33284454470` on `ecae55af1894889e0948d11a9ae01288c217c646` passed.
- Boundary: no physical-device claim, generic HA service tool, credential persistence, blind canonicalization, API-acknowledgement success, Luna, or Phase 7 behavior.
- Consequence: Phase 7 remains gated on independent Architect acceptance.
