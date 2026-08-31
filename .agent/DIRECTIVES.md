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
- Status: COMPLETE / PENDING ARCHITECT REVIEW
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

---

## ANIMA-HA-P3-GOVERNED-MEMORY-005 — Governed Memory Service and Routine Model

- Issued: 2026-08-29
- Status: COMPLETE / PASS pending independent Architect review
- Project stage: IMPLEMENTATION PHASE 3 — GOVERNED MEMORY
- Objective: Build canonical PostgreSQL memory with provenance, taxonomy, precedence, lifecycle/correction/expiry/retraction, bounded retrieval, rebuildable local index, and deterministic routine context.
- Exclusions: No Phase 4 identity/policy, Home Assistant, Luna, plugins/MCP, action execution, durable tasks, external tools, UI, or voice.
- Required external discovery: Mem0, direct PostgreSQL/pgvector, LangGraph, Letta, Graphiti, FastEmbed/local embedding options, and direct statistics versus River.
- Source: Architect directive `ANIMA-HA-P3-GOVERNED-MEMORY-005`.

### Completion record

- Completed: 2026-08-29
- Architecture: BUILD canonical ANIMA memory/lifecycle/retrieval/routine contracts; ADOPT/WRAP existing PostgreSQL/Psycopg and PostgreSQL full-text derived index; DEFER/WRAP-candidate Mem0; DEFER FastEmbed/pgvector embeddings, LangGraph, Letta, Graphiti, and River.
- Evidence: unit and synthetic x86-64 PostgreSQL integration; restart persistence; simulator; full static/test/build validation; Phase 1/2 regressions; public-safety and CI evidence.
- Phase 4 Identity/Policy and later behavior were not implemented.

---

## ANIMA-HA-P4-IDENTITY-POLICY-006 — Identity, Policy and Permission Engine

- Issued: 2026-08-29
- Status: COMPLETE / PASS pending independent Architect review
- Project stage: IMPLEMENTATION PHASE 4 — IDENTITY AND POLICY
- Objective: Build deterministic identity evidence, assurance, semantic action-risk classification, policy evaluation, confirmation, autonomy, decision audit, and fail-closed behavior before Phase 5.
- Exclusions: No Phase 5 plugins/MCP, Home Assistant, Luna, agent cognition, action execution, verification, durable tasks, external tools, UI, voice authentication, or biometric recognition.
- Decisions: ADOPT / WRAP local OPA/Rego 1.20.1; BUILD ANIMA contracts, risk, identity, confirmation, audit, and fail-closed adapter; REFERENCE Cedar/Casbin; DEFER/REJECT OpenFGA for this phase.
- Source: Architect directive `ANIMA-HA-P4-IDENTITY-POLICY-006`.

### Completion record

- Completed: 2026-08-29
- Evidence: `.agent/tasks/completed/ANIMA-HA-P4-IDENTITY-POLICY-006/EVIDENCE.md`; GitHub Actions run recorded at final checkpoint.
- Phase 5 Plugin Runtime and later behavior were not implemented.

---

## ANIMA-HA-P5-PLUGIN-CAPABILITY-RUNTIME-007 — Plugin Runtime and Capability/Tool Registry

- Issued: 2026-08-29
- Status: IN PROGRESS
- Project stage: IMPLEMENTATION PHASE 5 — PLUGIN CAPABILITY RUNTIME
- Objective: Build the ANIMA-owned manifest, lifecycle, capability registry, normalized tool descriptor, MCP/native runtime boundary, policy-gated invocation, secret/config isolation, validated plugin event ingress, persistence, and failure containment.
- Reconciled prerequisite: Phase 4 accepted product checkpoint `50ea9c73e31b2037120da5d12e04555fa08b1da5`; accepted CI `33271197523`. This directive does not create a checkpoint loop for that accepted history.
- Exclusions: No Home Assistant adapter, Luna/Agents SDK, physical actions, action verification, durable tasks, production external services, UI, voice, or runtime package installation.
- Required external discovery: Official MCP Python SDK v2, FastMCP, PyPA entry points, Pluggy, JSON Schema validation, and subprocess/container isolation.
- Source: Architect directive `ANIMA-HA-P5-PLUGIN-CAPABILITY-RUNTIME-007`.

