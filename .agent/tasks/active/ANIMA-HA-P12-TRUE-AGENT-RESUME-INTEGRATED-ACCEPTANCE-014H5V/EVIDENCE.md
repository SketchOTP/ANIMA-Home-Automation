# H5V evidence

Status: in progress. This file is intentionally not a completion claim.

Current implementation work adds `anima_agent_continuations` and extends the
episode-store contract so approval/rejection results are durably appended to
the original episode transcript. `AgentRuntime.resume_confirmation()` then
loads the persisted context and transcript and calls the existing runtime loop
for the next model turn. The UI confirmation adapter uses the Phase 9 action
record as the authoritative status.

Validation recorded so far:

- focused `tests/test_agent.py` and `tests/test_action.py`: passed;
- focused Ruff format/check: passed;
- migration `0016_agent_continuations`: applied successfully to the local
  PostgreSQL reproduction.
- `scripts/verify_phase12_h5v_true_resume.py`: passed against the local
  PostgreSQL and OPA services. The approval branch preserved one episode ID,
  produced two model turns, persisted one continuation row, forwarded an
  ANIMA provider execution context, dispatched once, and ended `SUCCEEDED`.
  The rejection branch preserved one episode ID, produced two model turns,
  persisted one continuation row, dispatched zero times, and ended
  `POLICY_DENIED`.
- Existing H4 Core, H5 Core, H5U, isolated-HA API, and restricted-content
  targets: passed after the H5V changes. Full `scripts/validate.sh` passed 173
  Python tests, Ruff, strict mypy, and OPA 7/7. Package build, migration
  repeat, diff-check, and public-safety scan passed.
- Implementation checkpoint `d3c8beacef23e20e69a6cafd31eae1b7e6a9edb2`
  passed hosted CI `33777520224` on the exact SHA. The hosted job also passed
  the H5V verifier, frontend checks/build, Docker UI health, and published
  artifact `9902390114` (`phase12-h5-evidence-d3c8beacef23e20e69a6cafd31eae1b7e6a9edb2`).

Required remaining evidence includes a dedicated browser confirmation journey,
same-browser process restart/SSE continuation, and any broader Phase 12
acceptance evidence required by the Architect. The existing hosted Playwright
job is green but does not itself exercise those H5V-specific journeys. Local
frontend validation is not available on this host because `npm` is not
installed; hosted frontend validation is the authoritative check for this
checkpoint. The implementation checkpoint is published; the packet remains
active until those acceptance gaps are resolved or explicitly returned to the
Architect.
