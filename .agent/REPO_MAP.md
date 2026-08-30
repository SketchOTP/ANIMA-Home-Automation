# Repository Map

Last verified against: IMPLEMENTATION PHASE 8 CODEX OAUTH AGENT RUNTIME 2026-08-30

## Entry points

- `anima-validate` — deterministic local format/lint/type/unit gate.
- `anima-migrate` — runtime-only ordered SQL migration runner.
- `anima-sim` — synthetic reality, graph, memory, policy, plugin, HA-normalization, attention, and credential-free agent scenarios; no physical household behavior.
- `anima-attention-replay` — read-only journal-range attention/ContextPacket replay and profile comparison; no model, tool, HA action, or external side effect.

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
- `src/anima_ha/plugins.py` — ANIMA-owned plugin manifests, lifecycle, capability/tool registry, native/MCP runtimes, JSON Schema boundary, policy-gated invocation, secrets/config isolation, persistence, and event ingress.
- `src/anima_ha/mcp_reference.py` — synthetic MCP stdio server for bounded Phase 5 integration evidence.
- `src/anima_ha/db/migrations/0006_plugin_runtime.sql` — plugin and normalized tool persistence.
- `scripts/verify_phase5_plugins.py` — PostgreSQL/OPA/MCP/native lifecycle and persistence integration harness.
- `tests/test_plugins.py` — Phase 5 contract, policy-gate, schema, discovery, failure, and MCP stdio tests.
- `docs/PHASE-5-PLUGIN-CAPABILITY-RUNTIME.md` — plugin runtime architecture and qualification decisions.
- `src/anima_ha/db/migrations/0007_home_assistant_adapter.sql` — HA instance status and bounded provider inventory persistence.
- `scripts/verify_phase6_home_assistant.py` — real pinned HA container, PostgreSQL, OPA, registry/event/action/reconnect evidence harness.
- `tests/test_home_assistant.py` — Phase 6 normalization, race, mapping, health, policy, lifecycle, and verification tests.
- `docs/PHASE-6-HOME-ASSISTANT-ADAPTER.md` — adapter architecture, dependency decisions, synchronization, action verification, and evidence limits.
- `src/anima_ha/db/migrations/0008_attention_context.sql` — durable attention profiles/cursors/decisions/triggers/aggregates/failures/metrics and ContextPackets.
- `config/attention/phase7.v1.json` — versioned provider-independent prototype attention profile.
- `tests/test_attention.py` — guaranteed, suppression, high-volume replay, sparse context, uncertainty, trust/egress, scenario, and degraded-source tests.
- `docs/PHASE-7-ATTENTION-CONTEXT.md` — attention/context/replay architecture, dependency decisions, and evidence limits.
- `src/anima_ha/db/migrations/0009_codex_agent_runtime.sql` — durable agent episodes, turns, and tool requests with duplicate-trigger protection.
- `scripts/verify_phase8_agent_runtime.py` — OAuth-free PostgreSQL migration/audit/duplicate/restart integration harness.
- `scripts/verify_phase8_live_oauth.py` — manual local ChatGPT OAuth/Luna synthetic A–I acceptance matrix; excluded from hosted CI.
- `tests/test_agent.py` — Phase 8 cloud boundary, strict process contract, tool-policy loop, failure, budget, and injection tests.
- `docs/PHASE-8-CODEX-OAUTH-AGENT-RUNTIME.md` — cognition boundary, dependency decisions, durable episode model, privacy/failure behavior, and evidence limits.

## Known sensitive/high-risk areas

- HA and Codex OAuth credentials remain runtime-owned secrets; neither is persisted or exposed to Luna. HA IDs remain provider references; only bounded low-risk virtual HA actions are evidenced. Phase 8 reprojects Phase 7 packets, rejects direct Codex capability events, and sends requested tools only through Phase 5/4. Physical/high-risk actions, generalized Phase 9 execution, external production connectors, and semantic embedding services require separate authorization. Phase 5 subprocesses are not malicious-code sandboxes.

GitHub baseline parent: `088b267467fff93bfd225b9a94a6f4999759fb9f`. This map is not exhaustive; update it when repository structure or understanding changes materially and is verified.