### Completion record

- Completed: 2026-08-29
- Status: COMPLETE / PASS pending independent Architect review
- Implementation checkpoint: `c186c34bcf93e9ff03d39c3e966fcb540583d478`; GitHub Actions run `33277823326` passed for that exact SHA. Any later closure commit contains metadata/evidence only.
- Architecture: BUILD ANIMA manifest, lifecycle, registry, tool normalization, policy-gated invocation, secrets/config boundary, persistence, audit, and event ingress; ADOPT/WRAP MCP Python SDK `2.1.1`, `jsonschema 4.26.0`, and PyPA entry-point discovery; REFERENCE/DEFER FastMCP and Pluggy; DEFER container sandbox and marketplace/install/update system.
- Evidence: unit, local x86-64 PostgreSQL/OPA/MCP integration, simulator, restart persistence, fresh local-disk checkout, CI, and public-safety scan. ARM64 remains package/metadata evidence only.
- Phase 6 Home Assistant Adapter and later behavior were not implemented.

---

## ANIMA-HA-P6-HOME-ASSISTANT-ADAPTER-008 — Home Assistant Adapter

- Issued: 2026-08-29
- Status: IN PROGRESS
- Project stage: IMPLEMENTATION PHASE 6 — HOME ASSISTANT ADAPTER
- Accepted prerequisite: Phase 5 governed checkpoint `b426d66e7293a132dcdb4abaa96bc7594cdf7b73`; accepted CI `33277980009`.
- Objective: Connect ANIMA to a real isolated Home Assistant Core 2026.8.2 instance through an ANIMA-owned adapter, normalize discovery/state/events into existing contracts, preserve provider-reference identity, and expose verified low-risk semantic actions through the mandatory Phase 4/5 policy gateway.
- Exclusions: No Phase 7 attention/context, Luna/Agents SDK, generalized concurrency/leases, full Phase 9 action engine, durable tasks, production external tools, UI, or voice.
- Required external discovery: `hass-client 1.2.3`, direct aiohttp, maintained alternatives, direct pinned HA container, and `ha-testcontainer 2.7.0` as test-only orchestration.
- Source: Architect directive `ANIMA-HA-P6-HOME-ASSISTANT-ADAPTER-008`.
- Implementation checkpoint: `ecae55af1894889e0948d11a9ae01288c217c646`; GitHub Actions `33284454470` passed for the exact SHA.

### Architect acceptance

- Accepted: 2026-08-29
- Governed checkpoint: `e1488d9a2d6280945cc2fd8bdba435733f0ba287`
- GitHub Actions: `33284537147` passed for the exact governed SHA.

---

## ANIMA-HA-P7-ATTENTION-CONTEXT-009 — Attention Layer and Context Broker

- Issued: 2026-08-29
- Status: IN PROGRESS
- Project stage: IMPLEMENTATION PHASE 7 — ATTENTION AND CONTEXT
- Accepted prerequisite: Phase 6 governed checkpoint `e1488d9a2d6280945cc2fd8bdba435733f0ba287`; accepted CI `33284537147`.
- Objective: Consume canonical journal events through restart-safe deterministic attention, preserve guaranteed classes, emit durable reasoning triggers, and build bounded provenance/trust/egress-aware ContextPackets for future cognition.
- Exclusions: No Luna/Agents SDK, LLM calls, agent reasoning, action planning, concurrency/leases, durable task engine, external research tools, UI, or voice.
- Required external discovery: typed predicates, CloudEvents SQL v1, official/community CEL Python runtimes, PostgreSQL cursor/trigger persistence, NATS/JetStream, and OpenTelemetry Context/Baggage.
- Source: Architect directive `ANIMA-HA-P7-ATTENTION-CONTEXT-009`.

### Completion record

