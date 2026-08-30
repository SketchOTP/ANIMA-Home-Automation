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
