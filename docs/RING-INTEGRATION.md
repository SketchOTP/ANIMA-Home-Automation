# Ring event-only integration — source handoff

This slice wraps the installed Home Assistant integration. It does not implement
a Ring cloud client, expose camera actions, fetch video, or identify a visitor.
No owner account login, configuration change or physical event was exercised.
Tapo/Wansview work remains paused.

## Version-qualified sources

The supported contract is HA **2026.9.0**, not the deprecated Ring binary sensors:

- [Ring setup](https://www.home-assistant.io/integrations/ring/): owner account and verification code.
- [Pinned config flow](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/ring/config_flow.py): `user` fields `username`/`password`, then `2fa` field `2fa` when required. HA owns the resulting account token.
- [Pinned HTTP flow resource](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/helpers/data_entry_flow.py): continuation receives the fields directly, not a `user_input` envelope. The new dedicated Ring connection method uses that wire shape; existing ZHA behavior is preserved.
- [Pinned Ring event entities](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/ring/event.py): ding emits `ring`, motion emits `motion`, intercom emits `intercom_unlock`.
- [Pinned EventEntity](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/event/__init__.py): entity state is HA's event receipt timestamp, and can be restored. It is not a camera-proven physical occurrence timestamp.

Disposition: WRAP HA, REUSE ANIMA adapter/Graph/Journal. No new dependency,
database, service or arbitrary HA endpoint is introduced.

## UI/API hook (lead-owned composition)

Call `install_ring_api(app, service, current_identity=current_identity,
current_session=current_session, require_mutation=require_mutation)` from the
existing UI app factory. The helper uses `service.core_runtime` dynamically and
keeps `RingSetupService(adapter, household_id)` state only for that runtime.

- `GET /api/v1/ring/status`: `configured`, `connected`, `connection_basis`,
  `state`, `can_edit`, `can_setup`, `event_entities`, `video_access:false`,
  `event_receipt_verified:false`. Configuration is evidenced by Ring inventory
  or this process's successful setup result, not an independent cloud probe.
  `connected` means HA transport with Ring configured, **not** verified Ring
  cloud delivery. No entities/entry found must not be described as working.
- `POST /api/v1/ring/setup/start` with `{}`.
- `POST /api/v1/ring/setup/continue` with
  `{setup_id, user_input:{username,password}}` or `{setup_id,user_input:{"2fa":code}}`.

FORM returns `setup_id`, `step_id:user|2fa`, fixed `fields` descriptors
(`name`, `type:text|password`, `required:true`) and safe `errors.base` codes.
SUCCEEDED returns `configured:true,refresh_required:true`; refresh discovered
inventory through the existing authorized UI action. ABORTED returns only
`ALREADY_CONFIGURED` or `SETUP_ABORTED`. The HA result, title, defaults, raw flow
ID and token never become the response.

Authenticate/session/CSRF and canonical owner membership checks precede body
parsing. Body bound is 4 KiB; fields and lengths are fixed. Flows bind principal,
household and current connection; expire after ten minutes, with at most eight
active flows. No plugin/MCP tool accepts these credentials. No raw argument audit
is created. UI must clear credentials after explicit submission and must not
persist or retry POSTs automatically. Ambiguous transport consumes the local
flow: require a fresh explicit setup. HA may retain its own flow/account state;
this does not claim memory erasure or control over HA's logs/backups.

## Event callback hook (lead-owned composition)

Construct `RingEventRouter(adapter, household_id, journal,
continuity=lambda:(online, connection_epoch, ready_at), dispatch=dispatch)` once
per runtime. `ready_at` must be the aware UTC timestamp when the current HA
snapshot/connection became ready, never a fabricated ancient time. Pass each
existing normalized adapter event to `router.handle(event)` alongside other
callbacks. `dispatch(event,journal_position)` must use exact-event, same-household
Attention with limit one, never a global pending sweep. This module does not
enable SENTRY auto-wake or alter its source allowlist.

Only active inventory entries with `platform=ring`, an `event.` identifier, and
an exact active canonical HA CAPABILITY reference exposed by a same-household
resource qualify. Input names and camera URLs do not qualify sources.

Emitted source is `anima.ring`; types are `household.ring.doorbell`,
`household.ring.motion`, `household.ring.intercom_unlock`. Payload is canonical
household/resource/capability IDs plus occurrence/receipt timestamps,
`time_basis:HA_EVENT_RECEIVED`, `physical_occurred_at:null`,
`temporal_uncertainty:true`, `physical_actor_verified:false`, and
`external_content_trust:EXTERNAL_UNTRUSTED`. DIRECT evidence means the provider
reported an event, not certainty about a person. It grants no authority.

Snapshots/recovery, timestamps before connection readiness, older than 120s,
future timestamps, unsupported entities, wrong scopes and duplicates are
suppressed. IDs derive from provider scope/entity/event timestamp/type. An
append/dispatch retry preserves its original envelope; baseline advances only
after dispatch succeeds. No replay sweep or historical learning is invented.

## Validation boundary

`tests/test_ring.py` exercises synthetic HA forms and real adapter normalization,
owner/CSRF route guards, safe errors, flow scope/expiry, event source gates,
deduplication and interrupted dispatch. The optional real PostgreSQL case uses
only `ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL` and verifies its database name
before Graph/Journal writes. External HA/Ring account and hardware qualification
remain separate live operator steps; the tests neither log in nor fetch video.
