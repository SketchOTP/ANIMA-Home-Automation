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
- Hosted CI, final publication, and Architect acceptance are not claimed in
  this evidence file.

Phase 14/15 and any Phase 13 voice implementation remain unauthorized.

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
