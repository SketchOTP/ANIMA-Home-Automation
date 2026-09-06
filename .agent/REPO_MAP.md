# Repository Map

Last verified against: PHASE 12 CORE INTEGRATION / PORTFOLIO CLOSURE 2026-09-01

## Entry points

- `anima-validate` — deterministic local format/lint/type/unit gate.
- `anima-migrate` — runtime-only ordered SQL migration runner.
- `anima-sim` — synthetic reality, graph, memory, policy, plugin, HA-normalization, attention, and credential-free agent scenarios; no physical household behavior.
- `anima-attention-replay` — read-only journal-range attention/ContextPacket replay and profile comparison; no model, tool, HA action, or external side effect.
- `anima-task-worker` — bounded durable-task due-event dispatcher; one-shot by default, optional local polling loop.

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
- `src/anima_ha/memory.py` — canonical memory, lifecycle, retrieval, index rebuild/fallback, and mutation audit.
- `src/anima_ha/routines.py` — deterministic journal-derived routine model.
- `src/anima_ha/home_assistant.py` — wrapped HA client, provider inventory/mapping, normalization, synchronization, health, reconnect, and semantic low-risk tools.
- `src/anima_ha/attention.py` — typed attention profiles, immutable decisions, durable cursor/cooldown/rate/aggregation state, reasoning triggers, metrics, replay, and profile comparison.
- `src/anima_ha/context.py` — sparse bounded ContextPacket selection, provenance, trust/egress classification, deterministic pruning, persistence, and cloud-safe projection.
- `src/anima_ha/phase7_replay.py` — side-effect-free Phase 7 replay CLI.
- `src/anima_ha/agent.py` — durable bounded cognition episodes, cloud-safe projection, structured Codex CLI adapter, sequential Phase 5/4 tool loop, budgets, audit, and explicit outcomes.
- `src/anima_ha/action.py` — deterministic consequential-action lifecycle, canonical-resource locking, freshness/preconditions, final policy reauthorization, idempotency, verification, partial/unknown outcomes, and restart reconciliation.
- `src/anima_ha/tasks.py` — declarative durable tasks, schedules, cron/DST/misfire policy, trusted task provenance/idempotency, PostgreSQL lifecycle/claim ownership, deterministic due events, task lifecycle tools, and scheduled cognition bridge.
- `src/anima_ha/ui_runtime.py` — ANIMA-owned production composition root and UI adapters over the existing Journal, Attention, Context Broker, AgentRuntime, PluginManager/Tool Gateway, policy, tasks, calendar, and Phase 9 coordinator.
- `src/anima_ha/ui_api.py` — local semantic UI API, session/OAuth boundary, and configured production Core runtime selection.
- `src/anima_ha/agent_instructions.py` — versioned provider instructions and authority/evidence boundary.
- `tests/` — deterministic Phase 0–8 unit tests and isolated provider fixtures.

## Important interfaces / contracts

- `.agent/PROJECT_GOAL.md` — adopted ANIMA HA goal, scope, non-goals, constraints, and acceptance boundary.
- `.agent/INDEX.md` — mandatory project-state retrieval map.
- `.agents/skills/authority/SKILL.md` — reusable Codex operating workflow.
- `AGENTS.md` — root Authority router.

## Tests

