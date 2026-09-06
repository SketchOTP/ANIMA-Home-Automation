# Handoff — Goal Alert Policy Management 017A

Status: `COMPLETE — PENDING ARCHITECT ACCEPTANCE`

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
