# Goal increment: owner-managed household preferences

## Intent

ANIMA now exposes a small owner-facing workflow for explicit household
preferences. This closes a practical management-plane gap for alert choices,
comfort, meals, shopping, privacy, and similar context without creating a
generic memory editor.

## Authority boundary

The workflow uses the existing `MemoryService` and the typed
`anima.household-preferences` native plugin. The browser and SENTRY receive
only bounded preference projections. Household and principal scope come from
the authenticated session or trusted `InvocationContext`; callers cannot
provide either value.

Preferences are `EXPLICIT_PREFERENCE` records with `EXPLICIT_INPUT`
provenance. Their content is context, not household Truth, authorization,
assurance, policy, permission, or device state. The memory metadata validator
rejects authority-like fields, and the plugin exposes only list, create,
correction, and retraction operations.

## Lifecycle

- Create validates normalized text to 1,000 characters and a bounded category.
- Correct creates a new active record, marks the original `SUPERSEDED`, and
  preserves the canonical correction audit trail.
- Forget transitions the active record to `RETRACTED` and removes it from
  active retrieval.
- All mutations are routed through PluginManager and the normal policy path;
  the API does not call the memory store directly for writes.

## Surfaces

- `GET /api/v1/preferences` returns active preferences for the authenticated
  household.
- `POST /api/v1/preferences/create` creates one preference.
- `POST /api/v1/preferences/update` corrects one preference by ID.
- `POST /api/v1/preferences/retract` forgets one preference by ID.
- The React Preferences view supports create, correction, and forget, and is
  refreshed through the existing bounded SSE invalidation channel.

The same registered typed capability is available to a request-bound SENTRY
catalogue. No raw SQL, filesystem, Home Assistant, provider, or policy-editing
interface is introduced.

## Deliberate limits

This increment does not infer preferences, expose all memory types, attach
preferences to permissions, or begin Phase 15. Device state and policy remain
authoritative in their existing ANIMA services.