- `uv run --locked --group dev pytest` — Phase 0/1/2 unit tests.
- `uv run --locked --group dev python scripts/verify_phase1_postgres.py` — synthetic PostgreSQL integration harness.
- `uv run --locked --group dev python scripts/verify_phase2_postgres.py` — synthetic PostgreSQL graph integration harness.
- `uv run --locked --group dev python scripts/verify_phase3_postgres.py` — synthetic PostgreSQL memory/routine integration harness.
- `uv run --locked --group dev python scripts/verify_phase7_attention.py` — 10,020-event PostgreSQL cursor/restart/aggregation/context/replay harness.

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
- `docs/PHASE-3-GOVERNED-MEMORY.md` — canonical memory/routine architecture, lifecycle, retrieval/index boundary, dependency decisions, and evidence boundaries.
- `src/anima_ha/policy.py` — ANIMA-owned identity evidence, assurance, ActionIntent/risk classification, OPA adapter, confirmation, decision persistence, and fail-closed policy service.
- `policy/phase4/` — pinned Rego policy data and `opa test` matrix.
- `scripts/verify_phase4_policy.py` — synthetic x86-64 PostgreSQL + local OPA integration evidence.
- `docs/PHASE-4-IDENTITY-POLICY.md` — identity, risk, OPA, confirmation, audit, and fail-closed architecture.
- `src/anima_ha/plugins.py` — ANIMA-owned plugin manifests, lifecycle, capability/tool registry, ANIMA execution-boundary normalization, trusted invocation context, native/MCP runtimes, JSON Schema boundary, policy-gated invocation, secrets/config isolation, persistence, and event ingress.
- `src/anima_ha/mcp_reference.py` — synthetic MCP stdio server for bounded Phase 5 integration evidence.
- `src/anima_ha/db/migrations/0006_plugin_runtime.sql` — plugin and normalized tool persistence.
- `scripts/verify_phase5_plugins.py` — PostgreSQL/OPA/MCP/native lifecycle and persistence integration harness.
- `tests/test_plugins.py` — Phase 5 contract, policy-gate, schema, discovery, failure, and MCP stdio tests.
- `docs/PHASE-5-PLUGIN-CAPABILITY-RUNTIME.md` — plugin runtime architecture and qualification decisions.
- `src/anima_ha/db/migrations/0007_home_assistant_adapter.sql` — HA instance status and bounded provider inventory persistence.
- `scripts/verify_phase6_home_assistant.py` — real pinned HA container, PostgreSQL, OPA, registry/event/action/reconnect evidence harness.
- `scripts/verify_phase9_action_execution.py` — isolated pinned HA action-coordinator harness covering real provider execution, PostgreSQL resource contention, post-action verification, and durable replay.
- `tests/test_home_assistant.py` — Phase 6 normalization, race, mapping, health, policy, lifecycle, and verification tests.
- `docs/PHASE-6-HOME-ASSISTANT-ADAPTER.md` — adapter architecture, dependency decisions, synchronization, action verification, and evidence limits.
- `src/anima_ha/db/migrations/0008_attention_context.sql` — durable attention profiles/cursors/decisions/triggers/aggregates/failures/metrics and ContextPackets.
- `config/attention/phase7.v1.json` — versioned provider-independent prototype attention profile.
- `tests/test_attention.py` — guaranteed, suppression, high-volume replay, sparse context, uncertainty, trust/egress, scenario, and degraded-source tests.
- `docs/PHASE-7-ATTENTION-CONTEXT.md` — attention/context/replay architecture, dependency decisions, and evidence limits.
- `src/anima_ha/db/migrations/0009_codex_agent_runtime.sql` — durable agent episodes, turns, and tool requests with duplicate-trigger protection.
- `src/anima_ha/db/migrations/0010_action_execution.sql` — durable action claims and per-effect outcomes with idempotency/status indexes.
- `src/anima_ha/db/migrations/0011_durable_tasks.sql` — durable task definitions and occurrence runs with idempotency, leases, status, and replay keys.
- `scripts/verify_phase8_agent_runtime.py` — OAuth-free PostgreSQL migration/audit/duplicate/restart integration harness.
- `scripts/verify_phase8_live_oauth.py` — manual local ChatGPT OAuth/Luna synthetic A–I acceptance matrix; excluded from hosted CI.
- `tests/test_agent.py` — Phase 8 cloud boundary, strict process contract, tool-policy loop, failure, budget, and injection tests.
- `docs/PHASE-8-CODEX-OAUTH-AGENT-RUNTIME.md` — cognition boundary, dependency decisions, durable episode model, privacy/failure behavior, and evidence limits.
- `docs/PHASE-9-ACTION-EXECUTION-CONCURRENCY.md` — action lifecycle, advisory locks, idempotency, verification, ambiguity/restart semantics, and evidence limits.
- `docs/PHASE-10-DURABLE-TASK-ENGINE.md` — declarative task lifecycle, schedule/DST/misfire policy, safety boundary, dependency decisions, and evidence limits.
- `scripts/verify_phase10_durable_tasks.py` — PostgreSQL migration, idempotent creation, lifecycle parity, stale-worker/cancellation races, real AgentRuntime task creation, fresh scheduled cognition, due-time Phase 9 consequential-action routing, event deduplication, and lease-recovery evidence.
- `tests/test_tasks.py` — task contract, DST/misfire, trusted AgentRuntime routing/provenance, policy outcomes, idempotency, lifecycle parity, concurrency, household scoping, deterministic dispatch, cancellation, and lease-recovery tests.
- `tests/test_ui_runtime.py` — real-AgentRuntime journal/Attention/Context trace and Core policy-gated task mutation evidence.

