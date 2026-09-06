# Specification — Goal SENTRY text operation 025A

## Objective

Make the selected owner-facing SENTRY text operation usable through ANIMA's
existing authenticated conversation path without storing provider response
content durably.

## Required behavior

- UI conversation remains `Journal → Attention → Context → SENTRY request`.
- SENTRY result submission remains the only source of a SENTRY response.
- Core durably stores status and digest metadata, not response text.
- Core publishes a bounded, non-durable live result notification.
- ANIMA UI accepts only a matching authenticated household request ID.
- The browser shows SENTRY's response or an honest live-delivery omission.
- Missing SENTRY leaves other ANIMA capabilities available and does not invoke
  the embedded AgentRuntime as a silent fallback.

## Non-goals

No ANIMA voice stack, Phase 15 scenario deck, raw Home Assistant access, new
database/broker/framework, provider credential exposure, or SENTRY source-tree
modification.
