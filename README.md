# ANIMA HA

ANIMA HA is an evidence-governed prototype of Anima, a local-first household intelligence layer built on Home Assistant. The repository contains the Architect-accepted Phase 0–7 foundations and the Phase 8 Codex OAuth/Luna runtime pending Architect review.

## Phase 0 through Phase 8 baseline

This checkpoint provides:

- a `src/` Python package boundary for the future modular monolith;
- environment-only configuration with a committed, non-secret example;
- JSON structured application logging;
- a pinned `uv` project and lockfile;
- deterministic unit, lint, format, and type checks;
- a pgvector-ready PostgreSQL development service with a migration runner;
- a simulator framework entrypoint that reports readiness but does not process household events;
- an ANIMA-owned PostgreSQL event journal, truth observation model, deterministic reconciliation projection, failure tracking, and replay/rebuild path;
- an ANIMA-owned PostgreSQL canonical household graph with commissioned topology, recursive place traversal, aliases, provider references, Truth bindings, semantic queries, and journaled graph mutations;
- an ANIMA-owned PostgreSQL canonical memory store with provenance, lifecycle/correction/expiry/retraction, bounded precedence-aware retrieval, rebuildable local lexical indexing, and explicit degraded fallback;
- a deterministic journal-derived routine model whose outputs are inferred context rather than Truth, permissions, or automation;
- ANIMA-owned identity evidence, assurance aggregation, semantic action-risk classification, confirmation challenges, and a local OPA/Rego policy boundary with fail-closed behavior and journaled decisions;
- a single local validation command and a matching GitHub Actions workflow.
- an ANIMA-owned Home Assistant adapter that preserves provider identity, normalizes HA state/events into the Phase 1 contracts, exposes bounded semantic tools through the Phase 5 registry and Phase 4 policy gate, and verifies low-risk service actions against observed HA state.
- a deterministic PostgreSQL-backed Attention Layer with guaranteed-event handling, durable cursor/cooldown/rate/aggregation state, immutable decisions, durable reasoning triggers, sparse provenance-rich ContextPackets, ANIMA-owned trust/egress controls, and side-effect-free replay/profile comparison.
- an ANIMA-owned bounded cognition loop using isolated ephemeral Codex CLI ChatGPT OAuth turns, Luna 5.6 at medium reasoning, schema-only decisions, mandatory Phase 5/4 tool-policy routing, durable episodes, cloud-safe context projection, and explicit failure/budget outcomes.

No UI, voice behavior, generalized Phase 9 action engine, durable future-task runtime, or production external action capability is included. Mem0, local embeddings, CEL, NATS, and policy-editing runtime APIs are not included. The Phase 6 integration is limited to an isolated HA test instance and low-risk virtual entities; Phase 8 live cognition uses synthetic tools and is not physical-home evidence.

## Supported baseline

- Python: CPython 3.12.x, constrained by `pyproject.toml` and `.python-version`.
- Host architectures: Linux ARM64 and x86-64 are the supported target shapes. This checkpoint is executed on x86-64; ARM64 support is established from image/package metadata and remains subject to native Pi execution in a later evidence pass.
- Infrastructure: Docker Engine with Compose v2 and a persistent Docker volume.
- Database: PostgreSQL 16.15 through the pinned pgvector image digest in `compose.yaml`. The image is extension-ready; Phase 0 does not create vector or household tables.

## Fresh-checkout workflow

Install `uv 0.12.7` using the official installer or package distribution, then run:

```bash
uv sync --locked --dev
cp .env.example .env
uv run --locked --group dev anima-validate
docker compose up -d db
uv run --locked --group dev anima-migrate
uv run --locked --group dev anima-sim --once
docker compose down
```

On filesystem mounts that cannot create virtual-environment symlinks (including the current SFTP-mounted workspace), set `UV_PROJECT_ENVIRONMENT` to a local-disk directory for the `uv sync` and `uv run` commands. This is a host filesystem limitation, not an application dependency.

The validation command runs format, lint, type, and unit checks. The database commands use only the local `.env` file and do not require household configuration.

For the full evidence workflow, see [`docs/PHASE-0-RUNTIME-BASELINE.md`](docs/PHASE-0-RUNTIME-BASELINE.md).
For the Phase 1 event/truth contracts and replay boundary, see [`docs/PHASE-1-REALITY-SUBSTRATE.md`](docs/PHASE-1-REALITY-SUBSTRATE.md).
For the Phase 2 graph contracts, prior-art decisions, commissioning, and evidence boundary, see [`docs/PHASE-2-HOUSEHOLD-GRAPH.md`](docs/PHASE-2-HOUSEHOLD-GRAPH.md).
For the Phase 3 memory taxonomy, lifecycle, retrieval/index boundary, routine model, prior-art decisions, and evidence boundary, see [`docs/PHASE-3-GOVERNED-MEMORY.md`](docs/PHASE-3-GOVERNED-MEMORY.md).
For the Phase 4 identity, risk, OPA, confirmation, audit, and fail-closed boundary, see [`docs/PHASE-4-IDENTITY-POLICY.md`](docs/PHASE-4-IDENTITY-POLICY.md).
For the Phase 5 manifest, lifecycle, native/MCP runtime, capability registry, policy gate, secrets, event ingress, and failure containment, see [`docs/PHASE-5-PLUGIN-CAPABILITY-RUNTIME.md`](docs/PHASE-5-PLUGIN-CAPABILITY-RUNTIME.md).
For the Phase 6 adapter, discovery, provider mapping, synchronization, reconnect, policy-gated semantic tools, and observed-state verification, see [`docs/PHASE-6-HOME-ASSISTANT-ADAPTER.md`](docs/PHASE-6-HOME-ASSISTANT-ADAPTER.md).
For the Phase 7 attention profiles, guaranteed triggers, durable cursor/aggregation, sparse ContextPackets, trust/egress controls, and replay boundary, see [`docs/PHASE-7-ATTENTION-CONTEXT.md`](docs/PHASE-7-ATTENTION-CONTEXT.md).
For the Phase 8 Codex OAuth boundary, structured cognition loop, durable episodes, policy-gated tools, privacy controls, dependency decision, and evidence limits, see [`docs/PHASE-8-CODEX-OAUTH-AGENT-RUNTIME.md`](docs/PHASE-8-CODEX-OAUTH-AGENT-RUNTIME.md).

## Authority

The adopted goal and operating workflow live in [`PROJECT_GOAL.md`](.agent/PROJECT_GOAL.md), [`AGENTS.md`](AGENTS.md), and `.agents/`. Product implementation remains bounded by the Authority records in `.agent/`.