## Phase 11 external capabilities

- `src/anima_ha/external.py` — ANIMA-owned bounded external result/trust/audit contracts, fixed-host transport, Open-Meteo, private SearXNG, OpenStreetMap Overpass, TheMealDB, ntfy, provider gates, and native plugin wrappers.
- `src/anima_ha/calendar.py` — first-party household-scoped PostgreSQL calendar, trusted invocation provenance/idempotency, CRUD, optimistic versioning, and Core-approved internal tool manifest.
- `src/anima_ha/db/migrations/0012_local_calendar.sql` — durable local-calendar schema.
- `tests/test_external.py` — bounded egress, hostile-content trust, SearXNG/Overpass normalization, audit, local-calendar idempotency/versioning, and provider-gate tests.
- `tests/test_phase11_integration.py` — actual AgentRuntime shared-catalogue selection, hostile external-content containment, and durable-task fresh external follow-up evidence.
- `scripts/verify_phase11_external.py` — live synthetic no-secret provider harness for weather, recipes, SearXNG, Overpass, and local-calendar evidence; `--require-phase11-targets` is strict and returns nonzero for missing required live targets.
- `scripts/verify_phase11_local_hardening.py` — target-only real OPA plus PostgreSQL calendar policy, CRUD/version/idempotency, audit, isolation, reconnect, and no-Phase-9-record evidence.
- `infra/searxng/settings.yml` and `compose.yaml` — pinned private SearXNG configuration with fixed engines, no public instance, no image proxy, and no Valkey.
- `docs/PHASE-11-EXTERNAL-CAPABILITIES.md` — current free/local provider architecture, trust/egress/audit boundary, gates, and evidence limitations.
- `src/anima_ha/external.py` — bounded external adapters and manifests; `WalmartProductProvider` wraps LedgerMind's signed, read-only Walmart Product API contract behind fixed host, trusted secrets, and untrusted result normalization.
- `tests/test_external.py` and `tests/test_phase11_integration.py` — signed-provider normalization, secret/gate behavior, manifest constraints, and actual AgentRuntime product-catalogue selection.
- `scripts/verify_phase11_external.py` — independent Phase 11 provider harness; `--require-upcitemdb-products` runs the two no-key product usefulness queries and reports explicit resource gates.
- `.agent/tasks/completed/ANIMA-HA-P11-WALMART-ENTITLEMENT-QUALIFICATION-013R3/` — evidence packet for the governance-only Walmart entitlement investigation and clarification blocker.
- `.agent/tasks/completed/ANIMA-HA-P11-BEST-BUY-PRODUCT-PROVIDER-013R4/` — evidence packet for Best Buy qualification; stopped before implementation because the published 72-hour Content-retention rule conflicts with current indefinite PostgreSQL tool-result persistence.
- `scripts/verify_phase11_restricted_content.py` — real PostgreSQL episode/export sentinel scan proving restricted Best Buy content remains live-only while structural durable evidence survives replay.
- `.agent/tasks/completed/ANIMA-HA-P11-RESTRICTED-CONTENT-PERSISTENCE-013R5/` — hardening evidence packet, provider boundary decision, validation, and publication record.
- `.agent/tasks/completed/ANIMA-HA-P11-UPCITEMDB-PRODUCT-PROVIDER-013R6/` — no-key provider qualification, live usefulness evidence, restricted-content integration, validation, and publication record.
- `src/anima_ha/external.py` — includes the fixed-host UPCitemdb adapter, conservative rate limiter, Core-restricted product manifest, and explicit no-key provider availability.
- `scripts/verify_phase11_external.py` — runs the strict no-key UPCitemdb `wireless headphones` and `air fryer` live target with structural counts and rate-limit headers.