- Completed: 2026-08-29
- Status: COMPLETE / PASS pending independent Architect review
- Implementation checkpoint: `77aafbe5f78333b1c50d042fb1ceb19e74dbe698`; GitHub Actions run `33286882961` passed for that exact SHA.
- Architecture: BUILD typed ANIMA attention/context/replay; ADOPT/REUSE/WRAP PostgreSQL and existing Phase 1–5 services; REFERENCE CloudEvents SQL/CEL/OpenTelemetry; DEFER CEL runtimes/NATS/provider tokenization; PROHIBIT executable attention scripts and behavioral automation.
- Evidence: 50 tests, strict static/build validation, 10,020-event PostgreSQL restart/replay harness, Phase 1–5 regressions, real isolated Phase 6 HA regression, replay CLI, simulator, and public-safety review passed.
- Phase 8 Luna Agent Runtime and later behavior were not implemented.

---

## ANIMA-HA-P8-LUNA-AGENT-RUNTIME-010 — Agents SDK Luna runtime

- Issued: 2026-08-29
- Status: SUPERSEDED by operator ruling; no implementation performed
- Correct blocking result: `NEEDS_ARCHITECT_DECISION` because the prior Agents SDK/API-key path could not consume the operator-required Codex CLI ChatGPT OAuth session.
- Historical boundary: repository remained unchanged at accepted Phase 7 checkpoint `44d4f59737aeed9aa55583eb49823a37535d607d`.

---

## ANIMA-HA-P8-CODEX-OAUTH-RUNTIME-010R — Constrained Codex OAuth agent runtime

- Issued: 2026-08-30
- Status: IN PROGRESS
- Project stage: IMPLEMENTATION PHASE 8 — CODEX OAUTH AGENT RUNTIME
- Accepted prerequisite: Phase 7 governed checkpoint `44d4f59737aeed9aa55583eb49823a37535d607d`; accepted CI `33287068428`.
- Objective: Build ANIMA-owned durable cognition episodes and a bounded sequential structured-decision loop around isolated `codex exec` turns using ChatGPT OAuth, `gpt-5.6-luna`, and medium reasoning.
- Required boundary: Codex receives only Phase 7 cloud-safe context and bounded tool descriptors, returns exactly one `TOOL_REQUEST` or `FINAL`, and never receives direct shell, filesystem, MCP, HA, policy, database, app, plugin, or web capability access. ANIMA alone invokes tools through Phase 5 and Phase 4.
- Exclusions: No Phase 9 generalized execution/concurrency/leases, durable tasks, production external tools, UI, voice, API-key path, Agents SDK foundation, direct Responses integration, or Codex coding-agent capability access.
- Required external discovery: current official Codex CLI non-interactive/auth/config/model/JSONL/structured-output behavior and replacement-path comparison with Codex SDK, App Server, Agents SDK, and Responses API.
- Source: operator-authorized Architect directive `ANIMA-HA-P8-CODEX-OAUTH-RUNTIME-010R`.

### Completion record

- Completed: 2026-08-30
- Status: COMPLETE / PASS pending independent Architect review
- Implementation checkpoint: `8486cd10b7962df11898bc8b61b1ec46d0809dd5`; GitHub Actions `33293828743` passed for that exact SHA without OAuth credentials.
- Architecture: BUILD ANIMA durable episode/structured loop; ADOPT/WRAP Codex CLI ChatGPT OAuth, `gpt-5.6-luna`, medium reasoning, JSONL/output schema, and Phase 5/4; REFERENCE/DEFER Codex SDK/App Server; DEFER/REJECT API-key Agents SDK/Responses foundations for this directive.
- Evidence: 84 tests, strict static/build/OPA, PostgreSQL restart, Phase 1–7 regressions, real isolated Phase 6 HA regression, simulator, public safety, and live OAuth A–I matrix passed.
- Phase 9 Action Execution/Verification/Concurrency and later behavior were not implemented.

## ANIMA-HA-P9-ACTION-EXECUTION-CONCURRENCY-011 — Deterministic action execution boundary

