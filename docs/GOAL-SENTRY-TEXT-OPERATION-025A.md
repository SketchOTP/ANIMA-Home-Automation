# Goal increment — SENTRY text household operation

Status: `COMPLETE — PENDING ARCHITECT ACCEPTANCE`; Phase 15 remains unauthorized.

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

Implementation head `97be56fac54a848982d5767fe792ea66083412e9` is pushed with
`main == origin/main` and a clean tree. Exact-head hosted CI `34055080097`
passed. The reviewable artifact is `9995888935`,
`phase12-h5-evidence-97be56fac54a848982d5767fe792ea66083412e9`, with digest
`sha256:9c077a0ed861bee7378ba8e79178248eab16243f1dfa80a2a0448ced29630833`.

The hosted run passed deterministic validation, strict mypy, the existing
Phase 13 boundary and MCP checks, Phase 14 regression/recovery checks,
ARM64/container checks, frontend checks, and the H5 browser validation.
Local validation was limited by the mounted checkout's unavailable Python
environment; hosted CI is the authoritative Python result.

This increment proves bounded asynchronous delivery from the ANIMA-owned
SENTRY service to the authenticated ANIMA conversation view. It does not claim
that a live external SENTRY host has been commissioned; that remains a later
runtime/resource qualification. No durable response text is introduced.
