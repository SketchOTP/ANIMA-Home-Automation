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

## R3 amendment — continuous household learning

Architect directive:
`ANIMA-HA-GOAL-PHYSICAL-LATENCY-AND-RESIDUAL-CLOSURE-027A-R3`.

This amendment remains inside 027A. It requires a continuous, evidence-backed,
correctable learning loop over the existing Journal, Truth, Graph, Memory,
routines, Attention, durable tasks, SENTRY provider boundary, Obsidian vault and
OPA. Required work is:

```text
qualified observations
→ deterministic source-linked candidates
→ serious bounded SENTRY review
→ versioned household understanding
→ daily/multi-day incremental reevaluation
→ owner inspection/promotion boundary
→ later ordinary SENTRY retrieval
```

Candidate maturity must expose observable support, distinct days, elapsed span,
temporal consistency, contradictions, source trust and missing evidence. SENTRY
may support, retain, reject, contradict or supersede a hypothesis, but it may not
fabricate evidence or persist private chain-of-thought.

The initial catch-up must use the current real store and remain explicitly
separate from scheduled-run evidence. Learned routines remain suggestions;
owner acceptance is required before any declared routine, automation, policy,
permission or physical behavior changes. Memory remains context and cannot
override Truth, identity, OPA or canonical event history.

Preserve all pre-existing local 027A work and do not open another active packet.
The physical exact-build latency and elapsed household-trial gates remain open.

## R5C amendment — persistent Android notification appliance

Architect directive:
`ANIMA-HA-GOAL-PHYSICAL-LATENCY-AND-RESIDUAL-CLOSURE-027A-R5C`.

The existing Waydroid/Tapo/Wansview notification route is a permanent
owner-local subsystem. It must recover without manual app/window babysitting
through the enabled system Waydroid container, lingering owner user session,
Android userspace services, vendor apps, private notification bridge and ANIMA
relay. Readiness must be one content-free `READY`, `DEGRADED` or `NOT_READY`
assessment with bounded reasons for each layer. No vendor API replacement,
new emulator, raw notification payload, token or credential is authorized.

The supervisor must require process presence before reporting a vendor ready,
keep startup-failure relaunches cooldown-bounded, and immediately retry an
observed healthy-to-dead process transition. The product acceptance boundary
also requires session/container/listener/relay restart qualification, a full
host reboot qualification or explicit owner operational gate, genuine Tapo and
Wansview receipt evidence where physically available, final owner wake tests,
and exact-build Tapo playback latency. Phase 15 remains unauthorized.