## Phase 12 custom local interface

- `src/anima_ha/ui_api.py` — ANIMA-owned FastAPI semantic API, HA OAuth bootstrap, exact identity mapping, hashed sessions/CSRF, bounded SSE invalidations, and fail-closed Core command/conversation seams.
- `src/anima_ha/db/migrations/0013_ui_sessions.sql` — server-side UI session/CSRF digest schema.
- `src/anima_ha/db/migrations/0014_ui_preferences.sql` — bounded allowlisted PostgreSQL UI preference storage.
- `scripts/verify_phase12_final_ux.py` — deterministic real `create_app()` PostgreSQL/OPA/Core composition target; only the model response is scripted.
- `ui/` — React/TypeScript/Vite responsive single-page interface, same-origin browser policy tests, and Playwright desktop/tablet/phone scenarios.
- `Dockerfile.ui` and `compose.yaml` — reproducible non-root local UI image and loopback-published Compose service.
- `scripts/verify_phase12_ui.py` and `tests/test_ui_api.py` — deterministic API/auth/view-model/CSRF/SSE evidence.
- `docs/PHASE-12-CUSTOM-LOCAL-INTERFACE.md` — current interface architecture, security boundary, deployment, and evidence limitations.
- `.agent/tasks/completed/ANIMA-HA-P12-CUSTOM-LOCAL-INTERFACE-014/` — historical Phase 12 specification, evidence ledger, and handoff.
- `.agent/tasks/completed/ANIMA-HA-P12-FINAL-UX-AUTHORITY-ACCEPTANCE-CLOSURE-014H3/` — final UX/authority convergence evidence and governance packet.
- `docs/assets/anima-home-desktop.png`, `anima-home-tablet.png`, `anima-home-phone.png` — responsive screenshots captured from the tested UI with synthetic data.
- `scripts/serve_phase12_h4.py` — explicit acceptance-only server that composes real PostgreSQL/OPA/Core with a scripted model and test auth.
- `scripts/verify_phase12_h4_core.py` — real `create_app()` conversation, task, calendar-version, settings-restart, and no-echo evidence target.
- `scripts/verify_phase12_h4_isolated_ha.py` — reused Phase 6 isolated Home Assistant evidence through UI HTTP, Core gateway, Phase 5/OPA, Phase 9, and observed verification.
- `ui/tests/ui.spec.ts` and `ui/playwright.config.ts` — serialized H4 browser matrix with desktop functional journeys and tablet/phone responsive smoke.
- `.agent/tasks/completed/ANIMA-HA-P12-VERIFIED-UX-E2E-CLOSURE-014H4/` — H4 directive, evidence ledger, and handoff.

### Phase 12 H5U durable confirmation continuation

- `src/anima_ha/action.py` — stable action-intent identity, durable pending-approval stores, authenticated single-use claim, expiry, rejection, and exact-request approval through the existing Phase 9 coordinator.
- `src/anima_ha/agent.py` — resumable confirmation episodes and same-episode continuation without replaying the original tool request.
- `src/anima_ha/ui_runtime.py` and `src/anima_ha/ui_api.py` — Core-routed approval/rejection boundary with session/CSRF/origin protection and bounded pending-approval projection.
- `src/anima_ha/db/migrations/0015_pending_approvals.sql` — PostgreSQL pending-approval persistence.
- `scripts/verify_phase12_h5u_confirmation.py` — real PostgreSQL exact-intent, wrong-principal, single-use, and one-dispatch verifier.
- `.agent/tasks/completed/ANIMA-HA-P12-CONFIRMATION-CONTINUATION-FINAL-ACCEPTANCE-014H5U/` — completed H5U directive, plan, evidence, and handoff; prior H5/H5R/H5S/H5T packets are preserved as completed historical records.

### Phase 12 H5V true AgentRuntime resume

