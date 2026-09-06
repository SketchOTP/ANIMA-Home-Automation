# Goal increment — SENTRY text household operation

Status: implementation in progress; Phase 15 remains unauthorized.

## Product outcome

The ANIMA conversation surface now queues a request for the configured SENTRY
intelligence provider and can receive the resulting SENTRY response through a
bounded live delivery channel. The owner sees SENTRY as the responding
intelligence while ANIMA remains responsible for household identity, Truth,
policy, tools, execution, and verification.

## Boundary

The SENTRY Core service publishes a bounded PostgreSQL `NOTIFY` message after a
durable result transition. ANIMA's UI process listens only while it is running
and holds the response in memory for a short delivery window. The UI result
route first verifies the request and household against the ANIMA session and
returns no response content for another household or after the live window.

Durable intelligence records continue to retain lifecycle, status, digest,
and bounded metadata only. The live response is not placed in PostgreSQL,
AgentEpisode history, browser storage, or the Event Journal. If live delivery
is missed, ANIMA reports that honestly instead of reconstructing the response.

## Owner flow

```text
owner → ANIMA conversation
      → Journal / Attention / Context
      → durable SENTRY request
      → SENTRY provider through anima-household
      → Core result + non-durable live notification
      → authenticated ANIMA UI
      → SENTRY response
```

This is a bounded text operation. It does not add ANIMA voice, direct browser
access to Home Assistant, a second intelligence, a raw provider console, or
Phase 15 scenarios.

## Evidence boundary

The implementation is locally compile- and frontend-build-verified at the
working checkpoint. Full Python dependency validation and hosted exact-head CI
remain required before this increment can be called complete.
