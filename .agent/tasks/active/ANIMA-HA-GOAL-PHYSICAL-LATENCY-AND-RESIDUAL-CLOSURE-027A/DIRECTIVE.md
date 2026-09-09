# 027A — physical latency and residual closure

Status: `ACTIVE`

## Authority

Architect disposition: `CONTINUE — IMPLEMENTATION ACCEPTED; EXACT-BUILD OPERATIONAL LATENCY EVIDENCE OPEN`.

Starting accepted builds:

- ANIMA `97f0b672c20e556ced27f5c22b6499bb9d870ea7`, hosted CI `34355814121` — PASS.
- SENTRY `ed8cbab98be1a34444d2514f38e94dc8b0244272`, hosted CI `34355814092` — PASS.

## Objective

Operationally qualify the push-first mandatory-alert path with one fresh genuine
Tapo DL110 unlock on the exact accepted deployed builds. Measure from the
qualified source-event timestamp to playback-owned `tts_start_at`; the objective
is at most three seconds. Preserve durable provider-start, frozen tools, OPA,
verification authority and no-blind-replay.

After the physical measurement, reconstruct the permanent Goal against current
Notion, both repositories, deployed services and accepted evidence. Classify
every remaining requirement as `COMPLETE`, `EVIDENCE GAP`, `IMPLEMENTATION GAP`,
`EXTERNAL RESOURCE GATE`, `OWNER-ACTION GATE`, `ELAPSED-TIME GATE`, or
`DEFERRED OUTSIDE PROTOTYPE`. Close the coherent software-controllable residual
set without inventing new product scope.

The household trial started at `2026-09-09T02:21:00Z`; its three-day elapsed-time
gate must not be accelerated or inferred complete.

## Physical evidence contract

Record only bounded IDs, timestamps, statuses, counts and digests for:

```text
physical/vendor event
→ relay receipt
→ Journal
→ Attention/request
→ push wake and claim
→ durable provider-start
→ playback-owner tts_start_at
→ contextual result
→ terminal delivery/follow-up
```

No alert text, vendor notification text, household payload, transcript, model
output, audio or credentials may enter committed evidence.

## Stop boundaries

Stop on deployed-source drift, duplicate provider-start/speech/replay, speech
before provider-start, untrusted vendor prose entering mandatory TTS, weakened
request binding/policy/verification, or a latency fix that requires weakening a
safety invariant. If no fresh physical event can be obtained, finish all safe
residual work and return `BLOCKED — OWNER PHYSICAL ACTION REQUIRED`.

Do not self-declare `ANIMA_HA_PROTOTYPE_GOAL_COMPLETE`.