- Issued: 2026-08-30
- Status: ISSUED / implementation complete pending Architect review
- Project stage: IMPLEMENTATION PHASE 9 — ACTION EXECUTION, VERIFICATION AND CONCURRENCY
- Objective: Make consequential agent-selected actions safe against stale/changing reality through resource conflict serialization, latest-state refresh, precondition validation, final policy reauthorization, idempotent connector execution, observed post-action verification, partial/unknown-result semantics, and crash/restart reconciliation.
- Scope: ANIMA-owned action coordinator and durable action/effect records; PostgreSQL session-level advisory locks for short-lived canonical-resource mutual exclusion; reuse Phase 1 Truth/Event Journal, Phase 2 canonical resources, Phase 4 OPA, Phase 5 Tool Gateway, Phase 6 refresh/verification, and Phase 8 agent bridge.
- Exclusions: No Phase 10 scheduling/durable future work, UI, voice, production external tools, automatic compensation, blind retries, stale-intent queueing, or transaction held across an external call.
- Required exit evidence: Simulated and isolated-provider races, duplicate action IDs/idempotency keys, contradictory commands, stale/manual state changes, ambiguous connector timeout, partial multi-effect outcome, process crash/restart, distinct-resource concurrency, and verification failure must remain structured with no duplicate or false-success claims.
- External discovery: PostgreSQL advisory-lock documentation and Stripe idempotency documentation checked 2026-08-30; see `.agent/EXTERNAL.md`.
- Source: Canonical Notion SSOT active directive `ANIMA-HA-P9-ACTION-EXECUTION-CONCURRENCY-011`, retrieved 2026-08-30.

## ANIMA-HA-P9-CHECKPOINT-CLOSURE-011C — Publish and close the Phase 9 checkpoint

- Issued: 2026-08-30
- Status: IN PROGRESS / closure and publication only
- Project stage: PHASE 9 CHECKPOINT CLOSURE — PENDING ARCHITECT ACCEPTANCE
- Architect disposition: `CONTINUE`, not accepted; the local Phase 9 implementation must be committed, pushed, and independently reviewable before acceptance.
- Objective: Preserve the validated Phase 9 implementation, perform fresh applicable validation, commit/push an implementation checkpoint, obtain passing hosted CI on its exact SHA, commit/push the governed evidence closure, and obtain passing hosted CI on the exact final SHA.
- Starting accepted checkpoint: `7153b127106c8e921185a38b1b4606fa42e5f92b` (Phase 8).
- Required final state: local `HEAD == main == origin/main`, clean working tree, Phase 9 implementation and evidence visible on GitHub, Notion reconciled to both exact SHAs and CI runs, and Phase 9 recorded as `COMPLETE — PENDING ARCHITECT ACCEPTANCE`.
- Exclusions: No new Phase 9 architecture, no Phase 10 durable tasks/scheduling/UI/voice, no production connectors, no compensation workflows, no new dependency decisions, and no external discovery unless a fresh validation defect requires it.
- Source: Architect directive in the Notion SSOT, retrieved 2026-08-30.

### Completion record

- Completed: 2026-08-30
- Status: COMPLETE / Phase 9 `COMPLETE — PENDING ARCHITECT ACCEPTANCE`
- Implementation checkpoint: `7b3d759992ce6cef56914ef19aa8626df0214031`; GitHub Actions `33323237014` passed on the exact SHA.
- Governed closure checkpoint: this closure commit; exact SHA and final GitHub Actions run are recorded in the Notion SSOT after push verification.
- Fresh local and isolated-provider validation passed; limitations remain x86-64, virtual/demo HA only, no native Pi/ARM64 or physical-home evidence.
- Phase 10 remains unauthorized.

## ANIMA-HA-P9-EXECUTION-HARDENING-011H — Correct Phase 9 execution-safety gaps

- Issued: 2026-08-30
- Status: IN PROGRESS / bounded correctness continuation
- Project stage: PHASE 9 EXECUTION HARDENING — PENDING ARCHITECT ACCEPTANCE
- Architect disposition: `CONTINUE`; published Phase 9 is not accepted.
- Objective: Correct system-owned precondition attachment, provider idempotency forwarding, connector-claim success bypass, and ambiguous-dispatch reconciliation while preserving Phase 0–8 and valid Phase 9 architecture.
- Exclusions: No Phase 10 durable tasks/scheduling, compensation, UI, voice, production connectors, new infrastructure, policy/Truth/plugin redesign, or external discovery unless a concrete connector defect requires it.
- Source: Architect directive recorded in the canonical Notion SSOT, retrieved 2026-08-30.

