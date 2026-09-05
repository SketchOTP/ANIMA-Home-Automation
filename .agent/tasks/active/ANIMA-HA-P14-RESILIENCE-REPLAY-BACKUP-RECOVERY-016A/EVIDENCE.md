# Evidence - Phase 14

Status: IN PROGRESS

Starting ANIMA SHA:
f0456d24fa09ed6873e882c89a9dce759f73a619

Accepted SENTRY shadow compatibility patch:
00aa9ac3a35b7b012581160b961e01a9480bbbdf

This file is append-only evidence. Results use the labels PASSED, FAILED,
NOT RUN, NOT APPLICABLE, or BLOCKED and identify exact commands and artifacts.
Full provider payloads, credentials, and restricted content are never written.

## Initial state

- Phase 13: Architect accepted.
- Phase 14: active.
- Phase 15: unauthorized and unimplemented.
- Baseline and exact-head results: pending this execution.

## Initial deterministic target - 2026-09-05

- PASSED: full pytest on the current Phase 14 worktree, including the new
  resilience tests. Result: 219 tests passed.
- PASSED: targeted Ruff for src, tests, and Phase 14 verifier.
- PASSED: strict mypy for src and tests.
- PASSED: deterministic verifier
  scripts/verify_phase14_resilience.py. Artifact is a secret-free JSON ledger
  with digest
  efa4b3d8320395827cc565bdfb2ee0827f0876687b8bd801200df1ba3e71fb62.
- PASSED scenarios: PROVIDER_PRESTART_CRASH_RECLAIM,
  PROVIDER_STARTED_CRASH_NO_REPLAY, PROVIDER_RESULT_DURABLE_NO_RERUN,
  BACKUP_SECRET_SAFE, and RESTORE_NO_SIDE_EFFECT_REPLAY. Evidence level:
  DETERMINISTIC.
- NOT RUN by this target: PostgreSQL pg_dump/pg_restore, live HA outage and
  reconciliation, SENTRY provider outage, and native ARM64 execution. These
  remain open Phase 14 targets and are not promoted by inference.
- No credentials, restricted provider payloads, or private household data were
  placed in the ledger.

## Reconstructed state

- main was at the governed starting SHA and clean before this continuation.
- Phases 0-13 were Architect accepted; Phase 14 was active; Phase 15 remained
  unauthorized and unimplemented.
- The protected SENTRY V0.4 worktree was inspected separately and not modified.

## Real execution evidence - 2026-09-05

- PASSED / POSTGRES_OPA_CORE: disposable PostgreSQL 16/pgvector and OPA were
  started on isolated ports 55433/18182, all 22 migrations applied, and the
  Phase 1 PostgreSQL integration passed: duplicate logical inserts collapsed
  to one record, append-only enforcement held, projection retry worked, and
  rebuild replayed the journal.
- PASSED / POSTGRES_OPA_CORE: provider lifecycle checks against the real store
  covered pre-provider crash reclaim, provider-start ambiguity without blind
  replay, durable result without a second model run, one concurrent claim
  winner, and stale-fence rejection across provider writes.
- PASSED / POSTGRES_OPA_CORE: Phase 4 real OPA integration passed with 15
  decision records and 15 audit events; an OPA outage failed closed with zero
  provider dispatch.
- PASSED / ISOLATED_HA: scripts/verify_phase9_action_execution.py passed
  with real PostgreSQL advisory-lock contention, contradictory requests,
  isolated Home Assistant action, observed verification, and idempotent replay.
- PASSED / POSTGRES_OPA_CORE: scripts/verify_phase10_durable_tasks.py
  passed task lifecycle parity, stale worker rejection, cancellation before
  dispatch, one concurrent claim, lease recovery, fresh scheduled context,
  fresh external read, and future Phase 9 action routing.
- PASSED / ISOLATED_HA: scripts/verify_phase6_home_assistant.py passed
  against Home Assistant 2026.8.2. It covered discovery, registry mapping,
  known/unknown/unavailable truth, OPA denial/confirmation/strong-auth gates,
  verified action, deliberate acknowledged-but-unobserved
  VERIFICATION_FAILED, disconnect/reconnect/reconcile, invalid-token
  failure, plugin disable/restore, PostgreSQL restart, and secret
  non-persistence. The current-version registry write is verified through the
  adapter's explicit reconciliation boundary when no legacy registry event is
  emitted.
- PASSED / POSTGRES_OPA_CORE: 80 task records and 80 calendar records were
  reachable from the real stores. Task pause/resume/cancel passed. Calendar
  update advanced the version, stale update raised CalendarConflict, and
  versioned cancellation passed.
- PASSED / REAL_BACKUP_RESTORE: actual pg_dump -Fc and pg_restore completed
  into a clean pinned PostgreSQL container, followed by migration verification.
  Dump size was 217705 bytes and its secret-scan SHA-256 was
  f044742805867bad15df32cb8c88cb273597b99bc200677d87d6ec3844a6a10c.
  Restored schema/history continuity included 322 journal records, 131 truth
  records, 2 action records, and all 22 schema migrations. The restore
  manifest recorded raw_secrets=false,
  physical_truth=UNKNOWN_UNTIL_REOBSERVED, and
  executed_effects_replayed=false.

## Contract evidence

- PASSED / DETERMINISTIC_CONTRACT: scripts/verify_phase14_resilience.py
  executed five contract scenarios. Its result digest was
  7f78731782ccceacea58e2acf5e110d746f4bc15dc58d21526938836df3b909c.
  These five results are explicitly contract evidence and are not promoted
  to destructive system evidence.

## Still open

The following software-controllable Phase 14 targets were not completed by
this bounded continuation and remain open: approval/continuation crash
windows; full Phase 9 concurrent/manual-change matrix; duplicate and
out-of-order SenseGuard/event replay; HA outage recovery with no redispatch;
plugin-by-plugin isolation; SENTRY bridge outage/restart and no-fallback
matrix; external-content attack matrix; full process restart matrix; real
store replay regression detection; and ARM64 build/runtime qualification.
Native Pi 5 hardware remains an external resource gate only after ARM64
qualification.

Phase 14 is not accepted. No claim of complete resilience or backup/restore
qualification is made from the open targets.
