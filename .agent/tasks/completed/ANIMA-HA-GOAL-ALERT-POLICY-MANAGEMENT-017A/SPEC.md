# Specification

## Typed alert policy contract

An alert policy contains only:

- canonical ANIMA resource references;
- normalized event type;
- IANA household timezone;
- local start/end time window;
- priority;
- guaranteed-attention flag;
- delivery mode (`SENTRY_COGNITION` or `NOTIFICATION`);
- enabled state;
- creator provenance and optimistic version.

The server owns `household_id`, `creator_principal_id`, policy identity, and
version transitions. Browser input cannot select a household, principal, role,
policy decision, or Home Assistant entity/service.

## Authority and persistence

Reads and mutations use the existing Core-owned `PluginManager`, `PolicyService`,
and `PostgresSenseGuardAlertPolicyStore`. Disabled policies remain durable for
audit/history. The event router continues to read enabled policies only.

Product content is ordinary ANIMA configuration, not restricted external
content. Existing Event Journal/Attention provenance remains authoritative.

Notification route metadata is a separate bounded owner setting. It selects
the existing server-configured ntfy provider without exposing its destination
or credentials to the browser or model. Route identity, household, creator,
and version are server-owned; label, minimum priority, and enabled state are
the only mutable fields.

## UI behavior

The Alerts view lists current household policies, supports bounded create/edit,
and toggles enabled state through a versioned save. HTTP transport success does
not imply semantic success; the existing `MutationOutcome` notice is shown.
The Notifications view provides the corresponding versioned route metadata
form and renders only `ntfy` / `server_configured` provenance.

When a matching policy uses `NOTIFICATION`, ANIMA evaluates the configured
route and priority threshold, then sends only a server-authored factual alert
through the existing coordinated ntfy provider path. The alert action has a
stable event/route idempotency key and is recorded as `notification.delivery`.
No-route and provider-unavailable outcomes are explicit. This narrow
owner-configured system-alert path is distinct from ordinary model/user
notification sends, which retain external-side-effect confirmation.