- `src/anima_ha/agent.py` — durable episode context/transcript reconstruction,
  fenced continuation lifecycle, original tool-catalogue/runtime binding,
  cumulative active-runtime accounting, and same-episode continuation.
- `src/anima_ha/db/migrations/0017_continuation_lifecycle.sql` and
  `0018_continuation_lifecycle_compat.sql` — continuation lifecycle, lease,
  fence, runtime identity, catalogue, and recovery persistence.
- `src/anima_ha/action.py` and `src/anima_ha/plugins.py` — exact policy-intent
  propagation and recovery-safe approval execution through Phase 9.
- `src/anima_ha/ui_runtime.py` and `ui/src/main.tsx` — dedicated task/calendar
  management projections and Core confirmation result wiring.
- `scripts/verify_phase12_h5v_true_resume.py` and
  `scripts/verify_phase12_h5_core.py` — real PostgreSQL/OPA resume and Core
  boundary targets.
- `scripts/serve_phase12_h5v.py`, `ui/playwright.h5v.config.ts`, and
  `ui/tests/h5v.spec.ts` — explicit test-only browser approval/rejection
  composition; the normal Playwright config excludes these tests.
- `scripts/verify_phase12_h5v_ledger.py` — secret-free scenario ledger for the
  currently proven H5V subset.
- `.agent/tasks/completed/ANIMA-HA-P12-TRUE-AGENT-RESUME-INTEGRATED-ACCEPTANCE-014H5V/`
  — completed H5V packet; its negative evidence remains historical
  carry-forward.

### Phase 12 H5 browser acceptance evidence

- `scripts/verify_phase12_h5_core.py` — deterministic PostgreSQL/OPA/Core target for external audit redaction, provider degraded/recovery projection, restricted-content durable scanning, and original-session reconstruction.
- `Dockerfile.ui` — reproducible UI image including the installed-runtime Phase 4 policy bundle required by the normal `create_app()` composition.
- `.github/workflows/ci.yml` — hosted H5 Core, restricted-content, isolated-HA API, Docker health, frontend, Playwright, build, diff-check, safety, and artifact-upload targets; live public-provider calls are intentionally excluded from H5 hosted CI in favor of deterministic fixtures.
- `ui/src/styles.css` and `ui/tests/ui.spec.ts` — measurable display-mode layout behavior and computed-geometry/order assertions.
- `.agent/tasks/completed/ANIMA-HA-P12-BROWSER-ACCEPTANCE-EVIDENCE-CLOSURE-014H5/` — superseded H5 directive, evidence, and handoff; its incomplete browser journeys remain preserved as negative historical evidence.

### Phase 13 SENTRY-ready intelligence platform

- `src/anima_ha/intelligence.py` — durable intelligence request/result,
  lifecycle, lease, fencing, and Attention-delivery contracts.
- `src/anima_ha/sentry_boundary.py` — Core-owned typed SENTRY boundary for
  sparse context, catalogue, semantic tools, Phase 9 actions, and results.
- `src/anima_ha/sentry_mcp.py` — ANIMA-owned stdio MCP transport without SQL,
  raw HA, secrets, shell, or arbitrary HTTP.
- `src/anima_ha/sentry_bridge.py` — explicit Attention-to-SENTRY queue pump.
- `src/anima_ha/db/migrations/0019_intelligence_provider.sql` — durable
  request and append-only transition schema.
- `integrations/sentry/anima-household/` — canonical installable SENTRY
  client-only bundle; the legacy `anima-core/` path is a compatibility alias
  and carries no ANIMA credentials or Core imports.
- `docs/SENTRY-ANIMA-INTEGRATION.md` — ownership, topology, setup, and
  SenseGuard event-flow documentation.
- `docs/ARCHITECT-PIVOT-ANIMA-SENTRY-PLATFORM.md` — architect-facing record of
  the strategic pivot, ownership boundary, target signal flows, evidence
  status, and remaining SENTRY integration gates.

### Phase 13 Home Assistant device control

- `src/anima_ha/home_assistant.py` — bounded ZHA pairing, HA registry refresh,
  and server-derived device commissioning into canonical Graph/Truth
  resources and capabilities.
