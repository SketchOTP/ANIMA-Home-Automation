# H4 Evidence

## Checkpoints

- Starting governed checkpoint: `a059898be1c9e85291cf73fd7bde912ad6c3c7c2`; hosted CI `33672285860` passed.
- Implementation checkpoint: `9e12f6e295b52ec382c1952a21a1a95287100740`; hosted CI `33686351783` passed on that exact SHA.

## Implemented and reproduced

- Home controls send `desired_on`; the server adds the canonical resource reference.
- `CoreUICommandGateway.control()` projects the Phase 9 terminal action record. Provider `SUCCESS` is bounded evidence only; deliberate verification mismatch returns `VERIFICATION_FAILED`, and unknown post-dispatch state returns `UNKNOWN_RESULT`.
- Browser mutation helpers parse HTTP-200 semantic outcomes and publish them after the corresponding Core refetch. Task lifecycle, calendar create/edit/cancel with versioning, stale-update failure, and settings persistence across application reconstruction pass through the real Core path.
- Appearance (`system`, `light`, `night`), accent, density, text scale, reduced motion, display mode, widget visibility, and widget order are applied by the browser.
- `create_app()` with PostgreSQL/OPA/Graph/Truth/Journal/Attention/Context Broker/AgentRuntime/PluginManager and the scripted model adapter produces a real conversation event/context/episode trace with `fallback_enabled=false`.
- The reused Phase 6 isolated HA harness proves UI HTTP → CoreUICommandGateway → Phase 5 → OPA → Phase 9 → Home Assistant → observation/verification: `SUCCEEDED` and deliberate `VERIFICATION_FAILED`.

## Validation

- `uv sync --locked --dev`: PASSED.
- `anima-validate`: PASSED, 168 tests, Ruff and strict mypy.
- OPA 7/7, package build, TypeScript, frontend unit tests, and Vite build: PASSED.
- Phase 6 isolated HA harness, Phase 11 restricted-content verifier, and Phase 11 external harness: PASSED with their documented resource gates.
- Local Playwright reproduction: PASSED for desktop conversation/task/calendar/settings and responsive desktop/tablet/phone smoke; 7 executed and 8 non-desktop functional cases skipped by design.
- `git diff --check` and public-safety scan: PASSED.

## Evidence limits

The current browser suite does not independently execute every requested H4 browser journey: browser-visible OPA denial, degraded-provider recovery, restricted-product reload, backend restart/session/SSE recovery, and an isolated-HA browser target remain represented by Core/API or existing provider/harness evidence rather than dedicated browser scenarios. Native ARM64/Pi, physical-home behavior, production TLS, and live household commissioning remain unclaimed. These limits are preserved rather than promoted to PASS.
