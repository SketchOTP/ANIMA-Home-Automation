# Evidence — Goal Alert Policy Management 017A

Status: `COMPLETE — PENDING ARCHITECT ACCEPTANCE`

This packet records only the bounded owner-facing alert-policy increment. It
does not accept Phase 15 or alter the accepted Phase 0–14 status.

## Result

Implementation head: `95268160021f9f9b6ca97b113ffb42bb8dca1405`.

Exact-head hosted CI: `34015458746` — PASS.

Reviewable artifact: `9983867189` (`phase12-h5-evidence-95268160021f9f9b6ca97b113ffb42bb8dca1405`).

The bounded increment is implemented and validated:

- `SENSEGUARD_ALERT_MANIFEST` exposes typed `list_policies` and `save_policy`
  operations through the existing PluginManager and policy boundary.
- The authenticated API provides household-scoped list/create/update/enable/
  disable behavior with optimistic version checks.
- Household, policy identity, version, and creator provenance are server-owned;
  updates preserve the original creator.
- Resource IDs are validated in Core against commissioned Graph resources in
  the current household before a policy can be saved.
- The Alerts view supports resource selection, event type, household timezone,
  local time window, priority, guaranteed attention, delivery mode, enabled
  state, edit, and enable/disable.
- Existing normalized HA event → canonical resource → enabled policy → Journal/
  Attention routing remains unchanged.
- No raw Home Assistant automation editor, entity/service payload, credential,
  new provider, database, broker, or Phase 15 behavior was added.

Local validation passed: full Python pytest, Ruff check/format, compileall,
TypeScript, frontend unit tests, Vite production build, and `git diff --check`.

Hosted validation passed the configured exact-head workflow, including the
existing Phase 0–14 and SENTRY suites, PostgreSQL/OPA/HA checks, ARM64 image
build/runtime smoke, Docker UI validation, public-safety scan, and local UI
validation.

This is a completed implementation handoff, not Architect self-acceptance.

## Follow-on management-plane increment

The same active packet also contains the bounded commissioned-device lifecycle
slice documented in `docs/GOAL-DEVICE-LIFECYCLE-017A.md`:

- `rename_device` preserves the prior canonical name as an alias.
- `reassign_device` changes only ANIMA's active `INSTALLED_IN` topology edge,
  after server-side household and destination validation.
- `retire_device` retires the canonical resource, capabilities, provider
  references, Truth bindings, aliases, and active relationships while leaving
  the Home Assistant registry unchanged.
- The Devices view now exposes these operations for mapped devices and renders
  canonical ANIMA names rather than stale provider labels.

The focused lifecycle test, full Python pytest, Ruff, TypeScript check, and
Vite production build pass locally. This follow-on remains part of the pending
Architect review; no goal-wide or Phase 15 acceptance is claimed.

## Notification-route management follow-on

The same active packet now includes the bounded owner-facing notification-route
slice. Implementation head: `09b0c8aff5e9b9ec59a0962381cf0d34a1d14e36`.

Exact-head hosted CI: `34019264187` — PASS.

Reviewable artifact: `9985073980`
(`phase12-h5-evidence-09b0c8aff5e9b9ec59a0962381cf0d34a1d14e36`).

The slice provides:

- a PostgreSQL-backed, household-scoped route record with optimistic versioning;
- typed `list_routes` and `save_route` operations through PluginManager and
  the existing policy boundary;
- an authenticated Notifications view for label, minimum priority, and
  enabled-state management;
- server-owned `ntfy` provider and configured destination references;
- no topic, token, URL, credential, or arbitrary destination exposed to the
  browser or model;
- explicit provider attribution and no claim that a notification was received.

Local validation passed full pytest, Ruff check/format, strict mypy, compileall,
TypeScript, frontend tests, Vite production build, and `git diff --check`.
Hosted validation also passed the existing Phase 0–14, SENTRY, PostgreSQL/OPA,
isolated-HA, ARM64, Docker, safety, and UI validation workflow.

This is route management, not automatic SenseGuard-to-ntfy delivery; delivery
remains a separate existing typed capability and is not claimed here. The
increment remains pending independent Architect acceptance. Phase 15 remains
unauthorized.