- `src/anima_ha/plugins.py`, `src/anima_ha/ui_runtime.py`, and
  `src/anima_ha/ui_api.py` — Core-owned policy-gated device operations and
  authenticated UI routes; raw HA services and arbitrary configuration remain
  unavailable.
- `ui/src/main.tsx` and `ui/src/styles.css` — Devices view for pairing,
  discovery, room assignment, and subsequent semantic Home control.
- `docs/PHASE-13-HA-DEVICE-CONTROL.md` — device-onboarding authority boundary
  and evidence limits.

### Phase 13 R1 SENTRY boundary hardening

- `src/anima_ha/sentry_service.py` — ANIMA-owned authenticated Unix-socket service; SENTRY receives no Core credentials.
- `src/anima_ha/sentry_boundary.py` — request-bound catalogue, fencing, semantic invocation, and non-escalating SENTRY identity evidence.
- `src/anima_ha/senseguard_alerts.py` and `src/anima_ha/db/migrations/0021_senseguard_alert_policy.sql` — typed canonical-resource SenseGuard alert policy.
- `integrations/sentry/anima-household/` — standalone client-only MCP package and bounded host-turn orchestrator; it has no ANIMA Core imports.
- `src/anima_ha/db/migrations/0020_sentry_boundary_hardening.sql` — durable request catalogue and provider-dispatch ambiguity markers.

### Phase 13 R3 integration qualification

- `src/anima_ha/sentry_service.py` and `src/anima_ha/sentry_boundary.py` —
  household/client-scoped direct requests, server-persisted SENTRY evidence
  references, and origin-bound service operations.
- `src/anima_ha/home_assistant.py`, `src/anima_ha/senseguard_alerts.py`, and
  `src/anima_ha/ui_runtime.py` — normalized HA event callback, typed
  SenseGuard policy routing, deterministic guaranteed alert deduplication, and
  Core composition wiring into the existing Attention bridge.
- `tests/test_sentry_boundary_hardening.py` — R3 direct identity/origin and
  SenseGuard routing evidence.

### Phase 13 R4 runtime compatibility certification

- `integrations/sentry/anima-household/anima_household_mcp.py` — MCP 1.x/2.x
  compatible server bootstrap for the client-only household bundle.
- `integrations/sentry/anima-household/skills/anima-household-agent/SKILL.md` —
  minimal SENTRY-side instructions preserving ANIMA authority and terminal
  result semantics.
- `scripts/verify_phase13_mcp_runtime.py` — actual MCP stdio initialize,
  tools/list, schema, direct/queued request, provider-start, read, mutation,
  result, and terminal certification harness.

## Known sensitive/high-risk areas

- HA, Codex OAuth, and external-provider credentials remain runtime-owned secrets; none is persisted or exposed to Luna. HA IDs and external provider IDs remain references; only bounded low-risk virtual HA actions and synthetic/public external traffic are evidenced. Phase 8 reprojects Phase 7 packets, rejects direct Codex capability events, and sends requested tools only through Phase 5/4. Physical/high-risk actions, commercial production external-provider use, and semantic embedding services require separate authorization. Phase 9 live coordinator evidence is isolated virtual/demo x86-64 and does not establish physical-home behavior. Phase 5 subprocesses are not malicious-code sandboxes.

GitHub baseline parent: `088b267467fff93bfd225b9a94a6f4999759fb9f`. This map is not exhaustive; update it when repository structure or understanding changes materially and is verified.

### Phase 14 resilience/replay/restore

- `scripts/verify_phase14_opa_outage_r2.py` - real Compose OPA outage,
  PostgreSQL policy-audit, zero-dispatch fail-closed target.
- `scripts/verify_phase9_action_execution.py` - real isolated-HA Phase 9
  opposing-request lock/verification/idempotency target now run in Phase 14
  hosted validation.
- `.github/workflows/ci.yml` - Phase 14 R2 hosted matrix, including ARM64
  runtime import smoke after the ARM64 UI image build.

- src/anima_ha/resilience.py - canonical bounded scenario/result ledger,
  explicit test-only one-shot fault injector, deterministic replay comparator,
  and secret-free backup/restore safety metadata.
