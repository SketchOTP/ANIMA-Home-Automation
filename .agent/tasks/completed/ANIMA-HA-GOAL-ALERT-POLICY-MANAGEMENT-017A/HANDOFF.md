# Handoff — Goal Alert Policy Management 017A

Status: `COMPLETE — PENDING ARCHITECT ACCEPTANCE`

## Current owner-facing publication — explicit household preferences

Implementation/final candidate:
`e2edc65b7fc0be5b5a429e15db75f7ace5112b46`.

Exact hosted CI: `34038924040` — PASS.

Reviewable artifact: `9991255680`.

Artifact digest:
`sha256:c15af9045e32d3c9bae1d9a79552253e7cc8e9d7329e297b4506fde3bc9130bd`.

ANIMA now gives the owner a bounded Preferences view for explicit household
context. The path is authenticated UI → API → Core UI gateway →
PluginManager → OPA → canonical `MemoryService`, with list/create/correct/
retract lifecycle. Household, principal, and explicit-input provenance remain
server-owned; preference content cannot authorize actions or replace Truth.

The typed `anima.household-preferences` capability is included in the
request-bound SENTRY catalogue. It exposes bounded projections only and does
not expose raw memory, SQL, HA, filesystem, or policy controls. Local and
hosted validation passed as recorded in the evidence packet. This increment is
complete pending independent Architect acceptance; Phase 15 remains
unauthorized.

Implementation/final candidate: `95268160021f9f9b6ca97b113ffb42bb8dca1405`.

Exact hosted CI: `34015458746` — PASS.

Artifact: `9983867189`.

Handoff: the owner can now configure typed SenseGuard alert policies in ANIMA
without opening Home Assistant. The bounded path is Alerts UI → authenticated
API → Core UI gateway → PluginManager → PolicyService → PostgreSQL policy store.
The server validates each selected resource against commissioned Graph topology
and preserves household/creator/version authority. Event routing remains the
existing normalized HA event → canonical resource → enabled policy → Journal /
Attention path.

The same goal-wide packet now includes bounded ZHA integration onboarding:
Integrations UI → authenticated API → Core UI gateway → PluginManager → OPA →
Home Assistant's fixed ZHA config flow. The browser receives no HA token,
endpoint, provider flow ID, arbitrary handler, or raw configuration payload.
Only bounded serial/radio fields are accepted, and unsupported steps fail
explicitly. This setup flow is separate from the existing typed pairing and
device-commissioning workflow.

The onboarding implementation is published at
`9a152d548549b13a69584cca34d186b49837ab70`. Exact-head hosted CI
`34036396342` passed; artifact `9990480601` has digest
`sha256:6f82097ddf081f3877827aac5382f63896b42ec9ee753cfc00a34323de1ab13b`.
This remains pending independent Architect acceptance.

Limitations and next candidates: this increment does not add notification
destination management, plugin/integration administration, backup/restore UI,
scenes/automation management, or Phase 15 behavior. The current packet remains
pending independent Architect review; Phase 15 is unauthorized.

The Devices view also now provides the bounded commissioned-device lifecycle
operations described in `docs/GOAL-DEVICE-LIFECYCLE-017A.md`: rename, move to a
validated household room/zone, and retire from ANIMA while preserving the
underlying Home Assistant registry. The lifecycle follow-on is included in
this active packet so governance retains one active goal increment until the
Architect reviews the combined publication.

## Notification-route management follow-on

The owner-facing Notifications view now manages one typed, household-scoped
route through the normal authenticated API → Core UI gateway → PluginManager →
PolicyService → PostgreSQL path. The route exposes only the fixed `ntfy`
provider and a server-configured destination reference; topic, token, URL, and
other credentials never enter the browser or model context. Label, minimum
priority, enabled state, creator provenance, and optimistic version are
bounded and server-validated.

Implementation head: `09b0c8aff5e9b9ec59a0962381cf0d34a1d14e36`.
Exact hosted CI: `34019264187` — PASS.
Artifact: `9985073980`.

The implementation is complete and pending Architect acceptance. This slice
does not claim automatic alert delivery or human receipt; it manages the
notification route metadata only. Phase 15 remains unauthorized.

Final governed documentation head: `549630a412cd8fc4fc69a608d67aeb31596c8fdf`.
Exact-head hosted CI: `34019836787` — PASS. The follow-up was governance-only;
runtime behavior remains at implementation head
`09b0c8aff5e9b9ec59a0962381cf0d34a1d14e36`.

