# Directive Ledger

Append new directives at the bottom; never rewrite an accepted historical directive.

---

## AUTHORITY-BOOTSTRAP-001 — Install Authority 3.0 for ANIMA HA

- Issued: 2026-08-28
- Status: COMPLETE
- Project stage: BOOTSTRAP
- Goal link: Establishes the governance, state, evidence, and handoff structures required to build and independently verify the adopted ANIMA HA prototype goal.
- Objective: Install the Authority 3.0 package, populate project-specific state records, and preserve the adopted `PROJECT_GOAL.md` contract.
- Scope: Root `AGENTS.md`, `.agent/` project state/history structure, `.agents/` reusable Authority workflow, and project-specific Architect startup prompt.
- Exclusions: No implementation, dependency adoption, GitHub creation, deployment, production work, or weakening/narrowing of the adopted goal.
- Acceptance: Required Authority files exist; project identity and Notion SSOT are recorded; `PROJECT_GOAL.md` contains the authorized adopted goal; empty implementation state is represented honestly; append-only bootstrap evidence is recorded.
- Required validation: File inventory and content inspection; no implementation acceptance implied. Minimum evidence `E2_REPRODUCED` for the bootstrap artifact set.
- External discovery: NOT REQUIRED for governance installation; Authority 3.0 Notion package was the governing source.
- Stop/escalation conditions: Any missing or contradictory Authority package requirement, inability to preserve the adopted goal, or request to expand beyond governance installation.
- Source: User-authorized project bootstrap; Authority 3.0 Complete Installation Package in Notion.

---

## ANIMA-HA-P0-GOVERNANCE-BASELINE-001 — Reconcile and publish governed repository baseline

- Issued: 2026-08-28
- Status: COMPLETE
- Project stage: GOVERNANCE BASELINE
- Goal link: Establishes one observable, publicly safe, independently reviewable repository baseline before any ANIMA HA product implementation.
- Objective: Reconcile local Authority 3.0 state with the existing `SketchOTP/ANIMA-Home-Automation` repository and publish the governance-only checkpoint to `main`.
- Scope: Read and reconcile Authority state; initialize/configure local Git; preserve the remote baseline; correct repository pointers; review public safety; commit and push governance files; run installed validation; record checkpoint evidence in Authority and Notion.
- Exclusions: No product implementation, dependency scaffolding, services, APIs, schemas, UI, Home Assistant integration, prototype features, product-goal changes, or requirement weakening.
- Acceptance: Local `main` tracks the existing remote baseline; remote content is preserved; public safety review passes; Authority state records the GitHub repository and checkpoint; the adopted goal and completion marker remain intact; validation passes; working tree is clean; governance checkpoint is pushed; implementation file count remains zero.
- Required validation: Starting/final Git state, remote history/tree, public-material scan, installed Authority validation, clean working tree, remote SHA verification, and zero product implementation files.
- External discovery: NOT REQUIRED unless an unexpected Git/Authority issue requires authoritative documentation.
- Stop/escalation conditions: Meaningful history conflict, unclear sensitive-material publication, goal disagreement, uncorrectable validation failure, blocked authentication/permissions, or any need for implementation.
- Source: Architect directive `ANIMA-HA-P0-GOVERNANCE-BASELINE-001`.

---

## ANIMA-HA-P0-RUNTIME-BASELINE-002 — Establish Implementation Phase 0 runtime baseline

