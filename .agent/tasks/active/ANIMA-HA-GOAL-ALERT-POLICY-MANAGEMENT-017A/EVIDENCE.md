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

## Household room/zone management follow-on

Implementation head: `4960a99d56ee49059e6e73e2b4c71e616cac8496`.

Exact-head hosted CI: `34025860330` — PASS.

Reviewable artifact: `9987176873`
(`phase12-h5-evidence-4960a99d56ee49059e6e73e2b4c71e616cac8496`).

The ANIMA-owned `household.topology` capability now provides typed
`list_spaces`, `create_space`, and `rename_space` operations through trusted
`InvocationContext`, the existing Graph/PluginManager/OPA/API boundaries, and
the authenticated Spaces UI. Graph mutations enforce household containment,
ROOM/ZONE kinds, bounded names, and sibling uniqueness; browser/model input
cannot provide household authority. The owner can create a room or zone before
commissioning a newly discovered device, so this closes the prior dependency
on an already-existing room without exposing Home Assistant administration.

Focused compile/Ruff, TypeScript, frontend tests, Vite build, and diff checks
passed. The full hosted workflow also passed the existing Phase 0–14 and
SENTRY validation, ARM64/container checks, H5 targets, and public-safety scan.
This remains implementation evidence pending independent Architect review.

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

Final governed documentation head: `549630a412cd8fc4fc69a608d67aeb31596c8fdf`.
Exact-head hosted CI: `34019836787` — PASS. This forward-only governance
follow-up changed records only.

## Final implementation correction

Current implementation head: `f808d9479735a957d47e36779ad04a5c3bc3d4b1`.
Exact-head hosted CI: `34020850164` — PASS.
Reviewable artifact: `9985597571`.

The Notifications view now presents the server-safe `server_configured`
reference as “Server configured” without exposing a destination, topic, token,
URL, or credential. This correction leaves the provider boundary unchanged.
The route-management increment remains pending Architect acceptance; automatic
delivery and human receipt are not claimed.

## Automatic configured-alert delivery follow-on

The `NOTIFICATION` SenseGuard delivery mode now uses the existing
`ActionExecutionCoordinator` → `PolicyService`/OPA → `PluginManager` → ntfy
path when a matched policy has an enabled priority-compatible route. The
server constructs the bounded factual message from the canonical resource and
event timestamp; the browser/model cannot provide a destination or arbitrary
alert body. A stable event/route idempotency key prevents duplicate provider
dispatch after retry, and `notification.delivery` records `SUCCEEDED`,
`NO_ROUTE`, or `UNAVAILABLE` outcomes.

The new narrow OPA rule authorizes only the server-generated configured-alert
semantic path (`DURABLE_SYSTEM_TASK` plus Core-owned route/policy metadata).
Ordinary user/model `notifications.send` remains confirmation-gated. Provider
acceptance does not establish human receipt. Local deterministic coverage
includes router-mode separation, no-route behavior, stable idempotency, and an
actual ntfy-plugin/action-coordinator transport with a mock provider.

Hosted qualification update:

- Implementation head: `1f29ad9ab20055cc2a5f15aee1c7bea440f78807`.
- Exact-head hosted CI: `34022620543` — PASS.
- Reviewable artifact: `9986165454`.
- The active packet remains complete pending Architect acceptance. No human
  receipt, automatic voice response, or Phase 15 behavior is claimed.

## Server-owned backup snapshot follow-on

The current bounded recovery increment adds an authenticated Backups view and
`/api/v1/backups` read/create/inspect routes. Requests cross the normal Core
gateway, PluginManager, and policy boundary. The backup plugin receives
household scope from ANIMA's trusted invocation context rather than from
browser/model arguments. PostgreSQL credentials and archive paths remain
server-owned; manifests are household-scoped and UI payloads are sanitized.

The surface creates and validates snapshots only. It does not expose restore,
database administration, archive downloads, or physical-state claims after a
restore. Restore remains a separately controlled maintenance workflow with
fresh HA reconciliation.

Hosted qualification passed on the exact implementation head:

- Implementation/final candidate: `240f29563e9a6326eb004bef367f3bd715624464`.
- Exact-head CI: `34028034777` - PASS.
- Reviewable artifact: `9987831976`
  (`phase12-h5-evidence-240f29563e9a6326eb004bef367f3bd715624464`).
- Artifact digest: `sha256:4c30e740e4f4995f4959adbb7e1ebddc4269c7b2b7632edc461d9a41034d8a34`.

## Declarative scene-management follow-on

The current goal increment adds the first reusable Scenes workflow. The
`anima.scenes` capability stores household-scoped, versioned definitions with
at most 16 canonical commissioned power resources. Scene resources are
validated by Core against the current Graph; the caller cannot provide a Home
Assistant entity, service, host, or credential.

The authenticated Scenes view supports create, edit, and apply. Applying a
scene calls the existing Core `control()` path once per step, so every step is
independently policy-gated, resource-locked, refreshed from current Truth, and
verified by Phase 9. A failed later step returns bounded `PARTIAL` evidence and
stops rather than claiming an atomic batch success.

Implementation is represented by `src/anima_ha/scenes.py`, migration
`0024_scenes.sql`, the `/api/v1/scenes` routes, and the React Scenes view.
Deterministic coverage proves household scope, commissioned-resource
validation, duplicate-resource rejection, and stale-version rejection.
This follow-on is complete pending hosted qualification and Architect review;
raw Home Assistant automation editing and advanced non-power scenes remain
outside this slice. Phase 15 remains unauthorized.

The hosted run passed deterministic validation, the existing Phase 0-14 and
SENTRY checks, ARM64/container validation, H5 targets, and the public-safety
scan. Exact-head evidence is:

- implementation/final candidate: `c59504dcb9d85daecb16972fd1dfe925431821b7`;
- hosted CI: `34030239375` — PASS;
- reviewable artifact: `9988522653`;
- artifact digest: `sha256:3c452d235a538c633840a6973f7111eae1d649df4e0abf6889f3199dd37f454d`.

The local SFTP checkout lacks a usable Python pytest interpreter, so the
hosted run is the authoritative full-regression result. This remains
implementation evidence pending independent Architect acceptance; Phase 15
remains unauthorized.
