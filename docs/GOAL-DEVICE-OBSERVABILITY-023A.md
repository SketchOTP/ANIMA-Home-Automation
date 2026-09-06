# Goal increment — device observability and governed control

## Outcome

ANIMA's Devices view now exposes the canonical capabilities and current
Truth-backed state of commissioned Home Assistant devices. Writable
`power.set` capabilities receive bounded On/Off controls that reuse the
existing authenticated ANIMA control route; the browser does not call
Home Assistant directly.

The Home room/device projection uses the same Truth resolution, so a
commissioned device is no longer presented as `UNKNOWN` when ANIMA has a
current observed state. Stale, unavailable, conflicting, and unknown Truth
remain explicitly represented rather than being converted into a success
claim.

## Boundary

The projection is read-only with respect to the provider registry. Canonical
resource IDs, semantic capability types, writability, state, Truth status, and
observation time are exposed; provider entity references, credentials, raw
Home Assistant service calls, and provider metadata are not added to the
browser contract. On/Off mutations continue through the existing Core
PluginManager, OPA, Phase 9 locking, fresh observation, and terminal-result
path.

No new provider, persistence store, browser transport, or Phase 15/SENTRY
behavior was added.

## Validation boundary

The focused backend tests, full Python test suite, Ruff, strict mypy,
TypeScript check, frontend unit tests, and production Vite build pass in the
pinned project toolchains. Exact-head hosted CI `34046105692` passed on the
published descendant `86f0cea4a5ef65b06ec5b8071789b960183b2730`; independent
Architect acceptance remains pending.

## Governance reconciliation

Documentation-only descendant `688356a876e230360a4925d844cd37c6752f8041`
records the terminal exact-head validation of this increment: hosted CI
`34047315770` passed on that exact SHA and published artifact `9993666377`.
The artifact endpoint exposed no digest. No runtime behavior changed and
independent Architect acceptance remains pending.

## Opaque provider-reference boundary — 2026-09-06

The owner-facing discovery and commissioning flow now uses a stable opaque
ANIMA `device_handle`. The browser selects that handle; Core validates it and
the Home Assistant adapter resolves the provider identifier internally. The
plugin-level refresh projection follows the same rule. The browser continues
to receive only bounded manufacturer/model metadata, canonical ANIMA mapping,
Truth state, and observation time.

The commission schema now requires `device_handle` and no longer accepts a
raw provider `device_id` from the owner-facing path. Focused tests cover
plugin refresh projection, commissioning, UI API projection, and Core gateway
handle validation. The implementation does not alter provider credentials,
Home Assistant service access, or Phase 15 behavior.

Implementation head `4ba98cc14e07eb095616352ede4c46ff0753d070` passed exact-head
hosted CI `34048949078`; artifact `9994126375` was published and no artifact
digest was exposed by the endpoint. The increment is implementation-verified
and remains pending independent Architect acceptance.
