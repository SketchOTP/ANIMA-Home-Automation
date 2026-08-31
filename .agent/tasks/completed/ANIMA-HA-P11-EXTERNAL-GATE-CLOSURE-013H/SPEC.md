# Phase 11 external gate-closure hardening

Directive: `ANIMA-HA-P11-EXTERNAL-GATE-CLOSURE-013H`

Architect disposition is `CONTINUE`; Phase 11 remains pending Architect
acceptance. The bounded continuation replaces the manually supplied,
short-lived Calendar access token with an ANIMA-owned refreshable OAuth
boundary, expands independent Brave and Calendar live-resource reporting, and
adds actual deterministic AgentRuntime and durable-task external-follow-up
evidence.

The adopted Calendar scope is
`https://www.googleapis.com/auth/calendar.events.owned`, configured for an
operator-owned test calendar. ANIMA constructs `google-auth` credentials from
brokered `GOOGLE_CALENDAR_CLIENT_ID`, `GOOGLE_CALENDAR_CLIENT_SECRET`, and
`GOOGLE_CALENDAR_REFRESH_TOKEN` references. Ephemeral access tokens never enter
model input, audit payloads, Event Journal, Notion, or Git. Existing
SecretBroker injection is the commissioning boundary; no new secret-storage
subsystem or operator token-printing helper is introduced.

The accepted fixed-host, external-untrusted, Phase 9 write, provider choice,
Phase 10 durable-task, and Phase 12 prohibition boundaries are unchanged.
