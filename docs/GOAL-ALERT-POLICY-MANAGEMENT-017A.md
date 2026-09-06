# Goal increment — typed SenseGuard alert-policy management

ANIMA now exposes the existing typed SenseGuard policy model through its
owner-facing management plane. This closes the gap between having a safe event
router and giving the owner a way to configure it without opening the Home
Assistant frontend.

## Supported contract

The Alerts view and /api/v1/alerts/policies API support:

- canonical commissioned resource references;
- normalized event type;
- IANA household timezone;
- local time window, including overnight windows;
- priority and guaranteed-attention semantics;
- SENTRY cognition or notification delivery mode;
- enabled/disabled state;
- optimistic versioned edits and durable creator provenance.

The Notifications view and `/api/v1/notifications/routes` API also expose one
bounded household route for those policies. The owner may set its label,
minimum priority, and enabled state. The provider remains the existing
server-configured ntfy boundary; the browser cannot provide a topic, token,
URL, or other destination. Route updates use the same Core PluginManager,
OPA, CSRF, household scope, and optimistic versioning boundary.

The browser cannot choose a household, principal, role, Home Assistant entity,
service, or raw automation payload. Mutations pass through the Core plugin
catalogue, policy service, and existing PostgreSQL SenseGuard store. Disabled
policies remain durable; event matching continues to read enabled policies only.

## Boundary

A matching event still follows the existing path:

Home Assistant event → ANIMA normalization → canonical resource → typed policy
→ Journal/Attention

The policy decides whether an event deserves attention. It does not decide what
SENTRY says or what household action SENTRY may take. Current event timestamps,
household timezone conversion, provenance, and duplicate alert identity remain
owned by the existing SenseGuard router.

This increment does not add a raw Home Assistant automation editor, arbitrary
service calls, a new provider, or Phase 15 behavior. A successful ntfy provider
acceptance is not a claim that a human received the message; notification
delivery remains an external observation.

## Configured alert delivery

The `NOTIFICATION` delivery mode now dispatches a matched SenseGuard alert to
an enabled, priority-compatible route through the existing ntfy provider,
`ActionExecutionCoordinator`, `PluginManager`, and OPA boundary. The message
is server-authored from the canonical resource and recorded event timestamp;
the model and browser cannot supply a destination or arbitrary notification
body. A stable alert/route idempotency key prevents a retry from redispatching
a completed provider action. Missing routes or an unavailable ntfy provider
are recorded as `NO_ROUTE` or `UNAVAILABLE` rather than reported as delivery.

This is a narrow system-alert authorization for an owner-configured route.
Ordinary model or user `notifications.send` operations remain external
side effects requiring the existing confirmation path. Provider acceptance is
still not evidence that a human received or read the notification.
