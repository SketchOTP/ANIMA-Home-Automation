# Phase 9 evidence

## Implementation

- `src/anima_ha/action.py`: coordinator, in-memory and PostgreSQL stores, resource lockers, verification and recovery contracts.
- `src/anima_ha/db/migrations/0010_action_execution.sql`: durable action and per-effect records.
- `src/anima_ha/agent.py`: consequential Phase 8 decisions route through the coordinator when configured and fail closed when it is absent.
- `src/anima_ha/plugins.py`: confirmation is propagated through the final gateway policy evaluation.

## Checks

- Focused coordinator tests: PASSED, 10 tests.
- Full unit suite: PASSED, 94 tests.
- Ruff on changed implementation/tests and the Phase 9 harness: PASSED.
- Strict mypy on `src` and `tests`: PASSED.
- Locked local-filesystem package build: PASSED.
- PostgreSQL migration repeat, durable replay, and advisory-lock contention: PASSED.
- `scripts/verify_phase9_action_execution.py`: PASSED against isolated Home Assistant Core 2026.8.2, including real `set_power`, contradictory requests from two authenticated household principals, same-resource contention, post-action refresh verification, and durable replay without a second connector call.
- Direct validation from the GVFS/SFTP checkout: BLOCKED by the known virtualenv symlink limitation; local-disk reproduction was used for Python checks.

## Evidence boundary

Evidence is x86-64 and uses isolated virtual/demo Home Assistant entities. It does not establish native ARM64/Raspberry Pi, physical-home, high-risk/security, or production external-provider behavior.

## Checkpoint closure

- Fresh local-filesystem validation after closure formatting fix: `uv sync --locked --dev`, Ruff format/check, strict mypy, 94-test pytest suite, migration repeat, OPA 4/4, and sdist/wheel build: PASSED.
- Fresh Phase 1–5 PostgreSQL/OPA/MCP regressions: PASSED.
- Fresh Phase 6 real isolated HA regression: PASSED.
- Fresh Phase 7 10,020-event PostgreSQL restart/replay/context regression and Phase 8 PostgreSQL episode restart regression: PASSED.
- Fresh Phase 9 real isolated HA coordinator harness: PASSED.
- Fresh critical checks: sorted multi-resource lock order, concurrent duplicate at-most-once dispatch, `EXECUTING` persistence before connector dispatch, and advisory-lock release on PostgreSQL session loss: PASSED.
- Implementation checkpoint: `7b3d759992ce6cef56914ef19aa8626df0214031`; GitHub Actions run `33323237014`: PASSED on the exact SHA.
- Final governed checkpoint: this closure commit; its exact SHA and final CI run are recorded in the Notion SSOT after push verification.
- Status: `COMPLETE — PENDING ARCHITECT ACCEPTANCE`.
- Phase 10 remains unauthorized; no Phase 10 behavior is included.

## Authority snapshot correction

- The committed `CURRENT.md` wording was corrected after publication to state `PHASE 9 COMPLETE — PENDING ARCHITECT ACCEPTANCE` and to name the exact final governed checkpoint and CI. This is governance metadata only; no implementation behavior changed.