### Completion record

- Completed: 2026-08-30
- Status: COMPLETE — PENDING ARCHITECT ACCEPTANCE; Architect disposition remains `CONTINUE`.
- Implementation checkpoint: `fd9cd822cc6bb10d5ab49b705a9e365c9fd42160`; GitHub Actions `33339779556` passed on that exact SHA.
- Corrections: trusted system-owned safety profiles and live AgentRuntime preconditions; non-model-visible provider execution context with optional native idempotency forwarding; observation-first effect verification; ambiguous-dispatch refresh/reconciliation; verified no-op and partial outcomes.
- Fresh validation: 94 pytest tests, focused hardening tests, Ruff, strict mypy, OPA 4/4, package build, migration repeat, Phase 1–8 regressions, PostgreSQL lock/idempotency/recovery evidence, and isolated HA harness passed.
- Governed evidence closure: subsequent metadata-only checkpoint; exact SHA and final CI are recorded in the Notion SSOT after push verification.
- Limitations: x86-64 local-filesystem reproduction and isolated virtual Home Assistant only; native ARM64/Pi, physical-home, high-risk, and production-provider evidence remain unclaimed.
- Phase 10 remains unauthorized.

## ANIMA-HA-P10-DURABLE-TASK-ENGINE-012 — Declarative durable task engine

- Issued: 2026-08-31
- Status: COMPLETE — PENDING ARCHITECT ACCEPTANCE
- Project stage: PHASE 10 — DURABLE TASKS AND SCHEDULED COGNITION
- Architect disposition: `CONTINUE` from the accepted Phase 9 checkpoint; Phase 10 is authorized and Phase 11 remains unauthorized.
- Objective: Build a bounded PostgreSQL-backed declarative task engine for one-shot, fixed-interval, and cron opportunities; support restart-safe claims, leases, idempotent creation, explicit misfire/DST policy, deterministic guaranteed due events, task lifecycle tools, and re-entry through existing Attention/Context/Agent boundaries.
- Scope boundary: Future intent only. No executable payloads, future physical tool calls, stale authorization, compensation, UI, voice, production connectors, or Phase 11 behavior.
- Decisions: BUILD ANIMA task/run/coordinator semantics; ADOPT/WRAP PostgreSQL and `croniter==6.2.4`; REFERENCE/DEFER APScheduler; DEFER Hatchet and Temporal; no new broker/service.
- Required evidence: schedule contract, DST/misfire, idempotency, household isolation, concurrent claims, lease/crash recovery, deterministic journal deduplication, PostgreSQL migration/repeat, Phase 0–9 regressions, static/test/build/CI, and public safety.
- Source: canonical Notion SSOT active directive `ANIMA-HA-P10-DURABLE-TASK-ENGINE-012`, retrieved 2026-08-31.

## ANIMA-HA-P10-TASK-POLICY-INTEGRATION-012H — Correct task integration and ownership defects

- Issued: 2026-08-31
- Status: COMPLETE — PENDING ARCHITECT ACCEPTANCE
- Project stage: PHASE 10 TASK-POLICY INTEGRATION — PENDING ARCHITECT ACCEPTANCE
- Architect disposition: `CONTINUE`; Phase 9 is accepted at `7f09b52f8773901ea73221f60b40414874809fda`; Phase 11 remains unauthorized.
- Objective: Make the real AgentRuntime task-mutation path policy-gated and functional, inject trusted provenance/idempotency outside model arguments, enforce PostgreSQL lifecycle parity and live worker ownership, and preserve fresh scheduled cognition and Phase 9 routing for later physical actions.
- Corrections: ANIMA-owned `READ_ONLY` / `POLICY_GATED_INTERNAL` / `COORDINATED_CONSEQUENTIAL` normalization; trusted `InvocationContext`; model-free creator/idempotency fields; guarded PostgreSQL pause/resume/cancel and claim/dispatch transitions; dispatch-cancellation cleanup.
- Exclusions: No Phase 11 behavior, new service, production connector, UI, voice, compensation, arbitrary executable task payload, or weakening of Phase 9 physical/provider guarantees.
- Required evidence: real AgentRuntime schedule/lifecycle path, policy matrix, provenance/idempotency replay, memory/PostgreSQL lifecycle parity, stale-worker and cancellation races, fresh scheduled cognition, Phase 1–10 regressions, static/test/build/OPA/CI, and public safety.
- Source: Architect directive recorded in the canonical Notion SSOT, retrieved 2026-08-31.

