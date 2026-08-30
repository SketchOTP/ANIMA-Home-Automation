# Current Project State

Last updated: 2026-08-30

## Current stage

PHASE 9 COMPLETE — PENDING ARCHITECT ACCEPTANCE

## Current objective

The deterministic action-execution/concurrency checkpoint is published with exact-SHA hosted CI evidence and is ready for independent Architect review. Phase 10 remains unauthorized.

## Active directive

`ANIMA-HA-P9-CHECKPOINT-CLOSURE-011C` — closure complete; implementation checkpoint `7b3d759992ce6cef56914ef19aa8626df0214031` passed CI `33323237014`, and final governed checkpoint `7b1cb07bd95c9f4641605dee89134990390c0640` passed CI `33323380633`. Phase 8 is accepted at `7153b127106c8e921185a38b1b4606fa42e5f92b`.

## Current verified state

- The project directory was empty before this bootstrap.
- Phase 0 now contains only runtime/engineering baseline code; no household intelligence or product behavior is implemented.
- The local project is a Git repository on `main`, configured with the required identity and connected to `git@github.com:SketchOTP/ANIMA-Home-Automation.git`.
- The existing GitHub baseline commit is `088b267467fff93bfd225b9a94a6f4999759fb9f` and contains `.gitignore` and `LICENSE`.
- The requested ANIMA HA goal is adopted at the prototype boundary `ANIMA_HA_PROTOTYPE_GOAL_COMPLETE`.
- The canonical Notion SSOT is the ANIMA HA Authority, Product Specification & Cold-Start Handoff page.
- Authority 3.0 governance files are installed and published in governance baseline commit `6fbabc892f53876fd94614ccc531dc7478a80288`.
- Python 3.12.x, uv 0.12.7, pinned development tooling, PostgreSQL 16.15/pgvector 0.8.6, migrations, structured logging, simulator scenarios, normalized event/observation contracts, append-only journal, deterministic truth projection, failure tracking, rebuild, tests, and CI are implemented in the current working tree.
- Phase 1 event identity, source deduplication, journal position, event/record time, source sequence, provenance, freshness, explicit unknown/unavailable/conflict states, projection retry, and replay/rebuild remain green.
- Phase 2 adds ANIMA-owned canonical graph nodes, typed relationships, recursive containment, entrance connectivity, separate resources/capabilities, aliases, provider references, Truth bindings, transactional commissioning, semantic queries, and graph mutation audit events.
- Phase 3 adds ANIMA-owned canonical memory records, provenance/taxonomy, deterministic precedence, correction/supersession, expiry/retraction, household-isolated retrieval, a rebuildable PostgreSQL lexical index with explicit fallback, and a journal-derived routine model.
- Phase 4 adds ANIMA-owned identity evidence and assurance aggregation, semantic action intents and risk classes, exact confirmation challenges, a local pinned OPA/Rego evaluator, PostgreSQL decision persistence, journaled policy audit, explicit autonomy configuration, and fail-closed policy behavior.

## Current hypotheses / unknowns

- Native Raspberry Pi execution has not yet been performed; ARM64 support is evidenced by image manifest and wheel metadata only.
- This SFTP-mounted workspace cannot reliably create a `.venv` symlink or complete mypy traversal; an allowlisted local-filesystem copy passes the full validation and build gate.
- No native Raspberry Pi run has been performed; ARM64 remains manifest/package evidence only.
- The canonical journal, truth projection, graph, memory store, derived lexical index, and routine model are PostgreSQL/Psycopg implementations behind ANIMA-owned interfaces. NATS/JetStream, graph extensions, NetworkX persistence, Graphiti, Mem0, FastEmbed, and River remain deferred or rejected for the current phase.
- OPA/Rego `1.20.1` remains the only Phase 4 policy evaluator, pinned by multi-architecture image digest. Cedar remains reference-only; Casbin and OpenFGA are not runtime dependencies.
- Phase 5 accepted prerequisite is Phase 4 governed SHA `50ea9c73e31b2037120da5d12e04555fa08b1da5` with CI run `33271197523`; Phase 5 implementation checkpoint is `c186c34bcf93e9ff03d39c3e966fcb540583d478` with CI `33277823326`. Any later closure commit contains metadata/evidence only.

