# H5R execution evidence

## Result

`IMPLEMENTED_UNVERIFIED / CONTINUE — PRODUCT SURFACES COMPOSED; PHASE 12 EXIT EVIDENCE REMAINS PARTIAL`.

The authorized product-surface implementation is present and independently
reviewed. Phase 12 is not accepted by this directive, Phase 13 remains
unauthorized, and the canonical goal is not complete.

## Investigation

- `PASSED` — Phase 4 `ConfirmationChallenge` contract inspection: exact action
  intent binding, principal binding, expiry validation, durable PostgreSQL
  challenge storage, and single-use guarded `UPDATE` consumption.
- `PASSED` — Phase 5/8 trace inspection: confirmation is policy-gated before
  invocation and an agent episode durably finishes as `WAITING_CONFIRMATION`.
- `NOT RUN` — a user-facing confirmation continuation: no existing route or
  API contract exists, and adding one would require a material Phase 8
  continuation design. The UI therefore exposes pending state as unavailable
  and has no approval control.

## Implementation

- Added household-scoped `places_in_household()` graph traversal.
- Added semantic home read surfaces for Graph-derived rooms/devices, sanitized
  journal notifications, episode reports, action summaries, pending
  confirmation state, and capability-derived health.
- Corrected the activity widget so it renders activity rather than the future
  voice label; future voice remains explicitly unavailable.
- Added preference version 2 migration and order normalization so existing
  partial widget records retain user order while gaining newly supported
  surfaces.
- Added focused API/compatibility tests and a desktop browser acceptance test.

## Validation

- `PASSED` — Ruff on changed Python sources/tests.
- `PASSED` — 169 Python tests.
- `PASSED` — frontend TypeScript check and Vite production build.
- `PASSED` — frontend policy/unit tests (3/3).
- `PASSED` — focused desktop browser product-surface test (1/1) on a fresh
  candidate server at an isolated port, including settings persistence.
- `PASSED` — full desktop browser run for 7/8 tests; the new product-surface
  test and six existing tests passed.
- `FAILED` — existing calendar browser lifecycle test in the shared development
  database. The command returned HTTP 200, but the newly-created event was not
  in the existing first-20 display window because the database contained 34
  historical calendar rows. This is retained as negative evidence; no cleanup
  or destructive reseed was performed.
- `PASSED` — `git diff --check`.

## Evidence level

- New semantic/API behavior: `E3_TARGET_TESTED`.
- New desktop product-surface browser journey: `E3_TARGET_TESTED`.
- Broader repository regression: `E4_REGRESSION_PROTECTED`.
- No new physical-home, native ARM64, live confirmation-continuation, or
  complete H5 browser-matrix claim is made.

## Remaining gap

Phase 12 still needs the remaining decisive browser/runtime evidence from the
canonical Notion gate, a clean/pristine calendar fixture for the existing
bounded-list journey, and an Architect decision on whether a Phase 8
confirmation-continuation contract is required. The H5 implementation/evidence
and all negative evidence remain preserved.
