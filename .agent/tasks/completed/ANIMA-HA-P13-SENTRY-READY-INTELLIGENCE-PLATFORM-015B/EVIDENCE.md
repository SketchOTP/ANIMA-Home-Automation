# Evidence — ANIMA-HA-P13-SENTRY-READY-INTELLIGENCE-PLATFORM-015B

Status: IMPLEMENTED LOCALLY — PENDING FULL COMPATIBILITY/ARCHITECT REVIEW

## Implemented

- Added migration `0019_intelligence_provider.sql` for durable intelligence
  requests and append-only lifecycle transitions.
- Added bounded `IntelligenceRequest`, `IntelligenceResult`, provider-health,
  idempotency, claim lease, and fencing contracts.
- Added `SentryAttentionBridge`, which converts existing Attention triggers and
  sparse ContextPackets into durable SENTRY requests. It does not execute HA.
- Added `CoreSentryBoundary` for health, sparse context, registered semantic
  catalogue, policy-gated tool invocation, and structured result submission.
  Consequential tools are converted to `ActionRequest` and routed through the
  existing Phase 9 coordinator.
- Added `anima-sentry-bridge` and the installable client-only
  `integrations/sentry/anima-household` bundle; the legacy `anima-core` path is
  retained only as a compatibility alias.
- Added direct UI queue-mode composition via
  `ANIMA_INTELLIGENCE_PROVIDER=sentry`; the embedded AgentRuntime remains the
  explicit `embedded_reference` default for existing deterministic regressions.
- Added ANIMA↔SENTRY architecture/setup documentation and reconciled README
  product/provider language.

## Fresh evidence

- Existing baseline suite: 174 tests passed before the new slice.
- New SENTRY boundary tests: 2 passed.
- Full pytest after the slice: passed.
- Ruff on `src` and tests: passed.
- Strict mypy on `src` and tests: passed.
- Migration against local PostgreSQL: `0019` applied once; repeat migration
  returned no pending migrations.
- Live PostgreSQL request lifecycle smoke: enqueue → claim generation 1 →
  delivered → provider running → bounded response → `COMPLETED`. The exact
  smoke row was removed after verification.
- Direct `build_postgres_core()` probe with `ANIMA_INTELLIGENCE_PROVIDER=sentry`:
  `SentryConversationPipeline`, Core boundary available, 17 registered tools.

## Not yet demonstrated

- A running SENTRY host process has not yet claimed a real HA SenseGuard
  alert, selected an ANIMA tool, and returned a user-visible voice response.
- The protected dirty SENTRY V0.4 working tree was intentionally not modified.
- No live household mutation, notification broadcast, or voice behavior is
  claimed by this packet.
- The implementation head `da9b6de2aceb34e36a51c400dcf8b090e010115d` passed
  exact-head hosted CI `33933037033`; artifact `9959297861` was published.
  This is implementation evidence only and does not claim Architect
  acceptance.

Phase 14/15 and any Phase 13 voice implementation remain unauthorized.

## R4 runtime compatibility certification — 2026-09-05

### Implementation

- Added MCP runtime compatibility for the installed SENTRY host: MCP 2.x
  `MCPServer` and MCP 1.x `FastMCP` are selected without changing the semantic
  ANIMA surface.
- Added the minimal resident `anima-household-agent` skill and declared it in
  the plugin manifest. It reinforces ANIMA authority, request-bound tools,
  terminal verification, and fresh follow-up reads without creating a second
  persona.
- Added `scripts/verify_phase13_mcp_runtime.py`, which uses the actual installed
  MCP client/session and stdio transport against a local deterministic contract
  fixture. It is run in hosted CI.

### Actual MCP evidence

- Pinned runtime: Python `3.12.3`, MCP `2.1.1`, protocol `2025-11-25`, server
  `anima_household`; 10 tools listed and all schemas validated.
- Direct path: `DIRECT_SENTRY_INTERACTION`, household-bound context, two
  request-bound tools, provider start before two provider calls, read and
  governed mutation `SUCCEEDED`, result `RECORDED`, terminal `COMPLETED`.
- Queued path: `AUTONOMOUS_ATTENTION`, same bounded context and terminal flow;
  the direct request is not consumed by the queued path. Four fixture provider
  calls were observed and no ANIMA credentials were used.
- Actual Codex CLI `0.153.1` shadow loading was exercised with a disposable
  `CODEX_HOME`; `anima_household` initialized, listed its tools, and completed
  an `anima_health` call through the configured MCP client. The disposable
  shadow profile was removed after the probe.

### Compatibility limit and disposition

- `sentry-office` and `anima-household` have distinct manifest/server names,
  but the protected SENTRY office launcher currently exits before MCP
  initialization: it resolves
  `/srv/ATLAS/100_ACTIVE/Projects/SENTRY/integrations/tools/sentry_mcp_server.py`,
  while the protected server is at
  `/srv/ATLAS/100_ACTIVE/Projects/SENTRY/tools/sentry_mcp_server.py`.
- The protected SENTRY checkout remains at HEAD
  `5441cf35f9a08aaa8f1d2926c17672b4f105d0f7` with its pre-existing dirty files;
  no file was changed by ANIMA work. Correcting the launcher would be a
  SENTRY-side protected-tree change and is outside this authorization.
- R4 result: `NEEDS_ARCHITECT_DECISION — PHASE13_RUNTIME_COMPATIBILITY_BLOCKED`.
  The ANIMA-side compatibility increment passed exact-head hosted CI
  `33938016240`; artifact `9960893002` was published. Phase 14/15 and ANIMA
  voice remain unauthorized.

## R2 implementation continuation

