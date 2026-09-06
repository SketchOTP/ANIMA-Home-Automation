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
