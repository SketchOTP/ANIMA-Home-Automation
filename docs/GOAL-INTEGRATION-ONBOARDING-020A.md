# Goal increment — bounded ZHA integration setup

ANIMA now exposes the first supported integration-setup workflow from its
authenticated Integrations view. The workflow is deliberately limited to
Home Assistant's ZHA config flow, which is the setup path required by the
Sonoff Zigbee coordinator and SenseGuard devices in the prototype.

## Supported contract

- The browser can start and continue only the fixed `zha` handler.
- Core keeps the Home Assistant access token, endpoint, and provider flow ID.
- The browser receives only an opaque ANIMA setup handle and a bounded field
  description for the current step.
- Accepted input is limited to the serial device path, offered radio type,
  bounded baud rate, and bounded flow-control mode.
- Unsupported or rejected Home Assistant steps become explicit failures; they
  are not passed through as a generic administrator/configuration interface.
- A successful flow is followed by Core reconciliation, and the existing
  device pairing/commissioning workflow remains in the Devices view.

## Authority boundary

The path is authenticated ANIMA UI → Core UI gateway → PluginManager → OPA →
Home Assistant. No browser or model input can select a host, token, arbitrary
handler, entity, service, SQL statement, or raw configuration payload. Setup
handles are process-local and expire when the provider runtime is reconstructed;
an interrupted flow must be restarted rather than silently resumed.

Home Assistant documents config flows as the normal integration setup
mechanism and exposes the flow through its authenticated config-flow API:
[config flows](https://developers.home-assistant.io/docs/core/integration/config_flow/),
[data-entry flows](https://developers.home-assistant.io/docs/data_entry_flow_index/),
and the [WebSocket API](https://developers.home-assistant.io/docs/api/websocket/).
ANIMA wraps only the supported ZHA subset and does not mirror the Home
Assistant administrator UI.

## Validation status

- Full Python pytest: 232 passed locally.
- Ruff check and format, strict mypy, TypeScript, frontend tests, Vite build,
  compile check, and `git diff --check` passed locally.
- The focused provider test proves the HA flow reference remains private,
  unsafe serial paths are rejected, and a bounded completion is reconciled.
- Exact hosted qualification completed on implementation head
  `9a152d548549b13a69584cca34d186b49837ab70` with CI run `34036396342`.
  Reviewable artifact `9990480601` has digest
  `sha256:6f82097ddf081f3877827aac5382f63896b42ec9ee753cfc00a34323de1ab13b`.
  This remains implementation evidence pending independent Architect
  acceptance. Phase 15 remains unauthorized.