- Added an explicit `provider-start` boundary. The client turn and the
  Attention bridge now transition a claimed request to `PROVIDER_RUNNING`
  before calling any SENTRY model planning code, including no-tool turns.
- Added a separate direct interaction contract. `POST /v1/interactions/direct`
  creates a new `DIRECT_SENTRY_INTERACTION` with sparse direct context and a
  request-specific claim; it cannot consume an older Attention request.
- Added server-owned `SentryServicePrincipal` binding to one household and the
  `sentry` provider. Client-supplied household, role, assurance, and worker
  values are not authority inputs. Direct identity observations are persisted
  as bounded, non-escalating ANIMA evidence; expired/ambiguous observations do
  not name a principal.
- Added request-specific PostgreSQL claiming and client/provider-generation
  binding checks. The `anima-household` client now exposes direct-open and
  provider-start operations; no ANIMA database, HA, OPA, or provider secret is
  present in its MCP environment.

## R2 validation boundary

The R2 code compiles on the native Atlas host and the new deterministic boundary
tests cover provider-start fencing, direct request independence, service
principal identity, and expired identity non-escalation. The current host could
not execute the dependency-bearing Python suite because the checked-in venv
points at an unavailable Python 3.12 path on the native host and the system
interpreter lacks `psycopg`; no test pass is claimed from that environment.
The protected SENTRY V0.4 tree remains dirty and untouched. A real/shadow SENTRY
Codex/Luna turn, physical SenseGuard event, voice path, and live HA action remain
open qualification gates.

## R1 hardening evidence — current working checkpoint

- ANIMA Core now has a separate Unix-socket service entry point. The SENTRY
  MCP bundle is a dependency-light client and receives only a configured Core
  endpoint, private service-token path, and worker label; it does not receive
  ANIMA database, OPA, Home Assistant, or provider credentials and does not
  import the ANIMA checkout.
- Service tokens are read only from private non-symlink regular files. Token
  rotation invalidates old authentication and previously issued binding
  signatures. Bindings carry server-issued request, household, provider,
  catalogue, correlation, expiry, and fencing identity.
- Intelligence requests persist their exact normalized tool catalogue. SENTRY
  catalogue and invocation paths enforce the original tool/version/schema
  intersection with current availability. Stale fencing generation cannot
  invoke or submit a result.
- Expired provider-delivered/running work with recorded possible dispatch is
  terminalized as `UNKNOWN_RESULT` with an auditable transition; it is not
  reclaimed for blind replay. SENTRY claims are provider-scoped.
- The HA registry adapter preserves current singular `config_entry_id` /
  `config_subentry_id` and sparse `parent_device_id` child-device metadata.
- Added an ANIMA-owned typed SenseGuard policy with household-local time-window
  matching, canonical resource scope, guaranteed-attention metadata, delivery
  mode, provenance, and optimistic-version PostgreSQL storage.

Focused R1 tests, full pytest, Ruff, and strict mypy pass locally. Real SENTRY
host/voice execution, physical SenseGuard triggering, live HA action, and
hosted exact-head CI remain unclaimed until the protected SENTRY host is
commissioned without modifying its dirty worktree.

## R3 integration qualification — 2026-09-04

- Starting governed checkpoint: `3112180fdefd7a6e199fc16376ca5790a7ba2158`;
  prior hosted CI `33929370701` passed on that exact head.
- Direct SENTRY idempotency is scoped by provider, household, registered
  service-client identity, and SENTRY request ID. The model cannot supply the
  household, provider, role, assurance, or authoritative idempotency identity.
- Direct identity observations are persisted through the ANIMA policy evidence
  store before direct request creation. The durable request binds the actual
  `IdentityEvidence.evidence_id`; profile mapping is server-owned and checked
  against household Graph membership. SENTRY observations remain at most
  `RECOGNIZED` and never mint authentication.
- `DIRECT_SENTRY_INTERACTION` and `SENTRY_PROVIDER` origin permissions are
  enforced at their respective intake boundaries. The client worker label is
  not an authority claim.
- Normalized non-snapshot HA events now pass through an ANIMA-owned callback.
  `SenseGuardEventRouter` resolves canonical resources, matches the typed
  household-local policy and normalized event type, emits a deterministic
  guaranteed alert event, and dispatches the existing Attention bridge once
  per logical alert. Ordinary unrelated event types are rejected.
- New focused evidence covers household/client-scoped request identity,
  persisted evidence-ID binding, origin rejection, deterministic SenseGuard
  alert deduplication, and unrelated-event rejection. Full pytest, Ruff, strict
  mypy, compileall, and `git diff --check` pass locally.

## R3 evidence limits

No live/shadow SENTRY Codex/Luna host turn, physical SenseGuard trigger,
SENTRY voice path, or live-household mutation was available from the protected
dirty SENTRY environment. Those remain explicit `EXTERNAL_RESOURCE_GATE` /
`NOT RUN` evidence, not implementation claims. Phase 14 and Phase 15 remain
unauthorized; this packet does not self-accept Phase 13.

## R3 exact-head hosted validation

- Exact tested head: `da9b6de2aceb34e36a51c400dcf8b090e010115d`.
- Hosted CI `33933037033` passed on the exact head.
- Artifact `9959297861` (`phase12-h5-evidence-da9b6de2aceb34e36a51c400dcf8b090e010115d`).
- Completed targets included deterministic validation, Phase 13 boundary
  validation, Core/UI validation, H5 targets, public-safety scanning, UI
  container health, frontend validation, and evidence publication.
- This does not claim live/shadow SENTRY, physical SenseGuard, voice, or live
  household mutation. Phase 14/15 remain unauthorized.
