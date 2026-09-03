# H5S evidence

## Result

`PARTIAL / CONTINUE — DECISIVE CORE AND PRODUCT-SURFACE EVIDENCE RECONFIRMED; REMAINING BROWSER JOURNEYS UNPROVEN`.

Retrieval confidence is `ADEQUATE`. The H5R product-surface implementation
remains intact and Phase 12 is not accepted. No Phase 8 confirmation
continuation or Phase 13 behavior was introduced.

## Validation

- `PASSED / E3_TARGET_TESTED` — `scripts/verify_phase12_h5_core.py` on the
  current implementation: real `create_app()` PostgreSQL/OPA/Core
  composition, provider degraded/recovery projection, restricted-response
  sentinel absence, original-session reconstruction, and post-restart durable
  mutation.
- `PASSED / E3_TARGET_TESTED` — `scripts/verify_phase12_h4_isolated_ha.py`:
  HTTP → CoreUICommandGateway → Phase 5 → OPA → Phase 9 → isolated HA, with
  observed success and deliberate verification failure.
- `PASSED / E3_TARGET_TESTED` — isolated browser runtime at
  `http://127.0.0.1:18091/`: after session recovery, Rooms & devices,
  Notifications & recent actions, System health, Activity, and all four H5R
  widget settings were visible after reload; the future Voice label was absent.
- `PASSED / E4_REGRESSION_PROTECTED` — prior H5R local regression remains
  applicable: 169 Python tests, Ruff, TypeScript/Vite, frontend tests 3/3,
  focused browser test 1/1, and full desktop browser 7/8.
- `FAILED` — the existing full desktop calendar lifecycle remains affected by
  the shared development database's bounded first-20 display with historical
  rows; HTTP create returned 200 but the new row was omitted. No cleanup or
  reseed was performed.
- `NOT RUN` — browser-visible OPA denial/zero-effect, browser provider
  failure/recovery, restricted-content reload/storage inventory, same-session
  process restart/SSE, and browser-visible isolated-HA outcome. Current
  supporting Core/API evidence is not promoted to browser evidence.
- `NOT RUN` — user-facing confirmation continuation; the existing contract
  has no safe continuation route and the UI correctly exposes unavailable state.

## Evidence boundary and remaining gap

New browser product-surface evidence is `E3_TARGET_TESTED`; supporting Core/API
evidence is `E3_TARGET_TESTED`; broader regression is `E4_REGRESSION_PROTECTED`.
Phase 12 remains `IMPLEMENTED_UNVERIFIED / CONTINUE` pending the named
browser/runtime journeys, an isolated/pristine calendar fixture result, and
Architect reconciliation of the confirmation-continuation gap. Physical-home,
native ARM64, and production-runtime claims remain outside this evidence.