## Phase 6 implementation state

- Phase 5 is Architect accepted at `b426d66e7293a132dcdb4abaa96bc7594cdf7b73`; CI `33277980009` passed.
- Phase 6 wraps `hass-client==1.2.3` against pinned HA Core `2026.8.2`, preserving provider references, Phase 1 normalization, Phase 2 mappings, Phase 4 policy, and Phase 5 lifecycle/tools.
- Real isolated HA evidence passes for discovery, WebSocket events, registry reconcile, explicit uncertainty, low-risk service execution, observed-state verification, deliberate verification failure, reconnect/gap, invalid auth, and restart.

## Phase 7 implementation state

- Phase 6 is Architect accepted at governed checkpoint `e1488d9a2d6280945cc2fd8bdba435733f0ba287`; GitHub Actions run `33284537147` passed.
- Phase 7 implementation checkpoint is `77aafbe5f78333b1c50d042fb1ceb19e74dbe698`; GitHub Actions run `33286882961` passed on that exact SHA.
- PostgreSQL-backed deterministic attention, guaranteed-event bypass, durable cursor/cooldown/rate/aggregation state, immutable decisions, durable reasoning triggers, sparse ContextPackets, trust/egress classification, and side-effect-free replay/profile comparison are implemented.
- Target evidence passed with 10,000 ordinary plus 20 guaranteed source events, restart after 5,000, exactly four aggregate and 20 guaranteed triggers, complete source journal, live/replay equivalence, context digest persistence, and Profile A/B comparison.
- Typed ANIMA predicates and existing PostgreSQL were selected; CloudEvents SQL, CEL, and OpenTelemetry remain reference material; CEL runtimes and NATS/JetStream remain deferred. No new service or runtime dependency was added.

## Phase 8 qualification state

- Phase 7 is Architect accepted at governed checkpoint `44d4f59737aeed9aa55583eb49823a37535d607d`; GitHub Actions `33287068428` passed.
- Codex CLI `0.150.0-alpha.8` reports `Logged in using ChatGPT` without credential inspection.
- The installed model catalog lists `gpt-5.6-luna` with `medium` reasoning support.
- An isolated strict-config live probe succeeded using ChatGPT OAuth, Luna, medium reasoning, ephemeral mode, ignored user config/rules, read-only sandbox, disabled shell/unified-exec/multi-agent/apps/plugins/web/image/memory/dependency-install controls, and no direct capability event.
- The documented `tools.view_image=false` spelling is unsupported by this CLI; the stable equivalent `features.view_image=false` is supported and is the required adapter mapping.
- Phase 8 implementation checkpoint is `8486cd10b7962df11898bc8b61b1ec46d0809dd5`; GitHub Actions `33293828743` passed without OAuth credentials.
- Durable episodes, cloud-safe projection, versioned instructions, strict isolated `codex exec`, structured sequential decisions, Phase 5/4 tool-policy routing, result filtering, budgets/timeouts, audit, fake CI adapter, and simulator parity are implemented.
- The final live A–I matrix passed with 14 Luna turns, model-selected one/two-tool sequences, three no-action outcomes, confirmation/stronger-auth stops, honest tool failure, prompt-injection containment, and zero forbidden direct capability events.

## Phase 9 implementation state

- ANIMA-owned `ActionExecutionCoordinator` is implemented in `src/anima_ha/action.py` and can be inserted between Phase 8 agent decisions and the Phase 5 gateway for consequential tools.
- Durable `anima_actions` and `anima_action_effects` records are added by migration `0010_action_execution.sql`; idempotency keys are unique and parameter mismatches are explicit conflicts.
- Canonical resource UUIDs use non-blocking PostgreSQL session-level advisory locks. Conflicts return immediately and are not queued behind stale intents; no PostgreSQL transaction remains open across the connector call.
- The coordinator refreshes latest state after lock acquisition, validates caller-supplied Truth preconditions, re-evaluates Phase 4 policy, records `EXECUTING` before the external call, refreshes again after the call, and requires observed verification for consequential tools.
- Ambiguous timeout/error results become `UNKNOWN_RESULT`; mixed effect results become `PARTIAL`; no blind retry or automatic compensation is performed. Restart reconciliation marks planned work `RECOVERY_REQUIRED` and in-flight work `UNKNOWN_RESULT`.
- Focused evidence: 10 Phase 9 tests plus existing suite; local-filesystem Ruff, strict mypy, and 94-test suite passed; PostgreSQL migration/repeat, durable replay, and real advisory-lock conflict passed; the isolated pinned HA coordinator harness passed real `set_power`, contradictory two-principal same-resource contention, post-action refresh, and durable replay.

