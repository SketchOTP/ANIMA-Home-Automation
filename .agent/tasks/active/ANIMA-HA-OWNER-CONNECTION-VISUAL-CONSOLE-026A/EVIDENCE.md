# 026A — owner connection and visual console evidence

## Scope and current disposition

This is an owner product increment, not a new resilience phase. Phases 0–14
remain Architect accepted. No whole-goal or resident SENTRY acceptance is made.
Publication identifiers are supplied in the final handoff/Notion after hosted
qualification; this record distinguishes runtime observations from fixtures.

Starting SHA: `11265fb6a9d84c7b4a0cf1d9dae99a570c32d7ed`.
Starting exact CI `34063086056` failed its stale frontend login-copy assertion.
That historical failure is retained.

## Real owner runtime observations

- HA 2026.9.0 is connected through the server-owned private credential volume.
  The actual owner was verified through HA OAuth and commissioned in a distinct
  household. No sample identity was used for these operations.
- Eight devices, five HA areas and eighteen registry entities were discovered.
- Four canonical ANIMA rooms were created through the owner UI.
- Both SONOFF SenseGuard devices were commissioned through UI → Core → policy
  → HA integration, with matching Basement/Kitchen canonical room assignments.
  PostgreSQL readback confirmed both relationships.
- At the initial state check, both upstream devices had zero registry entities;
  the HA browser itself reported “This device has no entities” for Basement.
  Commissioning does not qualify a functioning door-state feed or physical alert.
- A real owner UI → external Codex Luna helper → ANIMA read → browser response
  passed for request `b9c5b3ec-0fef-56c7-9b33-9bd40a454f6a`.
  Provider-start was recorded and the durable lifecycle reached COMPLETED.
  This is not resident SENTRY voice or persistent-persona evidence.
- A private workstation client and Unix SSH tunnel were provisioned without
  moving HA/DB/OPA or Codex login credentials. User services keep the helper
  separate from protected SENTRY. Worker failure is not automatically restarted.

## Negative results retained

- `086b964a-a023-56df-bf8a-736ce45e6a04`: Core completed the read, but the UI
  originally polled the journal event ID instead of the intelligence request ID.
  This was corrected and regression-tested before the subsequent browser pass.
- First device commission: KeyError from the generic power-control handler.
  The trusted household invocation-context adapter was missing; the correction
  passed real UI commissioning and focused legacy/current-registry tests.
- `b89d05af-d8ad-57bb-aad4-d2d83fe8381d`: conditional room creation ended
  UNKNOWN_RESULT/ANIMA_TURN_UNAVAILABLE. No Bedroom room existed on readback.
  This request was not replayed.
- `ce878704-0d24-5014-8e8d-9cc9b67c811c`: a new checked request ended
  UNKNOWN_RESULT at TOOL_INVOKE/AnimaHouseholdError. Neither failed request is
  counted as successful agent-driven configuration.
- A ten-second aggregate snapshot timeout hid successful device changes behind
  old counts. Successful mutation and failed refresh were displayed separately;
  retry recovered. A backend read-only profile did not support a single slow
  Home query as the cause. The UI's all-or-nothing refresh was a confirmed
  contributor to stale presentation, not proof of the transport-delay cause.

## Validation evidence levels

- Deterministic backend: full pytest, strict mypy, Ruff and package build.
- Deterministic worker: subprocess isolation, exact catalogue schemas,
  sequential planning budgets, restricted-content stop, safe diagnostics and
  no automatic ambiguous replay. JUnit is published in the CI artifact.
- Browser fixtures: all fifteen redesigned sections, responsive layout,
  settings application and semantic outcomes; synthetic screenshots only.
- PostgreSQL/OPA/Core browser harness: conversation, tasks, calendar,
  confirmation/rejection, restricted reload and existing accepted scenarios.
- Real owner deployment: OAuth connection, inventory, room creation,
  SenseGuard commissioning, and the real Codex read/browser response above.

Exact hosted results supersede local counts at publication. A fixture or
isolated-provider test is never promoted to physical household evidence.

## Boundaries

No arbitrary raw HA administration, model shell/code editing, firmware updates,
resident voice, persistent SENTRY conversation memory, fabricated telemetry,
notification receipt, or whole-house automation completion is claimed.
Existing history and the protected SENTRY worktree are preserved. Private owner
screenshots, raw provider payloads and credentials are excluded from Git and CI.
