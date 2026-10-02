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

## Stage4 source amendment — qualification and prospective limits

Historical R3 operational results above remain history. A dispatched request,
candidate materialization or old completion receipt is not a successful review.
Current Core request lifecycle must be COMPLETED/NO_ACTION with a qualified
terminal result, durable provider start and the bounded candidate outcomes.
Failed/ambiguous/incomplete requests remain visible and are not replayed.
Chronological keyset pages use (created_at, memory_id), not UUID-only order;
bounded enumeration fails explicitly instead of presenting a first50 as totals.

The existing owner Initiative panel and typed household-learning tools expose
review outcome and projection status, correction/retraction and prospective
shadow windows. ACK is only review, never execution approval. CORRECTED stores
explicit owner provenance; dismissal/retraction remove active retrieval and
disable the corresponding digest-checked note. Projection faults remain durable
and retry in the existing review worker with bounded backoff, not a model replay.
An owner correction remains authoritative even when its original provider review
failed. Reconciliation and later acknowledgement preserve its explicit provenance,
enabled note and retrieval; retraction still disables it. This does not qualify
the original failed review or grant executable authority.

Owner-only `freeze_shadow` requires the exact current suggestion version and a
qualified source reference. It freezes future timer opportunities, the predicted
occurrence/non-occurrence and a no-occurrence baseline in existing Memory.
Window closure is idempotent; correction invalidates dependent future windows.
Source receipts are not physical occurrence timestamps or independent trials.
Missing, stale, conflicting or truncated interval coverage cannot certify a
negative opportunity; quiet heartbeat alone is insufficient. Production does
have qualified household-scoped Journal receipts. An on-time positive receipt
evaluates a frozen source-occurrence prediction without asserting completeness
or a physical occurrence timestamp. Known-positive opportunities and complete
interval-covered opportunities are exposed separately. Unknown negatives never
improve measured accuracy. The production service has no qualified complete
interval coverage reader, so a quiet window stays UNKNOWN; a future negative
commissioning path must qualify end-to-end source continuity before supplying
the existing server-owned coverage callback. No new sensor/coverage claim is
created. Isolated complete-coverage fixtures are not household trial outcomes.
Actual future evidence remains pending until the frozen windows really elapse.

Host Core's relay configuration default is private host custody at
`~/.config/anima/vendor-relay-credential.json`. The original Compose/UI shared
UID10001 relay file is unchanged; the host loader's ownership check is unchanged.
Provisioning is parent-controlled and is not performed by this source change.
HA instance identity remains operator configuration from the existing
EnvironmentFile, not a tracked UUID or invented default. A bounded shell
regression verifies the unit launch preserves the operator-provided instance
and removes only the database password after constructing its URL. This is not
proof of effective systemd EnvironmentFile ordering. Systemd applies
EnvironmentFile values after Environment directives; a later operator
EnvironmentFile can intentionally override stale project-file endpoints without
changing the project file. The parent verified that the retained project file
already contains the commissioned instance, but its HA base/websocket values
conflict with the saved/UI loopback connection. The parent-controlled later
`core-ha-connection.env` must carry the existing instance, qualified endpoints
and version together; this source does not seed or auto-trust any connection.
With a
configured connection file, a missing/mismatched instance or base URL remains
HA_CONNECTION_CONFIGURATION_MISMATCH; parent controls actual provisioning and
installed-environment reconciliation. No new identity or credential is created.
No model, credential, private profile, unit installation or runtime mutation is
authorized by these source-only inspection features.
