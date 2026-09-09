# Owner operational trial — 026A

## Status

`IN_PROGRESS` from `2026-09-09T02:21:00Z`. The minimum three-day review point is
`2026-09-12T02:21:00Z`. This file records a running product trial, not a claim
that several days have already elapsed.

## Unattended SENTRY event-to-TTS qualification

The first synthetic qualification request
`75378ca5-ab63-5d38-9f35-d9d173d2692a` reached the real Journal, Attention,
durable intelligence queue, provider-start boundary and SENTRY Codex turn. The
model selected a separate notification path that was absent from the frozen
catalogue. Core recorded `UNAVAILABLE`; no TTS delivery was claimed and the
request was not replayed.

The focused repair clarifies the existing channel contract: host TTS is selected
with the bounded `speak` decision, while `notify` requires a successful governed
notification tool. Request `0dcaff7c-3af4-5a17-8939-4f05b25afcdb` then followed:

```text
synthetic qualification event
→ PostgreSQL Event Journal position 9705
→ event-scoped Attention and ContextPacket
→ fresh AUTONOMOUS_ATTENTION request
→ exact auto-wake claim
→ PROVIDER_RUNNING before model execution
→ actual persistent SENTRY Codex turn
→ Core ALWAYS_NOTIFY disposition
→ decision=speak
→ warm host Kokoro speaker
→ delivery_status=DELIVERED
→ result_status=RESPONSE
```

The source event is explicitly marked synthetic and is not evidence that a
physical SenseGuard fired. The runtime path and delivery receipt are
operationally observed. The two real SenseGuard opening resources are configured
`ALWAYS`, and their single active opening policy now routes through
`SENTRY_COGNITION`; a duplicate historical opening policy is disabled so one
physical edge cannot intentionally create two announcements.

## Content-free trial ledger

SENTRY writes only request-level outcome metadata to:

```text
~/.local/state/sentry/anima-event-trial.jsonl
```

The directory is mode `0700`; the ledger is mode `0600`, opened without
following symlinks and fsynced after each record. It contains no event text,
model transcript, household payload, credentials or spoken answer.

Report command:

```bash
.venv/bin/python scripts/report_owner_event_trial.py \
  --ledger /home/sketch/.local/state/sentry/anima-event-trial.jsonl \
  --since 2026-09-09T02:21:00+00:00
```

Initial result: two unique attempts, one retained negative `UNAVAILABLE`, one
required TTS delivery, zero duplicate request records and zero required
deliveries currently unproven. Whether a discretionary announcement was useful
or unnecessary still requires owner feedback; a transport receipt cannot answer
that question.

The active Codex heartbeat `anima-household-trial-check` reviews the ledger and
runtime once per day at 09:00 America/New_York. It cannot change household
policy, infer phone ownership or promote a short run into a completed trial. The
voice edge now reports `EMPTY` while it is healthily waiting between polls;
`NOT_READY` is reserved for an actual commissioning, configuration or review
gate.

## Presence commissioning

Home Assistant's `person.tym` source is commissioned and bound to canonical user
Tym through ANIMA. Nmap provides 22 opaque router candidates, but vendor labels
and partial MAC suffixes do not establish ownership. Candiss, Jaden, Patience
and Logan are not yet canonical ANIMA users and their phones cannot be assigned
without physical one-device-at-a-time identification. ANIMA deliberately does
not guess these associations. This is the remaining owner-assisted commissioning
gate, not a missing transport or UI workflow.

## Real preferences, routines and learning

Current explicit records include:

- household Ring doorbell always-notify guidance;
- household SenseGuard opening guidance requiring concise active-SENTRY TTS,
  factual event time and canonical device identity, with no actor inference;
- two SenseGuard device rules set to `ALWAYS` for all-day opening events;
- Wansview camera rules restricted to 00:00–05:00 household-local time;
- Tapo front-door lock set to contextual SENTRY judgment;
- owner-declared Tym weekday work routine, 08:00–17:00 America/New_York.

ANIMA has observed three calendar dates, but the configured multi-day gate also
requires elapsed duration. It remains not ready and no inferred routine is
promoted as fact. Daily and multi-day review tasks are durably scheduled; their
actual due-run/provider result will be collected during this trial.

## Obsidian MEMORY qualification

The managed vault is `/home/sketch/Documents/MEMORY/ANIMA`. A real SENTRY model
turn used only ANIMA's governed knowledge tools to search and create one
source-linked note. A second real turn read the same note, copied its current
digest, corrected it in place and preserved provenance. Exactly one note with
that title exists. Raw transcripts, restricted product content, secrets and
transient state remain prohibited.

Periodic routine-learning review is `IN_PROGRESS`, not complete: the durable
daily and multi-day tasks exist, but their due executions must be observed over
the trial window before automatic review is qualified operationally.

## Trial exit review

At or after the minimum review point, report:

- required alerts versus deliveries proven;
- discretionary speech count and owner classification as useful/unnecessary;
- notification-channel receipts by route where available;
- duplicate request records;
- daily/routine review task dispatch and SENTRY result;
- memory notes created, corrected or proposed without retaining transcripts;
- presence source coverage and remaining owner-assisted mappings;
- any service restart or unavailable result, preserved as negative evidence.

The trial does not complete merely because the service stays running. Missed
alerts, unnecessary announcements and channel delivery must be reviewed from
the content-free ledger plus explicit owner feedback.

## Current qualification checkpoint

- ANIMA validation passed: Ruff, strict mypy, 1,142 pytest tests with 74
  opt-in/environment skips, OPA 9/9, sdist and wheel build, Docker UI build and
  healthy startup.
- The primary browser matrix passed 112 scenarios with 14 deliberate
  desktop-only skips. Isolated owner-product fixtures additionally passed 42
  routines, 15 presence/preferences, 3 initiative and 30 knowledge scenarios
  across the applicable desktop/tablet/phone targets.
- SENTRY passed its complete 525-test Ubuntu suite after the unattended idle
  status correction. The live service restarted with Kokoro warm, wake state
  `LISTENING`, and ANIMA event state `EMPTY`.
- ANIMA implementation `f6916d4ad0be4e5b0d1e11559df9cf0f30a292fa` plus the
  hosted-environment correction `c16919271d748d28de76494405d3b37518f4a03c`
  passed exact-head CI `34307221255`. Artifact `10087481883` has digest
  `sha256:5396f6931d0289401fff0811d577b3385aaa192eb904bcaebb099a150fabf69b`.
  SENTRY head `b2de5913d939b2cfa05ad75bc0fd7984005a579c` passed exact-head CI
  `34306897931`. The multi-day outcome remains `IN_PROGRESS`; hosted checks do
  not replace elapsed household evidence.
