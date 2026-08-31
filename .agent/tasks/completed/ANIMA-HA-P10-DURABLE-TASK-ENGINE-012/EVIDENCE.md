# Evidence packet

## Status

Complete — pending Architect acceptance. Exact SHAs and hosted CI run IDs are
recorded here after the two publication checkpoints.

## Architecture evidence

- `src/anima_ha/tasks.py` implements typed declarative task, schedule, and run
  contracts; recursive executable-key rejection; deterministic IDs; in-memory
  and PostgreSQL stores; leases/attempts; due-event dispatch; lifecycle tools;
  and the scheduled cognition bridge.
- `src/anima_ha/db/migrations/0011_durable_tasks.sql` persists task definitions
  and occurrence runs with uniqueness, status checks, indexes, and leases.
- `src/anima_ha/plugins.py` forwards ANIMA household scope to trusted native
  task capabilities while preserving provider execution-context forwarding.
- `src/anima_ha/agent.py` resolves trusted action safety metadata on the live
  Phase 8 consequential-tool path; scheduled cognition still re-enters fresh
  existing boundaries.

## Required scenarios

`tests/test_tasks.py` covers declarative schedule validation, DST spring-forward
and fall-back policy, task creation idempotency/conflict, deterministic
guaranteed events, concurrent worker claims, lease reclaim/replay, misfire,
pause/resume/cancel, and household isolation. Existing Phase 9 tests cover
observation-first action verification and ambiguous dispatch. The PostgreSQL
script covers migration/repeat, two-worker claim race, journal event
deduplication, and lease recovery. Full counts, exact SHAs, CI, and safety
scan results are appended at closure.

## Limits

Evidence is local x86-64 and isolated. No native ARM64/Pi, physical-home,
production-scale scheduler, production connector, or Phase 11 evidence is
claimed.
