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
pinned project toolchains. This increment remains implementation evidence
pending exact-head hosted validation and independent Architect acceptance.
