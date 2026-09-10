# 027A R3 — continuous household learning

Status: `IMPLEMENTED / LOCALLY REGRESSION PROTECTED / LIVE CATCH-UP OBSERVED`

This increment turns qualified household history into a bounded, correctable
learning loop. It does not make Memory authoritative and it does not promote an
inference into a routine, automation, identity claim, policy rule, or physical
action.

## Product path

```text
qualified Journal observations
→ deterministic bounded feature extraction
→ source-linked pattern candidates
→ request-frozen SENTRY review packet
→ provider-start-fenced SENTRY evaluation
→ versioned Memory conclusion + Obsidian note
→ owner inspection / acknowledgement / dismissal
→ later sparse ContextPacket retrieval
```

Daily and multi-day review tasks use the existing durable-task scheduler. They
process source events not already incorporated into earlier packets, while
retaining only the bounded prior context needed to compare a candidate. A late
or out-of-order event remains eligible because incremental progress is tracked
by source identity rather than only by timestamp.

## Evidence and trust inventory

The initial catch-up inspected the live owner store. Counts below are sanitized
aggregates recorded during qualification; they are not fixture claims.

| Evidence class | Observed coverage | Learning use | Authority boundary |
| --- | ---: | --- | --- |
| Qualified SenseGuard openings | 24 observations over 4 local dates | Repetition, timing, sequence, room/resource relationships | Does not identify who opened a door/window |
| Qualified Tapo lock reports | 54 observations over 3 local dates | Lock-state repetition and sequences | Vendor report remains external, untrusted evidence; not authentication |
| Qualified Wansview motion reports | 23 observations over 3 local dates | Motion repetition and co-occurrence | No video/person identity or intent inference |
| Qualified Ring motion reports | 20 observations over 2 local dates | Motion repetition and co-occurrence | No person attribution |
| Qualified presence transitions | 0 | No presence or arrival/departure candidate was produced | Absence of evidence is not evidence that someone was away |
| Owner preferences | Existing explicit records | Agreement/disagreement context for SENTRY review | Owner statements outrank inferences; neither overrides policy |
| Owner-declared routines | One existing explicit routine at review time | Agreement/disagreement context | Separate from learned suggestions and never modified automatically |
| Existing Memory | Three managed notes before catch-up | Prior context and concept correction | Memory is context only, never Truth or authority |

All 121 raw eligible-source rows inspected after catch-up had unique source
identities. The live candidate packet used the qualified projection available at
dispatch time and retained bounded event references, evidence dates, trust,
contradictions, missing-source days and a deterministic digest.

## Deterministic candidates

`household_patterns.py` extracts at most six candidates with at most twelve
source references each. It evaluates:

- local time and day of week;
- repeated events in bounded time windows;
- event sequences within ten minutes;
- resource and room relationships;
- qualified presence transitions when available;
- observation count, distinct-day count and elapsed span;
- temporal consistency, missing source days and exact-timestamp conflicts;
- comparison inputs for owner preferences and declared routines.

Candidate maturity is derived from these observable inputs. It is not a model
probability. Duplicate event identities do not increase support. Out-of-order
events retain their actual occurrence time. Conflicting qualified observations
are exposed as contradictions rather than averaged into certainty.

## SENTRY review contract

The normal qualified SENTRY reasoning path receives the bounded packet and one
exact frozen catalogue. For each candidate it returns one structured outcome:

- `SUPPORTED_OBSERVATION`;
- `TENTATIVE_HYPOTHESIS`;
- `LEARNED_ROUTINE_SUGGESTION`;
- `INSUFFICIENT_EVIDENCE`;
- `CONTRADICTED`;
- `REJECTED`; or
- `SUPERSEDED`.

The durable result contains concise inspectable rationale, evidence categories,
contradictory and missing evidence, rejected alternatives where relevant, and
the underlying maturity inputs. Hidden chain-of-thought, prompts, transcripts,
audio, images, raw vendor prose, tool arguments/results, and secrets are not
stored.

## Durable Memory hierarchy

Learning records are synchronized into the existing managed Obsidian vault:

| Dewey class | Note type | Meaning |
| --- | --- | --- |
| `300.1` | `household_model` | Stable source-linked household understanding |
| `300.2` | `observed_pattern` | Repeated factual correlation |
| `300.3` | `hypothesis` | Tentative interpretation requiring more evidence |
| `300.4` | `learned_routine` | Owner-reviewable routine suggestion |
| `300.5` | `rejected_hypothesis` | Rejected, contradicted, or superseded interpretation |
| `100.1` | `decision` | Existing conclusion-level SENTRY decision journal |