### Completion record

- Implementation checkpoint: `27f7c3fb8ce53c4eb988d7de22c63672770998a8`; GitHub Actions `33425928381` passed on that exact SHA.
- Final governed checkpoint: `ae18833e2ddffd30b17b613248d1c2206062b66a`; hosted CI `33428938215` passed on that exact SHA.
- Evidence: local-filesystem locked validation, 122 tests, OPA 4/4, package build, migration repeat, Phase 1–5 and 7–8 regressions, isolated real HA Phase 6/9, PostgreSQL Phase 10 harness, and public-safety scan passed.

### 012H correction publication record

- The scheduled-cognition fixture was strengthened to select a synthetic consequential action at due time and prove it still enters the existing Phase 9 coordinator.
- Corrected implementation checkpoint: `945f89c13b67e52a9027d3f42cc3e2bccd5608d2`; GitHub Actions `33428295199` passed on that exact SHA.
- Fresh local evidence: `scheduled_future_action_phase9=PASS`; full pytest `122 passed`; Ruff, strict mypy, OPA 4/4, package build, migrations, Phase 1–10 harnesses, isolated HA Phase 6/9, diff check, and public-safety scan passed. One rebuilt-venv MCP startup failure was immediately reproduced as passing in isolation and in the subsequent full suite.
- The previous governed checkpoint `17d627b988aebb89b419671de8ee3c5a5525f516` is superseded for this correction. Phase 10 remains `COMPLETE — PENDING ARCHITECT ACCEPTANCE`; Phase 11 remains unauthorized.

## ANIMA-HA-P11-EXTERNAL-CAPABILITIES-013 — Bounded external-by-intent capabilities

- Issued: 2026-08-31
- Status: COMPLETE IMPLEMENTATION / PENDING ARCHITECT ACCEPTANCE
- Project stage: PHASE 11 — EXTERNAL-BY-INTENT CAPABILITIES
- Architect authorization: Phase 10 is accepted at `2c8f88f62c27a728b2bf0861dabaf7a3a3d03e56`; Phase 11 is authorized for bounded implementation and review. Phase 12 remains unauthorized.
- Objective: Add bounded weather, web/place/product discovery, recipes, Calendar, notifications, trusted egress/audit, provider gates, and Phase 9-verified external writes without introducing Phase 12 behavior.
- Architecture: BUILD ANIMA-owned semantic adapters and trust/egress/audit contracts; ADOPT/WRAP Open-Meteo, Brave, TheMealDB, Google Calendar REST, ntfy, httpx, and Google auth dependencies; defer retailer checkout/cart and Google Calendar MCP preview.
- Safety boundary: external content is `EXTERNAL_UNTRUSTED`; arbitrary URLs, hosts, redirects, credentials, topics, and provider headers are not model inputs. Calendar creation and notification send use exact Core-owned Phase 9 profiles; connector acknowledgement is not authoritative success.
- Required evidence: local unit/integration/static/build/OPA validation, live synthetic public-provider evidence where no credential is required, explicit Brave/Google credential gates, and publication on exact hosted-CI SHAs.
- Exclusions: No Phase 12 custom interfaces, UI, voice, shopping checkout/payment, physical-home claim, production-scale claim, automatic compensation, or unbounded external execution.
- Source: Architect directive in the canonical Notion SSOT, retrieved 2026-08-31.

### Completion record

- Implementation checkpoint: `17252304a4f0642bb654ec612cfcb55a01411804`; hosted CI `33442439042` passed on the exact SHA.
- Governance/evidence closure checkpoint and final hosted CI are recorded in the completed task packet and Notion after the closure push.