Current implementation publication: `f808d9479735a957d47e36779ad04a5c3bc3d4b1`.
Exact-head hosted CI: `34020850164` — PASS. Artifact: `9985597571`.
The presentation correction maps `server_configured` to “Server configured”
in the Notifications view. Route management remains pending Architect
acceptance; automatic delivery, human receipt, and Phase 15 are not claimed.

## Automatic configured-alert delivery follow-on

Implementation adds the bounded server-side delivery path for matched
SenseGuard policies whose delivery mode is `NOTIFICATION`. Enabled routes are
selected by household and minimum priority, then the factual alert is sent
through the existing action coordinator, OPA, PluginManager, and configured
ntfy provider. Route/event idempotency prevents duplicate dispatch on retry;
missing route and provider-unavailable states are recorded explicitly.

This does not claim human receipt. Ordinary model/user notification sends
remain confirmation-gated, and no Phase 15 behavior is implemented.

Hosted qualification update:

- Implementation head: `1f29ad9ab20055cc2a5f15aee1c7bea440f78807`.
- Exact-head hosted CI: `34022620543` — PASS.
- Reviewable artifact: `9986165454`.
- This follow-on is complete pending Architect acceptance; Phase 15 remains
  unauthorized.

## Household room/zone management follow-on

Implementation/final candidate: `4960a99d56ee49059e6e73e2b4c71e616cac8496`.
Exact-head hosted CI: `34025860330` — PASS. Artifact: `9987176873`.

The Spaces view and typed `household.topology` Core capability let the owner
create and rename bounded ROOM/ZONE resources, then select those resources
when commissioning a discovered device. The path is authenticated UI → API →
Core UI gateway → PluginManager → trusted Graph mutation; household identity
and authority remain server-owned. No Home Assistant frontend, raw HA
configuration, or new authority store is introduced. This follow-on remains
pending Architect acceptance.

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
fresh HA reconciliation. This increment remains implementation evidence
pending independent Architect acceptance; Phase 15 remains unauthorized.

Hosted qualification is complete on the exact candidate head:

- Implementation/final candidate: `240f29563e9a6326eb004bef367f3bd715624464`.
- Exact-head CI: `34028034777` - PASS.
- Reviewable artifact: `9987831976`
  (`phase12-h5-evidence-240f29563e9a6326eb004bef367f3bd715624464`).
- Artifact digest: `sha256:4c30e740e4f4995f4959adbb7e1ebddc4269c7b2b7632edc461d9a41034d8a34`.

The hosted workflow passed the existing Phase 0-14/SENTRY suites, backup
management validation, ARM64 image/runtime checks, Docker UI validation, H5
evidence targets, and public-safety scan. The implementation does not claim
restore through the browser or current physical state after restore.

## Declarative scenes follow-on

Implementation adds a household-scoped, versioned `anima.scenes` capability
and authenticated Scenes UI. Owners can compose up to 16 commissioned power
resources into a named preset and apply it through the existing per-device
Core control path. Every step remains behind PluginManager, OPA, Phase 9
locking, fresh observation, and verification; a later failure is surfaced as
`PARTIAL` and stops the sequence.

Static and frontend focused checks pass locally. The local SFTP checkout lacks
a usable Python pytest interpreter, so no local pytest claim is made. Hosted
exact-head qualification is required before Architect review. No raw HA
automation editor, provider credential, or Phase 15 behavior was added.

Hosted qualification is now complete for this scene-management follow-on:

- implementation/final candidate: `c59504dcb9d85daecb16972fd1dfe925431821b7`;
- exact-head CI: `34030239375` — PASS;
- reviewable artifact: `9988522653`;
- artifact digest: `sha256:3c452d235a538c633840a6973f7111eae1d649df4e0abf6889f3199dd37f454d`.

The scene provider remains a bounded sequential power-preset capability, not a
raw automation editor or atomic batch executor. This publication is complete
pending independent Architect acceptance; Phase 15 remains unauthorized.

## Bounded automation-management follow-on

The active goal packet now also contains the bounded automation capability
documented in `docs/GOAL-AUTOMATION-MANAGEMENT-017A.md`. Owners can create and
edit household-scoped rules that match an observed commissioned resource
state (`on`/`off`) and request one typed power action on a commissioned
resource. The Automations view uses optimistic versions and never accepts raw
Home Assistant entities, services, hosts, credentials, or arbitrary payloads.