## Current blockers

- NONE for the closure work; independent Architect acceptance remains the Phase 9 gate.
- Phase 10 durable tasks, external production tools, UI, and voice remain explicitly out of scope.

## Latest accepted evidence

- `AUTHORITY-BOOTSTRAP-001`: governance package installed and inspected; `E2_REPRODUCED` for the bootstrap artifact set only. This is not implementation or prototype acceptance evidence.
- Remote baseline `088b267467fff93bfd225b9a94a6f4999759fb9f`: observed and preserved as the Git history parent.
- Phase 0 acceptance checkpoint is `e68fc6240e5ae922f4e289b9ccdb7ed9f9babfe0`; GitHub Actions run `33232686789` passed.
- Phase 1 implementation checkpoint is `0ee72b736aa27e1b52d652eafb8e045e4b892148`; GitHub Actions run `33252987351` passed for that exact SHA.
- Phase 1 evidence is recorded in `.agent/tasks/completed/ANIMA-HA-P1-REALITY-SUBSTRATE-003/EVIDENCE.md`.
- Phase 2 evidence is recorded in `.agent/tasks/completed/ANIMA-HA-P2-HOUSEHOLD-GRAPH-004/EVIDENCE.md` after checkpoint closure.
- Phase 2 implementation checkpoint is `ed261e8a3bc794ededdc3084f63b816152988820`; GitHub Actions run `33261359336` passed for that exact SHA.
- Phase 3 implementation checkpoint is `0410cdb148cfcf42021d83bf73a6d239fab37a1d`; the final governed metadata checkpoint is recorded in the completed task evidence and Notion after push verification.
- Phase 4 accepted governed checkpoint is `50ea9c73e31b2037120da5d12e04555fa08b1da5`; accepted CI run is `33271197523`. Later metadata-only self-reference is not treated as a new product acceptance.

## Current risks

- Native Raspberry Pi runtime/resource qualification and backup/restore remain future evidence items.
- Truth bindings currently consume generic Phase 1 keys; Home Assistant source adapters must remain external-reference mappings when introduced.
- Public-repository publication requires continued exclusion of secrets, credentials, and runtime state.
- Mem0/FastEmbed remain unadopted; any future semantic index must first qualify telemetry, offline behavior, model licensing, native ARM64/Pi resource use, and canonical-store rebuild.
- OPA has official amd64/arm64 image manifests and local REST/policy-test support, but native Raspberry Pi execution and resource measurement remain unverified. No remote bundle or decision-log egress is configured.
- Phase 5 MCP and subprocess evidence will be synthetic/x86-64 unless a native ARM64 run is explicitly performed; subprocess isolation is not a malicious-code sandbox.
- Phase 5 adds `mcp==2.1.1` and `jsonschema==4.26.0`, ANIMA-owned manifest/lifecycle/registry contracts, policy-gated native/MCP invocation, scoped secrets/configuration, declared plugin events, persistence, and failure containment. Streamable HTTP is adapter-supported but not exercised against a permanent remote endpoint.
- Phase 9 action coordination is implemented against the Phase 5 gateway and PostgreSQL; live provider evidence is isolated virtual HA on x86-64. No native ARM64/Pi or physical-home execution evidence exists. The installed Codex CLI remains pre-stable and Phase 9 does not add a production connector.

## Next Architect decision point

Architect review of the Phase 9 implementation checkpoint and governed closure is required before Phase 10. Phase 9 status is `COMPLETE — PENDING ARCHITECT ACCEPTANCE`; final governed checkpoint `7b1cb07bd95c9f4641605dee89134990390c0640` passed CI `33323380633` and is recorded in Notion.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.