- Issued: 2026-08-28
- Status: IN PROGRESS
- Project stage: IMPLEMENTATION PHASE 0 — RUNTIME BASELINE
- Goal link: Establishes the reproducible repository and runtime foundation required before Phase 1 truth/state work while preserving `ANIMA_HA_PROTOTYPE_GOAL_COMPLETE`.
- Objective: Establish the smallest portable Python, tooling, isolated PostgreSQL, migration, simulator, validation, and CI baseline with no household intelligence.
- Scope: Runtime/toolchain qualification, package structure, configuration/secrets boundary, JSON logging, tests/lint/type checks, CI, PostgreSQL/pgvector evaluation, runtime-only migrations, versioning, simulator entrypoint, restart/persistence proof, fresh-checkout proof, documentation, and governed records.
- Exclusions: No Event Journal, Truth/State, household graph, memory, policy, agent cognition, Home Assistant adapter, NATS semantics, plugins/MCP, durable tasks, external tools, UI, voice, or product schema.
- Required external discovery: Current primary/official sources for Python packaging/tooling, PostgreSQL/pgvector, Docker portability, and GitHub Actions.
- Stop/escalation conditions: Incompatible licensing, no credible ARM64 path, Pi-incompatible architecture, irreproducible fresh checkout, unexpectedly heavy infrastructure, premature Phase 1 semantics, unsafe public publication, or SSOT architecture change.
- Source: Architect directive `ANIMA-HA-P0-RUNTIME-BASELINE-002`.

### Completion record — ANIMA-HA-P0-RUNTIME-BASELINE-002

- Completed: 2026-08-28/29
- Status: COMPLETE / PASS
- Implementation checkpoint: `3fd0bfd1dc2c26798423a8077d2a1d9ca3bc3480`
- Evidence: `.agent/tasks/completed/ANIMA-HA-P0-RUNTIME-BASELINE-002/EVIDENCE.md`
- No Phase 1 product behavior was implemented.

---

## ANIMA-HA-P1-REALITY-SUBSTRATE-003 — Core contracts, event journal and Truth/State service

- Issued: 2026-08-29
- Status: COMPLETE
- Project stage: IMPLEMENTATION PHASE 1 — REALITY SUBSTRATE
- Objective: Build ANIMA-owned normalized event/observation contracts, a PostgreSQL canonical append-only journal, deterministic Truth/State projection, failure retry, replay/rebuild, and synthetic simulator scenarios.
- Exclusions: No Household Graph, memory, identity/permissions, policy, plugins/MCP, NATS production integration, Home Assistant, Luna, action execution, durable tasks, external tools, UI, or voice.
- Required external discovery: Direct PostgreSQL/Psycopg implementation compared with Python `eventsourcing`, NATS JetStream, and KurrentDB/EventStoreDB.
- Completion record: PASS; implementation checkpoint recorded in `.agent/tasks/completed/ANIMA-HA-P1-REALITY-SUBSTRATE-003/EVIDENCE.md`.
- Source: Architect directive `ANIMA-HA-P1-REALITY-SUBSTRATE-003`.

---

## ANIMA-HA-P2-HOUSEHOLD-GRAPH-004 — Deterministic canonical Household Graph

- Issued: 2026-08-29
- Status: COMPLETE / PASS
- Project stage: IMPLEMENTATION PHASE 2 — HOUSEHOLD GRAPH
- Objective: Build the ANIMA-owned PostgreSQL canonical household graph with identity, containment, entrance topology, resources/capabilities, aliases, provider references, Truth bindings, commissioning, semantic queries, and journaled graph mutations.
- Exclusions: No memory, policy, Home Assistant adapter, Luna, plugins/MCP, actions, durable tasks, external tools, UI, or voice.
- Required external discovery: PostgreSQL recursive CTEs, Apache AGE, NetworkX, Brick, Project Haystack, and Graphiti.
- Source: Architect directive `ANIMA-HA-P2-HOUSEHOLD-GRAPH-004`.

### Completion record

- Completed: 2026-08-29
- Status: COMPLETE / PASS
- Architecture: BUILD ANIMA graph contracts/repository; ADOPT/WRAP PostgreSQL/Psycopg; REFERENCE/ADAPT Brick/Haystack; DEFER Graphiti; REJECT AGE and NetworkX as canonical persistence.
- Implementation checkpoint: `ed261e8a3bc794ededdc3084f63b816152988820`; GitHub Actions run `33261359336` passed for that exact SHA.
- Evidence: unit validation and x86-64 PostgreSQL integration; synthetic fixture/simulator; no HA or physical-home evidence.
- Phase 3 Memory Service and later behavior were not implemented.