A candidate has a stable concept identity. New evidence corrects/supersedes the
existing Memory concept and updates its digest-checked Obsidian note instead of
creating endless duplicates. Explicit owner correction remains higher priority
than an inferred pattern.

## Live initial catch-up

The explicitly labeled initial catch-up ran once against the current owner
store. It was not represented as a scheduled run.

- provider lifecycle: durable provider-start before SENTRY review;
- candidate packet: 6 bounded candidates with one digest;
- outcomes: 1 owner-reviewable learned-routine suggestion and 5 tentative
  hypotheses;
- declared routines created: 0;
- automations/actions/permissions/identity assertions created: 0;
- duplicate catch-up dispatch on repeat: 0;
- Obsidian result: 6 source-linked learning notes plus the pre-existing managed
  notes and later decision records;
- note permissions observed: `0660`;
- live contradictions in this evidence window: 0;
- qualified presence transitions: 0, therefore no inferred household-member
  attribution.

The request and packet are represented in evidence only by digests. No raw
household text or private source identifiers are committed.

## Continuous scheduling

The owner store has two active durable learning tasks:

- daily incremental review every 86,400 seconds;
- multi-day trend review every 259,200 seconds.

Dispatch is idempotent and restart-safe. Candidate generation can be repeated
without duplicating the packet, SENTRY outcome, Memory concept, or Obsidian
note. A provider-started ambiguous review cannot be blindly replayed into
knowledge. No failed or incomplete review becomes a learned conclusion.

## Owner inspection and promotion

Preferences → SENTRY initiative now shows the evidence window, events
considered, candidate classes, last/pending reviews, maturity inputs, rationale,
missing information, rejected alternatives, and the Obsidian receipt digest.
Preferences → Memory can filter household model, observed pattern, hypothesis,
learned routine, rejected hypothesis, and decision records.

Acknowledging a learned routine records owner review only. It does not install
an owner routine or automation. Dismissal prevents that conclusion from being
used as active context. System-authored records can be retracted but cannot be
edited into a different purported SENTRY conclusion.

## Later-use evidence

After the catch-up, an ordinary SENTRY browser turn asked about a recurring
SenseGuard pattern. The resulting Phase 7 ContextPacket contained one relevant
learned-routine suggestion and two tentative hypotheses, along with explicit
owner routine/preference context. Internal review packets, configuration and
completion markers were excluded. SENTRY identified the result as inferred and
uncertain and did not infer actor, cause, policy, or routine certainty.

This is operational evidence that learned Memory is retrievable and useful; it
does not elevate Memory above current Truth or OPA.

## Validation

- Complete ANIMA validation: `1169 passed, 76 skipped`; Ruff format/check and
  strict mypy across 147 source files passed.
- Focused learning/context/worker tests against an isolated migrated PostgreSQL
  store passed; one environment-dependent optional target skipped.
- Main Playwright matrix against isolated PostgreSQL/OPA: `115 passed,
  14 intentionally skipped` for desktop-only cases repeated at smaller
  viewports.
- Focused SENTRY initiative browser matrix: `42 passed` across desktop, tablet,
  and phone.
- Frontend source contract tests: `14 passed`; TypeScript and production Vite
  build passed.
- Complete SENTRY suite in its qualified environment: `542 passed`.
- Pinned `uv` sdist/wheel build, OPA `9/9`, public tracked-file safety scan,
  `git diff --check`, Docker UI build and live health passed.
- Phase 11 restricted-content verifier found zero sentinel occurrences in its
  durable PostgreSQL export. The live learning records contained zero
  prohibited payload/credential metadata keys and the managed vault contained
  zero credential-pattern files.

The first SENTRY test attempt used the host interpreter and failed because that
interpreter does not contain the qualified NumPy/OpenCV/OpenVINO runtime. It was
not counted as a product failure or pass. The same complete suite then passed
under `/home/sketch/.venvs/sentry-ubuntu/bin/python`.

## Remaining 027A gates

- A fresh exact-build physical Tapo unlock and playback-owned latency result is
  still required.
- The minimum three-day household trial cannot complete before its real elapsed
  boundary.
- Scheduled due-run evidence will accrue naturally; it is not fabricated by the
  one-time catch-up.
- Not all household phones/presence sources are commissioned. No identity or
  presence conclusions are inferred from that missing evidence.

No permanent-Goal completion is claimed by this increment.
