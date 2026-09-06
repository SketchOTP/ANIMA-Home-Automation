# Goal increment — integration health and recovery

ANIMA's Integrations view now gives the owner a bounded operational view of
the configured Home Assistant connection and a Core-owned recovery action.
This closes an owner-facing gap without turning the browser into a Home
Assistant administrator.

## Supported contract

- Registered integrations continue to be enabled or disabled only through the
  authenticated ANIMA API, PluginManager, and policy boundary.
- The Home Assistant provider exposes only safe connection health: state,
  connected version, last successful state sync, last received event,
  subscription state, discovered/mapped counts, reconnect attempt, and an
  error category.
- The owner may request `Reconnect` for the configured Home Assistant
  integration. Core retains the token, endpoint, and connection factory,
  reconnects through the existing adapter, reconciles the registry, and
  returns the adapter's bounded health result.
- The browser and SENTRY cannot supply a host, token, entity ID, service name,
  raw configuration, or arbitrary provider payload.

## Boundaries

Home Assistant configuration and credentials remain server-owned. Reconnect is
not a raw service call and does not modify Home Assistant configuration. Device
pairing, commissioning, naming, room assignment, and supported power control
remain the separate typed workflows in the Devices view.

The Home Assistant integration uses the official WebSocket boundary already
qualified by the project. Home Assistant's current documentation describes
the WebSocket API as the command/event boundary and config flows as the normal
way integrations are configured; ANIMA intentionally exposes only the
bounded supported setup/recovery surface here.

## Validation

- Full Python tests, Ruff, strict mypy, TypeScript, frontend tests, Vite
  production build, and `git diff --check` passed locally.
- The focused provider test proves Core-owned reconnect and confirms the safe
  status projection contains neither the endpoint nor token.
- Exact hosted qualification remains required before independent Architect
  acceptance. Phase 15 remains unauthorized.
