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

## UI behavior

The Alerts view lists current household policies, supports bounded create/edit,
and toggles enabled state through a versioned save. HTTP transport success does
not imply semantic success; the existing `MutationOutcome` notice is shown.

