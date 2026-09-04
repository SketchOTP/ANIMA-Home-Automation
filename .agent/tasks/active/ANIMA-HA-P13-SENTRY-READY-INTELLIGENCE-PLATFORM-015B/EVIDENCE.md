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
- Added `anima-sentry-mcp` and `anima-sentry-bridge` entry points plus the
  installable `integrations/sentry/anima-core` compatibility bundle.
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