- tests/test_resilience.py - focused schema, fault-injection, replay-regression,
  append-only ledger, and restore-safety tests.
- scripts/verify_phase14_resilience.py - deterministic Phase 14 contract target;
  it reports the scenarios it actually executes and names unrun infrastructure
  rather than promoting it to success.

Final bounded closure evidence (2026-09-06):

- `scripts/verify_phase14_final_closure_bundle_r2.py` - real PostgreSQL,
  Core/OPA process, and isolated-HA residual closure bundle. Its HA harness
  reconnects the same adapter after the real container restart before allowing
  Phase 9 verification; initial state preparation uses a separate uninstrumented
  connection so dispatch counts measure only the governed action.
- Exact implementation/evidence head `6a61e38276a086535fa933b38d5b69cabdb0a167`
  passed hosted CI `34012962667`; artifact `9983142603` digest is
  `sha256:d6cb85b3234f1cb70ac2132bff6dcdc5baf8af05fa14e74d9621ed8e8348970e`.
- Final mapped R2 audit is `40 VERIFIED / 0 UNKNOWN`; native Pi 5 remains an
  external hardware gate. Phase 14 is pending Architect acceptance and Phase
  15 remains unauthorized.

Phase 14 acceptance and current product direction (2026-09-06):

- Governed head `1f13b4421cff819d13163eb8580d16191fd1c40a` passed exact-head CI
  `34013571702`; artifact `9983326562` is the accepted closure evidence.
- The Phase 14 packet is under `.agent/tasks/completed/`. Current work is a
  goal-wide owner-facing management-plane increment, beginning with typed
  SenseGuard alert-policy management through ANIMA rather than the Home
  Assistant frontend.

Owner-facing management increment (2026-09-06):

- `src/anima_ha/senseguard_alerts.py`, `src/anima_ha/ui_api.py`, and
  `ui/src/main.tsx` — typed SenseGuard alert-policy storage, policy-gated UI
  management, and server-owned household/principal/version handling.
- `src/anima_ha/graph.py`, `src/anima_ha/home_assistant.py`, and
  `src/anima_ha/ui_runtime.py` — canonical device alias rename, active-room
  reassignment, retirement of ANIMA mappings, and bounded Core command
  routing without Home Assistant registry mutation.
- `docs/GOAL-ALERT-POLICY-MANAGEMENT-017A.md` and
  `docs/GOAL-DEVICE-LIFECYCLE-017A.md` — scope, evidence, and explicit
  lifecycle limits for the combined increment.
- Published head `b3057add1b912d15b82b4ccc5b836041e3b11c89` passed exact-head
  hosted CI `34017171506`; artifact `9984398595` was published without a
  public digest. The increment remains pending Architect acceptance.

Owner-facing notification-route management follow-on (2026-09-06):

- `src/anima_ha/notification_routes.py` and migration
  `src/anima_ha/db/migrations/0023_notification_routes.sql` — typed,
  household-scoped, optimistic-versioned route metadata with fixed
  server-owned `ntfy` provider/configured-destination references.
- `src/anima_ha/ui_runtime.py`, `src/anima_ha/ui_api.py`, and
  `ui/src/main.tsx` — Core/PluginManager/PolicyService routing and authenticated
  Notifications view for label, priority threshold, and enabled state.
- Head `09b0c8aff5e9b9ec59a0962381cf0d34a1d14e36` passed exact-head hosted CI
  `34019264187`; artifact `9985073980` was published. Automatic alert delivery
  and human receipt are not claimed; the active goal packet remains pending
  Architect acceptance.
- Governance reconciliation head `549630a412cd8fc4fc69a608d67aeb31596c8fdf`
  passed exact-head hosted CI `34019836787`; no runtime behavior changed.

Notification-route presentation correction (2026-09-06):

- `ui/src/main.tsx` maps the server-safe `server_configured` destination value
  to the user-facing “Server configured” label while preserving the fixed
  server-owned boundary.
- Head `f808d9479735a957d47e36779ad04a5c3bc3d4b1` passed exact-head hosted CI
  `34020850164`; artifact `9985597571` was published. The active increment
  remains pending Architect acceptance.