Automation firing is Core-owned: normalized HA observation → matching enabled
rule → journaled `automation.fired` → autonomous `set_power` request → existing
PluginManager/OPA/ActionExecutionCoordinator → fresh observation and Phase 9
verification. Stable event-derived idempotency prevents duplicate dispatch;
connector acknowledgement cannot override the terminal verification result.

Focused checks pass for household isolation, commissioned-resource validation,
version conflicts, provenance, timestamps, and deterministic event identity.
This is implementation evidence pending exact-head hosted qualification and
independent Architect acceptance. It is not a raw HA automation editor or
Phase 15 behavior.

Exact-head hosted qualification is now complete:

- Implementation/final candidate: `bdb3c2430f596cf2f9ea9ee97a6656c98d06ef75`.
- Exact-head CI: `34032615735` — PASS.
- Reviewable artifact: `9989311210`.
- Artifact digest: `sha256:a576e085c3bdeb37a65b6efb857a9b980709fb8fb81586366d05f75d8df8a985`.

The hosted workflow passed the complete existing validation, including the
Phase 0–14/SENTRY suites, ARM64/container checks, H5 targets, and public-safety
scan. The automation increment is ready for independent Architect review;
Phase 15 remains unauthorized.
## Goal-wide integration health and recovery follow-on — 2026-09-06

ANIMA's Integrations view now renders server-safe Home Assistant connection
health and offers a typed Reconnect action. Core keeps the HA token and
endpoint, calls the existing adapter's supervised reconnect/reconciliation,
and returns bounded health. The browser and SENTRY cannot provide a host,
token, entity, service, or raw configuration payload.

Local Ruff, formatting, strict mypy, the full Python suite, TypeScript,
frontend tests, Vite build, and `git diff --check` passed. Hosted exact-head
qualification and independent Architect acceptance remain pending. Phase 15
remains unauthorized.

## Owner-facing alert inbox follow-on — 2026-09-06

The Alerts view now includes a bounded Alert inbox backed by the existing
PostgreSQL Event Journal. It presents matched SenseGuard events with their
canonical resource name, source-observation timestamp, priority, configured
delivery mode, and latest notification disposition when available.

The authenticated `/api/v1/alerts/events` route is household-scoped and uses
stable cursor pagination. The browser receives a sanitized read projection;
raw journal rows, credentials, Home Assistant internals, and policy authority
remain in Core. This is not an acknowledgement workflow or a human-receipt
claim. No new store/provider, raw HA editor, or Phase 15 behavior was added.

At draft time the implementation was pending exact-head hosted qualification;
that qualification is recorded below. Independent Architect acceptance remains
pending. Phase 15 remains unauthorized.

## Owner-facing alert inbox qualification

The alert inbox implementation passed exact-head hosted qualification on
`87a990f5452f85ab748a1f7ea4a88d84a03d86f4` with CI `34041527112` — PASS.
The reviewable artifact is `9992007435`, digest
`sha256:917058baa013dc3a08e7756b083c0c19b48e04c1d22e23d886c3bfe943776686`.
Local focused validation passed the alert/preferences tests, Ruff, strict
mypy, TypeScript, the Vite production build, and `git diff --check`.

This remains a bounded owner-facing projection, not a new alert store,
provider, acknowledgement workflow, raw Home Assistant editor, or Phase 15
feature. Independent Architect acceptance remains pending.

## Opaque device-handle boundary — 2026-09-06

The Devices view and commissioning flow now use stable opaque ANIMA device
handles. Browser and UI API callers do not receive or submit raw Home Assistant
registry identifiers; Core validates the handle and resolves the provider ID
inside the Home Assistant adapter. The public projection retains only safe
metadata and canonical ANIMA/Truth-backed state.

Implementation head `4ba98cc14e07eb095616352ede4c46ff0753d070` passed exact-head
hosted CI `34048949078`; artifact `9994126375` was published with no digest
available from the artifact endpoint. Focused local validation passed 42
backend tests, Ruff, strict mypy, TypeScript, frontend tests, Vite build, and
`git diff --check`. This is implementation-verified and pending independent
Architect acceptance; Phase 15 remains unauthorized and unimplemented.
