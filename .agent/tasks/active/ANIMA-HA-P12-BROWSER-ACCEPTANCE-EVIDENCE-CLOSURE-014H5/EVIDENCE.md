# H5 evidence ledger

## Current checkpoint

- H5 implementation/evidence head: `800d8cf4a183ce0e7548545182ed09f0687ad98f`
- Hosted CI: `33696481738` — `success` on the exact head.
- Artifact: `phase12-h5-evidence-800d8cf4a183ce0e7548545182ed09f0687ad98f`
- Artifact ID: `9872060277`
- Artifact ZIP SHA-256: `33e32d1966462416f27b1fec109cfac7097de2d15dac0f5e8086a580ce31a383`
- Governance/CI reliability checkpoint: `828230a73d3c9097bab448192747a3f6786c0d4f`
- Governance-head hosted CI: `33697593173` — `success` on the exact governance head.

## Passed evidence

- `PASSED / E2_REPRODUCED`: display-mode CSS has measurable wall/tablet/phone/desktop geometry differences; local Playwright assertions cover computed columns/gaps and widget ordering.
- `PASSED / E3_TARGET_TESTED`: real `create_app()` PostgreSQL/OPA/Graph/Truth/Journal/Attention/Context Broker/AgentRuntime/PluginManager composition with only the model scripted.
- `PASSED / E3_TARGET_TESTED`: deterministic external audit redaction and provider degraded/recovery state at the Core/API boundary.
- `PASSED / E3_TARGET_TESTED`: restricted live response plus zero matching sentinel occurrences in durable PostgreSQL state.
- `PASSED / E3_TARGET_TESTED`: original session cookie reused across application reconstruction and post-restart task mutation succeeds once at the API/Core boundary.
- `PASSED / E3_TARGET_TESTED`: isolated-HA API path reaches Core UI gateway, Phase 5, OPA, Phase 9, isolated HA, fresh observation, and terminal success; deliberate mismatch returns verification failure.
- `PASSED / E4_REGRESSION_PROTECTED`: 168 Python tests, Ruff, strict mypy, OPA 7/7, package build, frontend checks/build, Playwright, Docker UI image/health, diff check, and public-safety scan in hosted CI.

## Explicit evidence limits

- `NOT RUN`: browser-visible real OPA denial and zero-effect proof.
- `NOT RUN`: browser-visible provider failure, degraded state, recovery, and SearXNG/Overpass independence.
- `NOT RUN`: browser restricted-content response followed by reload and complete browser storage inventory.
- `NOT RUN`: same browser session surviving a real process stop/reconstruct/reconnect with SSE recovery.
- `NOT RUN`: browser-visible isolated-HA outcome target; the API allowance is covered by the reused isolated-HA harness.
- `NOT RUN`: a complete H5 Playwright journey matrix. Hosted Playwright reports 11 passed and 10 skipped across desktop/tablet/phone; the skipped cases are responsive/functional variants, not the missing H5 journeys.
- The prior live public-provider harness was intentionally removed from H5 hosted CI because H5 requires deterministic provider fixtures; its earlier local live results remain separate evidence and are not promoted to exact hosted evidence.
- The first governance-head run `33697435341` failed during a transient PostgreSQL startup/readiness race before H5 targets. The bounded workflow fix waits for healthy Compose containers; rerun `33697593173` passed. This history does not change the explicit browser evidence limits above.

## Status

`CONTINUE — IMPLEMENTATION/EVIDENCE PARTIAL; PENDING ARCHITECT ACCEPTANCE`.

Phase 13 remains unauthorized. No Phase 13 behavior is present.
