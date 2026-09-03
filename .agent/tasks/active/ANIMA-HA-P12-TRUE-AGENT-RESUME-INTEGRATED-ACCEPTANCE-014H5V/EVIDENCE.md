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
frontend validation uses the bundled Node/npm runtime on this host and hosted
frontend validation remains the authoritative check for the published
checkpoint. The implementation checkpoint is published; the packet remains
active until those acceptance gaps are resolved or explicitly returned to the
Architect.

## H5V-R1 continuation hardening — 2026-09-03

Implementation checkpoint: `8bcff850a56b0bd8b3a70cc4d837e1268e12716f`.
Hosted CI run `33817879359` was cancelled after exposing a port collision in
the test workflow; the bounded follow-up CI configuration was published in
`58636eaec87a9ad4ddd0958b916a4d74b2d9fe74`, whose exact-head hosted CI run is
`33818551425` (`success`). Artifact `9917602062` is
`phase12-h5-evidence-58636eaec87a9ad4ddd0958b916a4d74b2d9fe74` with digest
`sha256:257886d0b85f485bc2b103cdfc55b159618a00bb6c72f46f14f8b0352237464b`.

The bounded H5V-R1 implementation adds durable continuation lifecycle fields,
claim ownership/fencing and expired-lease reclaim, original tool-catalogue and
runtime-identity binding, pre-dispatch context/transcript preflight, cumulative
active-runtime accounting, recovery-safe approval handling, exact policy-intent
propagation, dedicated task/calendar projections, and a test-only browser
approval/rejection composition. The normal Playwright configuration now
excludes the dedicated H5V spec; the H5V server uses an isolated port so it
does not collide with the Docker UI health target.

Fresh local evidence:

- `scripts/validate.sh`: passed 174 Python tests, Ruff, strict mypy, and OPA
  7/7.
- Migrations: repeat-safe with no pending migrations.
- `scripts/verify_phase12_h5v_true_resume.py`: passed with real PostgreSQL and
  OPA; approval preserved one episode, two model turns, one provider dispatch,
  provider execution context, and `SUCCEEDED`; rejection preserved one
  episode, two model turns, zero provider dispatches, and `POLICY_DENIED`.
- `scripts/verify_phase12_h5_core.py`: passed with external audit redaction,
  provider degraded/recovery, restricted PostgreSQL sentinel absence, original
  session reconstruction, and post-restart task mutation.
- Dedicated H5V Playwright: 2/2 passed (browser approval and rejection).
- Existing Playwright matrix: 12 executed passes and 12 intentional responsive
  skips across desktop/tablet/phone; frontend check, tests, and Vite build
  passed. Package sdist/wheel, diff-check, and public-safety scan passed.

Evidence limits remain material and keep this packet active: browser-visible
real denial/strong-auth, provider degradation/recovery, restricted-content
live/reload/storage inventory, same-browser process restart with SSE recovery,
dirty task/calendar projection under the required historical-row fixture,
crash-window/concurrency accounting, and browser-visible isolated-HA outcomes
are not all proven by this checkpoint. The H5V-R1 work therefore remains
`CONTINUE`; it does not self-accept Phase 12 and does not implement Phase 13.
