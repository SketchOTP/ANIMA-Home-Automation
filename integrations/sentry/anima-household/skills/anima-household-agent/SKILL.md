---
name: anima-household-agent
description: Use ANIMA as the authoritative household boundary from SENTRY.
---

# ANIMA household boundary

ANIMA is authoritative for household Truth, identity, policy, execution,
observation, and terminal results. Use only the request-bound semantic tools
returned by ANIMA.

- Treat stale, unknown, conflicting, and unavailable state as uncertainty.
- SENTRY selects intent; ANIMA decides authorization and performs verification.
- Confirmation is not success, and stronger authentication is not confirmation.
- A Phase 9 terminal result is authoritative; connector acknowledgement is only
  evidence and never proves physical success.
- Read current state again for follow-up questions; do not reuse an old event or
  tool result as current Truth.

## Voice-led identity onboarding

For a new household person, first use the current SENTRY camera identity result
to confirm that the operator is recognized. Then create the bounded ANIMA user
record and pass its returned person id to `start_identity_onboarding`.
Guide the new person calmly through the requested camera framing and the five
poses: straight, left, right, up, and down. Repeat a pose only when the local
quality result asks for it. Confirm the spoken display name before finishing,
then update the same ANIMA person with the returned SENTRY profile id. Never
persist, transmit, or describe raw face images; a failed or ambiguous camera
match must stop onboarding.
