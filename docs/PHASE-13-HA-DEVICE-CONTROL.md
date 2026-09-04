# Phase 13 HA device control

ANIMA's local interface now owns the supported Home Assistant device-onboarding
flow. The browser does not open the Home Assistant console and does not receive
an arbitrary Home Assistant service API.

## User flow

```text
ANIMA Devices view
  -> POST /api/v1/devices/permit-pairing
  -> Core PluginManager
  -> Phase 4 policy
  -> bounded ZHA permit service
  -> POST /api/v1/devices/refresh
  -> HA registry snapshot normalized by ANIMA
  -> choose discovered device + existing ANIMA room
  -> POST /api/v1/devices/commission
  -> canonical Graph resource/capability/Truth bindings
  -> Home view and semantic controls
```

The pairing window is clamped to 1–120 seconds. Commissioning accepts only a
present device from the configured Home Assistant registry and an existing
place in the authenticated household. ANIMA derives entity capabilities,
provider references, Truth bindings, and canonical IDs from the refreshed
registry; the browser supplies only the bounded display name, selected place,
and pairing duration.

## Authority boundary

`refresh_inventory` is read-only. `permit_zigbee_join` and
`commission_device` are Core-owned, policy-gated internal capabilities of the
built-in Home Assistant plugin. They are not Phase 9 physical actions because
they operate on ANIMA/HA commissioning state rather than directly asserting a
device outcome. Existing `read_state` and `set_power` semantics remain
unchanged; `set_power` continues through Phase 5, Phase 4, and Phase 9
post-action observation and verification.

There is no model- or browser-controlled host, raw service name, credential,
entity target, policy change, shell command, or arbitrary configuration
payload. Future HA configuration features must be added as separately typed,
Core-owned capabilities with their own policy and evidence contracts.

## Evidence status

The adapter and UI changes are implemented and covered by the focused and full
Python test suites plus the frontend type-check and production build. The
repository's isolated Home Assistant harness remains the authoritative route
for end-to-end provider evidence. Physical-device pairing and real-household
behavior must still be commissioned and measured against that harness; they
are not inferred from deterministic tests.

