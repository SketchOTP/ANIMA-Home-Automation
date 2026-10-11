# 027A owner amendment — semantic multi-signal household reasoning

## Authority and objective

On 2026-10-10 the owner directed ANIMA to move household learning beyond
counting repeated sensor types and nearby pairs. Combine qualified signals,
household relationships, event order, declared routines/mode, coverage and
preferences so SENTRY can explain the likely household situation and choose a
useful governed response. This is a continuation inside existing 027A, not a
new phase or replacement of the pending prospective-usefulness gate.

## Scenario acceptance matrix

| Scenario | Signals/context | Expected interpretation | Response boundary |
| --- | --- | --- | --- |
| Morning departure | Repeated Ring/driveway activity then a member-associated phone disconnect, around the owner's established morning routine | Likely departure preparation; work intent only if an owner routine/calendar supports it | Check actual capabilities and preferences; use only existing allowed greeting, weather, calendar, music, lighting or coffee tools; no invented tools or unapproved control |
| Logan arrival | Driveway motion, Ring motion, then Logan-associated device reconnect; no press event | Likely Logan arrival is a reasonable inference; no Ring press record is not contrary proof | Welcome once if preferences and the current speech path allow; report inference with uncertainty; phone association is not authenticated physical identity |
| Night anomaly | Source-covered outdoor quiet interval, then backyard motion and basement-window opening at 03:00; registered devices remain visible | Unusual combined situation worthy of prompt review; actor/intent remain unknown | Notify through an already approved homeowner route; no intrusion assertion, lock control or route invention |
| Declared owner travel | Explicit dates/mode; parents' devices not detected; children are expected home; repeated unusual garage/entry/backdoor signals | Evaluate the evidence against the known children-at-home context; repeated unexplained entry activity may still warrant owner attention | Notify only through the current approved route when the combination warrants; ordinary child activity is not itself a threat; offline phones are not proof that people are away |

## Cross-scenario stop conditions

- A single source, stale clock, duplicate transport receipt, incomplete source
  coverage, or missing event cannot establish identity, absence, causation or
  intrusion.
- Preserve observations separately from tentative interpretation, alternatives,
  confidence and unknowns. Do not persist hidden chain-of-thought.
- Learning review may save a source-linked hypothesis and a future observation
  target, but cannot execute an action, declare owner intent, authenticate a
  person, install an executable routine or satisfy prospective usefulness.
- Existing permission, OPA, preference, route, action-verification, no-replay,
  privacy and owner-correction boundaries remain authoritative.

## Technical scope and acceptance

- Add deterministic recurring multi-signal episode candidates from qualified
  Journal rows. Preserve order, distinct local days, signal families, event
  offsets, canonical IDs and bounded source references. Require recurrence on
  multiple days; do not learn a routine from one episode.
- Ask SENTRY to describe the likely situation, evidence-to-meaning reasoning,
  alternative, future observable check and any capability-dependent utility.
- Update live reasoning guidance for the four scenarios without bypassing the
  existing model/tool/policy paths.
- Add synthetic tests for arrival, departure, night motion/window, declared
  travel with children at home, truncated coverage and unsupported identity.
- Run relevant regression and static checks on exact clean source. Publish via
  the current ANIMA repository after exact-head hosted validation, then update
  the active instance using its established state-preserving source/runtime
  method. Never generate real household notifications/actions during tests.

## Evidence boundary

Synthetic scenarios qualify candidate construction and prompt/context contracts,
not live model reasoning or owner-perceived benefit. New hypotheses remain
unproven until genuine future observations and owner correction/use are
available. Do not rewrite earlier learning assessments or retroactively score
old prediction windows.

Starting source: ANIMA `d373364fa1ba5eff2f4f0984060883c799e2854d` (PR #1 merge;
exact-head hosted CI was still running at task start). Active Core process was
observed in the older local checkout at `/home/sketch/Projects/ANIMA Home
Automation`; unrelated local governance changes are preserved. Retrieval
confidence at start: ADEQUATE for the event candidate, live reasoning, review
prompt and action boundaries; deployment qualification remains pending.
