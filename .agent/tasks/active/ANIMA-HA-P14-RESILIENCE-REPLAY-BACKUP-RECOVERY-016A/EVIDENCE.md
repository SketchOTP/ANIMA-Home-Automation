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
