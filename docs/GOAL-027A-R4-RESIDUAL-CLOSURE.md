# 027A R4 residual closure

Status: `IN_PROGRESS` — software correction locally qualified; live owner and
elapsed-time gates remain open.

Date: 2026-09-10 UTC

Retrieval confidence: `ADEQUATE`

## Scope

R4 closes the known personality/profile residuals while the exact-build Tapo
latency sample and the minimum household trial continue. It does not reopen
household learning, Phase 14, or the protected SENTRY V0.4 source tree.

## Personality boundary

Before R4, the active owner-authored profile was appended to operational SENTRY
prompts. After R4:

1. Operational direct and autonomous prompts receive neutral built-in guidance;
   profile text is structurally absent.
2. ANIMA has already accepted the structured result before any presentation
   rendering is attempted.
3. Only a harmless, tool-free, non-autonomous conversational answer may enter a
   separate ephemeral Codex presentation pass.
4. The presentation pass receives only the bounded answer and profile text. It
   runs read-only, with no user configuration, MCP, apps, browser, computer,
   shell, filesystem, memory or workspace authority, and can return only an
   `answer` field.
5. Tool choices, arguments, Truth interpretation, authority, policy,
   notification requirements, uncertainty, verification and terminal status
   remain the accepted operational result. Mandatory security, safety, failure,
   uncertainty and consequential paths bypass presentation rendering.

The presentation pass is a wording adapter, not a second household brain. A
renderer failure returns the neutral operational answer; it cannot create a
successful action or hide a governed result.

## Profile lifecycle

ANIMA now persists every newly created custom profile as inactive. Activation is
explicit and version-checked. `Built-in SENTRY` deactivates the current custom
profile without deleting saved profiles. Activation is household-scoped and
atomic; the existing active profile is not silently deactivated by migration.

Local owner API and PostgreSQL lifecycle tests cover create-inactive,
activate, stale-version rejection, built-in fallback, reactivation and
household isolation.

## Evidence ledger

| Requirement | Result | Evidence boundary |
| --- | --- | --- |
| Profile absent from operational prompts | `PASSED` | SENTRY focused tests, E3/E4 |
| Harmless ordinary answer can be styled | `PASSED` | isolated renderer contract and invoke path, E3 |
| Structured operational result cannot be changed by style | `PASSED` | renderer schema/eligibility tests, E3 |
| Sensitive and consequential paths bypass style | `PASSED` | eligibility and existing action/event regressions, E4 |
| New profiles save inactive | `PASSED` | ANIMA API/PostgreSQL tests, E3 |
| Built-in fallback is explicit and reversible | `PASSED` | ANIMA API/PostgreSQL tests, E3 |
| Full ANIMA regression after correction | `PENDING` | rerun required after final local patch |
| Full SENTRY regression | `PASSED` | qualified environment, 545 tests |
| Wake correction, ambient observation | `PASSED` | ten-minute metadata-only office observation; zero unintended transitions |
| Three deliberate exact wake attempts | `OWNER-ACTION GATE` | no physical speech evidence yet |
| Corrected eight-capture face enrollment | `OWNER-ACTION GATE` | nonblocking UX follow-up |
| Exact-build physical Tapo latency | `OWNER-ACTION GATE` | fresh unlock still required |
| Three-day household trial | `ELAPSED-TIME GATE` | cannot complete before 2026-09-12T02:21:00Z |

## Wake qualification boundary

The running office process completed a ten-minute metadata-only observation
while remaining `LISTENING`, with `last_segment_outcome` `non_wake`, empty Vosk
classification, no wake chime request and no command or Codex dispatch metadata
in the observed samples. This qualifies the unattended ambient interval only;
three exact spoken wakes and the confusing negative phrase remain open. No
ambient transcript or audio is persisted.

## Face-enrollment classification

The permanent goal explicitly requires a demonstrable voice software path with
supported test/development audio and does not require final whole-home physical
hardware deployment. Corrected live eight-capture face enrollment is therefore
classified as a `NONBLOCKING OWNER UX FOLLOW-UP`, not a permanent-goal gate.
The owner-facing physical retry remains unclaimed and is not fabricated as
E5 evidence.

## Remaining permanent-goal gates

| Item | Classification | Current boundary |
| --- | --- | --- |
| Exact-build Tapo unlock to playback-owned TTS timing | `OWNER-ACTION GATE` | requires one fresh genuine physical unlock on the published push-first build |
| Minimum three-day household event trial | `ELAPSED-TIME GATE` | earliest completion is 2026-09-12T02:21:00Z |
| Three exact spoken `Sentry` wakes and negative speech | `OWNER-ACTION GATE` | must be performed against the running office instance |
| Eight-capture live face enrollment | `OWNER-ACTION GATE` | nonblocking UX follow-up |
| Software personality/profile behavior | `COMPLETE` | locally regression-protected after R4 correction |
| R3 evidence-backed learning loop | `COMPLETE` | Architect accepted; no automatic promotion to authority |
| Phase 13 SENTRY-ready boundary | `COMPLETE` | Architect accepted |
| Phase 14 resilience/recovery | `COMPLETE` | Architect accepted; do not reopen absent regression |
| Native whole-home hardware deployment | `DEFERRED OUTSIDE PROTOTYPE` | outside adopted prototype boundary |

No permanent-goal completion is claimed by this document.

## Privacy and tooling

The R4 code and evidence do not persist hidden chain-of-thought, prompts,
transcripts, audio, raw camera captures, secrets, credentials, or restricted
vendor content. Repository-local Graft telemetry reports `off` under
`DO_NOT_TRACK=1`. Graft's authorized dirty `AGENTS.md`/`.gitignore` changes and
ignored `graft/` cache remain outside product commits.
