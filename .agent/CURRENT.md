# Current Project State

Last updated: 2026-08-29

## Current stage

IMPLEMENTATION PHASE 6 — HOME ASSISTANT ADAPTER IMPLEMENTED / VALIDATION IN PROGRESS

## Current objective

Connect ANIMA to an isolated real Home Assistant instance through canonical truth, identity, policy, and plugin boundaries without implementing Phase 7 behavior.

## Active directive

ANIMA-HA-P6-HOME-ASSISTANT-ADAPTER-008

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

## Current blockers

- NONE currently known for Phase 6 implementation; final GitHub CI and governed closure remain pending.
- Phase 7 Attention/Context Broker, Luna, generalized actions, durable tasks, external tools, UI, and voice remain explicitly out of scope.

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

## Next Architect decision point

Finish Phase 6 checkpoint/CI/Notion evidence, then return it for Architect review. Phase 7 is not authorized.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.
