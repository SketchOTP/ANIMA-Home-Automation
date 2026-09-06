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
