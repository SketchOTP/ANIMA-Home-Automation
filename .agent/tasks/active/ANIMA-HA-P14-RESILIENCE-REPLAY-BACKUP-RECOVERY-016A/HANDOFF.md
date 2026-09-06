# Handoff - ANIMA-HA-P14-DESTRUCTIVE-QUALIFICATION-016A-R1

Verdict: CONTINUE - DESTRUCTIVE QUALIFICATION PARTIALLY EXECUTED

Starting ANIMA:
d63c5f090a5ea5133d9ca76e5c597e1d0b54748d

Implementation/evidence checkpoint:
d3701184439f084c591044eff7f3c36d91f4b1f7

Hosted CI on that exact checkpoint:
33958140497 - PASS
Artifact 9967105897; digest sha256:6d838a098beb157b05e3d881887cfe5600644110031927645e67025d94fcc9f5

The final governance head and its exact CI are recorded in the Codex handoff and authority readback after this packet update.

This continuation retained the Phase 14 foundation, corrected the scenario
schema to carry resource locks, independent failpoints, restart points,
durable-record expectations, process identity, policy references, dispatch
metadata, verification metadata, and tested SHA, and corrected the Phase 6
verifier for the current Home Assistant registry behavior.

Real isolated PostgreSQL/OPA, Phase 1/4/9/10, Home Assistant, 80-record
task/calendar, and actual pg_dump/pg_restore evidence is recorded in
EVIDENCE.md. The five foundation scenarios remain
DETERMINISTIC_CONTRACT only.

Open software-controllable acceptance targets include the complete approval,
action, event-ordering, plugin, external-content, SENTRY, process-restart,
real-store replay, and ARM64 matrices. Phase 14 remains active and Phase 15
is unauthorized. No Phase 15 behavior, ANIMA voice, or protected SENTRY
source modification was performed.


## R2 continuation result

Verdict: `CONTINUE — FINAL DESTRUCTIVE QUALIFICATION PARTIALLY EXECUTED`.

The structural task/calendar defect is repaired with stable cursor pagination and a real 250/250 PostgreSQL traversal. The R2 real-store ledger passes 13 scenarios and is stored in `R2_REAL_STORE_LEDGER.json`. Phase 14 remains active because the approval/action crash windows, HA/SENTRY outage and restart matrices, plugin isolation, external-content attack matrix, clean-store replay set, and ARM64 runtime/replay remain open. Phase 15 remains unauthorized and unimplemented.

## R2 supplemental qualification

The real PostgreSQL approval ownership race now passes through the existing
pending-approval store and challenge issuer: concurrent approval and rejection
has one durable winner and zero provider dispatches. A fresh custom-format
PostgreSQL dump restored into a clean pinned PostgreSQL container with journal,
Truth, task, and calendar continuity. PostgreSQL and OPA restart checks also
returned healthy with journal continuity. The full Phase 14 exit gate remains
CONTINUE; these results do not claim completion of the remaining crash,
outage, plugin, attack, process-matrix, replay, or ARM64 runtime targets.

The external failure qualification also passes on the real journal-backed
adapter path: timeout, malformed response, and 5xx failures are explicit;
hostile/restricted content remains untrusted/restricted; audit records contain
no raw sentinel; and Overpass remains available when SearXNG fails. This does
not close HA, notification, SENTRY, or full process isolation scenarios.

The real service-restart target also passes: PostgreSQL and OPA were restarted
as actual Compose services, returned healthy, and preserved journal continuity.
This is idle continuity evidence only; the in-flight restart matrix remains
open.

The real action-recovery target passes through PostgreSQL, OPA, and the action
coordinator: pre-dispatch recovery is safe, started/possibly-dispatched work
is not retried, verification mismatch is reported as
`VERIFICATION_FAILED`, and durable success is idempotent. The remaining
approval continuation, HA, SENTRY, plugin, and in-flight process matrices are
still open.

## R2 event and plugin increment

The real PostgreSQL event/plugin verifier passes duplicate event and source-ID
deduplication, out-of-order Truth resolution by source sequence, journal
append-before-projection recovery with one observation, and duplicate
guaranteed SenseGuard-style Attention with one trigger. It also passes
three-class plugin failure isolation: Home Assistant, external-read, and
notification-side-effect failures leave an unrelated healthy plugin available,
with durable `plugin.failed` audit records. This is a bounded real-store
increment; Phase 14 remains `CONTINUE` until the remaining outage, SENTRY,
process, replay, and ARM64 runtime matrices are executed.

## R2 clean-store replay increment

Two independent disposable pinned PostgreSQL environments each received all
22 migrations and the real 13-scenario R2 store verifier. Durable behavior
fingerprints matched at
`06b1ed74d115f5fdc7ca2b2847fc134e0f5131cb6067724a2df7fea5ffcac806`, and an
intentional terminal-state change was detected as a machine-readable
divergence. This is real-store replay evidence; the remaining Phase 14
process, SENTRY/HA outage, and ARM64 runtime matrices remain open.

## R2 SENTRY bridge restart increment

The actual ANIMA Attention bridge process now has a bounded isolated consumer
option for test qualification. A unique guaranteed event was processed by
the real `anima_ha.sentry_bridge --once` process before and after a process
restart; one durable SENTRY request remained, with no model invocation and no
embedded fallback. Full provider-running/model and in-flight process
recovery remain open.

## R2 isolated HA outage increment

The real isolated-HA outage target passed: an action whose latest-state refresh
ran while HA was disconnected became `UNKNOWN_RESULT` with zero dispatches;
after adapter reconnect, replay returned the durable result without dispatch
and a fresh state read remained `off`. This closes only the exercised
no-redispatch boundary; the full in-flight process and SENTRY provider outage
matrices remain open.

## R2 SENTRY provider crash increment

The real PostgreSQL SENTRY bridge boundary was exercised in a child process.
The provider callback was reached only after the durable `PROVIDER_RUNNING`
transition, then the child terminated before result submission. Lease recovery
produced `UNKNOWN_RESULT`, returned no reclaimable work, and invoked no second
provider callback. This is deterministic provider-crash evidence and does not
claim a live SENTRY model turn. Phase 14 remains `CONTINUE`.

The next hosted increment also runs the actual Compose process restart matrix
for PostgreSQL, OPA, SearXNG, and the ANIMA UI. It records container
start-identity changes, service health recovery, and Journal continuity. This
is service-continuity evidence only; the complete in-flight process matrix
remains open.

The initial hosted attempt (`33980726478` on `59a72fe...`) exposed a workflow
ordering defect: the UI health-check cleanup trap stopped the UI before the
restart matrix began. That attempt is retained as a harness failure, and the
workflow now keeps UI alive through the matrix with always-run cleanup.

## Current exact hosted handoff checkpoint

The exact hosted checkpoint is `631d6de89ca6591ade1afe273aa1fe2c98a4d352`,
CI `33983789113` (PASS), artifact `9974663615`. This checkpoint adds and
passes the real OPA outage fail-closed target and the real isolated-HA Phase 9
opposing-request concurrency target. It preserves the R2 real-store ledger,
clean-store replay, event/plugin, external attack, HA outage, SENTRY bridge/
provider crash, service restart, 250/250 pagination, and ARM64 image evidence.

The honest disposition remains `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`.
The active packet is not moved to completed and Phase 15 is not started. Open
software targets are the full approval/continuation crash matrix, SENTRY outage
with local-platform continuity, complete in-flight process restart coverage,
broader attack/restricted-content coverage, and ARM64 replay/runtime evidence.
R1 backup/restore remains accepted carry-forward evidence. The local checkout's
Docker bind-mount failure on the GVFS/SFTP path is an environment limitation;
hosted CI is the authoritative execution source.

## Latest exact governed handoff checkpoint

The current head is `194079699b9c55e5e4311fd5a0454729ecd4cac3`, matching
`origin/main`, with exact-head CI `33984850396` passing. Artifact `9974957442`
is reviewable. The run includes the corrected ARM64 runtime-import smoke as
well as the real OPA outage, real-store replay, event/plugin isolation, HA
outage/no-redispatch, SENTRY bridge/provider crash, service continuity, and
250-record pagination evidence. It does not claim the remaining full
approval/continuation crash matrix, SENTRY outage/local-platform continuity,
complete in-flight process restart matrix, broader attack/restricted-content
matrix, or ARM64 replay/runtime beyond import smoke.

Disposition: `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`. The active packet
is not moved to completed. Phase 15 was not implemented. R1 backup/restore
remains carry-forward evidence and native Pi 5 remains an external gate.

## Latest exact-head correction checkpoint

The current governed head is `0283b648620e18ae4b771b9099673ec4d81eac88`,
matching `origin/main`, with exact-head hosted CI `33991073890` passing and
artifact `9976506229` published. The SENTRY provider-crash qualification now
uses the genuine queue-level expired-provider recovery while asserting the
tested request directly, so accumulated prior pending work cannot create a
false failure. The request reaches durable `PROVIDER_RUNNING` before the child
provider callback, then recovers to `UNKNOWN_RESULT` without a second callback.

This is a narrow Phase 14 qualification correction. Phase 14 remains
`CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`; the task packet remains active.
Full approval/continuation crash coverage, broader action/manual-change proof,
complete in-flight SENTRY/HA/plugin/process coverage, broader external-content
coverage, and ARM64 replay/runtime beyond smoke remain open. Phase 15 remains
unauthorized and unimplemented.

## Out-of-process plugin qualification increment

The pushed head is `f713be88e844a8d4d663e32f7289b14a5190f0da`. The new
test-only stdio MCP fixture was exercised through the production
`PluginManager` and `McpRuntime`, not a synthetic in-process callback. The
healthy plugin was invoked, disabled/re-enabled with a different child PID,
and then kept healthy while a separate child process failed. The failing
plugin became `FAILED`, exposed no tools, and produced a durable failure audit.
Scenario: `PLUGIN_PROCESS_RESTART_AND_FAILURE_ISOLATION`; evidence:
`POSTGRES_MCP_PROCESS`; local result: `PASS`.

Hosted exact-head CI `33992570340` is running on this head. This increment is
not a Phase 14 completion claim. The active packet remains active; the full
approval/continuation, ambiguous action/HA, SENTRY/HA/plugin/process,
external-content, and ARM64 replay/runtime closure remains required. Phase 15
was not implemented.

## HA manual-change race checkpoint

Published head: `10830755f2f449b5c2a64b1f095f52a1fafb04d4`, matching
`origin/main`. Exact-head hosted CI `33996868220` passed. Artifact `9978452041`
was published with digest
`sha256:1bc74e5ebf694e7107b6eec706aa31e912a400a1adb44fb9f605cc186de495b9`.

The real isolated-HA manual-reality scenario passed: an external state change
after governed dispatch caused authoritative `VERIFICATION_FAILED`, and replay
did not redispatch. This is a bounded race result; Phase 14 remains
`CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`. Phase 15 was not implemented.

## Policy reauthorization and clustered closure checkpoint

The exact code head `cc8b0107ca9615750a580a41fc95dcbdc3722f74` passed hosted CI
`33998136623` with artifact `9978800620`. The real PostgreSQL policy-transition
scenario `POLICY_CHANGE_BEFORE_APPROVAL_NO_DISPATCH` passed: approval was
requested, current policy changed before continuation, reauthorization denied
the action, and zero provider dispatch occurred.

`docs/PHASE-14-QUALIFICATION-MATRIX.md` now groups the remaining work by shared
runtime. Phase 14 remains `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED` until
the partial approval/action, outage/process, external-content, and ARM64
families are closed and replayed at one final head. Phase 15 remains
unauthorized and unimplemented.

## Isolated HA ambiguous-dispatch checkpoint

Published head: `2a0bb87eb140883f7ccb824c1344767f07d47b38`, matching
`origin/main`. Exact-head hosted CI `33995910836` passed. Artifact `9978159486`
was published with digest
`sha256:23ae7c69bcd17dc5abe5e9c3d4950fc3f3004c8eedcc1996c581d72e6dc7a619`.

Scenario `POSSIBLE_DISPATCH_VERIFICATION_FAILED_NO_RETRY` passed at
`ISOLATED_HA_POSTGRES_OPA`: real HA dispatch occurred once, deliberate stale
observation produced authoritative `VERIFICATION_FAILED`, and replay returned
the durable failure without redispatch. The baseline counter correction and
the local absent-OPA limitation are recorded in the evidence packet.

Phase 14 remains `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`; Phase 15 was
not implemented.

## Exact-head hosted publication

The current governed head is `75a8a9b94b89cbc53be577e935b1cfb2552eff5f`,
matching `origin/main`. Exact-head CI `33993069173` passed. Artifact
`9977351837` was published with digest
`sha256:b287820e12898642f5e23b780d3c99c6fad596a579cd777eea85420c0cd021bf`.
The run passed the configured real-store, backup/restore, OPA, isolated-HA,
SENTRY, out-of-process plugin, external-content, replay, restart, ARM64,
frontend/container, H5, safety, and artifact-publication targets.

The prior `f713be8...` exact-head ARM64 failure is retained as a harness
correction record: `grep -q` closed the replay-output pipe after finding the
marker, causing a broken pipe. The corrected workflow captures the output in
a file and then checks it; the current run passed the ARM64 replay contract.

Disposition remains `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`. This
publication does not close the remaining approval/continuation, ambiguous
action/manual-reality, full in-flight SENTRY/HA/plugin/process,
external-content, or deeper ARM64 replay/runtime gates. Native Pi 5 remains
an external gate. Phase 15 was not implemented.

## Durable continuation exact-head qualification

The current head is `d9de9a11abc21700a93abb5c0297bf1a382ed70a`, matching
`origin/main`, with exact-head CI `33994352076` passing. Artifact `9977709643`
was published with digest
`sha256:19ba41615602200f9a15db47248442094019b107e8d7a34b7246eec52c49d536`.
The real PostgreSQL/process scenario
`CONTINUATION_POST_ACTION_DURABLE_NO_DUPLICATE_RESULT` passed: the child
crashed after durable action success and before continuation completion, a
wrong principal was rejected, and correct recovery returned `SUCCEEDED` with
one total dispatch and zero recovery redispatches.

Disposition remains `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`; this is a
narrow crash-window closure, not Phase 14 acceptance. The remaining approval/
continuation, ambiguous action/HA, full in-flight SENTRY/HA/plugin/process,
external-content, and deeper ARM64 replay/runtime work remains open. Phase 15
was not implemented.

## SENTRY process lifecycle checkpoint

Published head: `62533e8673a25ece7079595bd73bb3a650cb1d8c`, matching
`origin/main`. Exact-head CI `33998969482` passed. Artifact `9979026256`,
digest
`sha256:7cab468a7a6915bad3a94fcd103104a4759583f3c368aa751a496bfe3b305225`.

The real PostgreSQL process matrix
`SENTRY_PROCESS_LIFECYCLE_MATRIX_NO_BLIND_REPLAY` passed across pre-claim,
post-claim, provider-started, and durable-result child-process exits. It
proved safe reclaim only before provider work began, `UNKNOWN_RESULT` after
provider start, and no new claim after a durable result. No model or embedded
AgentRuntime ran. This remains a partial Phase 14 checkpoint; the active
packet stays active and Phase 15 remains unauthorized.

## Consolidated evidence ledger checkpoint

The current exact governed head is `d68f8205787d67b2f21ea9a7bba690b3e37f145c`,
with exact-head CI `34000279143` passing. Artifact `9979391397` has digest
`sha256:1a45b144e9cf001aad7beeef459d5517636769f7b619a68b309cce9880f5073e`.
The `PHASE14_EVIDENCE_LEDGER` found all 22 required real-store output files,
validated their machine-readable evidence, and recorded family-level coverage.
The ledger remains `CONTINUE`; it does not self-accept Phase 14 or upgrade the
remaining broader lifecycle gaps. Phase 15 remains unauthorized.

## Consolidated ledger governance publication - 2026-09-06

The current documentation/governance head is
`76453a3f38e2abfbd52dcad78f6128f97bf4af8c`, matching `origin/main`. Exact-head
hosted CI `34000794948` passed and published artifact `9979518862` with digest
`sha256:c4b2b2ba6e818b6ae37f7f488eddd0bfb55027007ee9e73a211e48a735d6cb17`.
This is a reconciled integrity/coverage checkpoint, not Phase 14 acceptance;
the active packet remains `CONTINUE` and Phase 15 remains unauthorized.

## Explicit-status ledger correction

The current code/evidence head is `527810827728fc8242fbc4069b9eecb5c8060f6a`,
matching `origin/main`, with exact-head hosted CI `34001997325` passing.
Artifact `9979858475` has digest
`sha256:c749ca63200ab46f32473e70976e107858796005cbef63153bd37ba76dc948b9`.
The approval-race evidence now emits an explicit pass status, and the ledger
auditor requires explicit pass status for every mapped scenario. All ten named
families are verified for evidence integrity at this checkpoint. The overall
Phase 14 disposition remains `CONTINUE`; this does not promote contract-only
fixtures or close broader process-state and final-replay requirements.

## Current exact-head mapped-family ledger - 2026-09-06

- PASS / exact governed code/evidence head:
  `4006bcde922eb3c86c827db5700ece2ce46e98a9`; hosted CI `34002634015` passed.
- Reviewable artifact `9979858475` has digest
  `sha256:c749ca63200ab46f32473e70976e107858796005cbef63153bd37ba76dc948b9`.
- The evidence auditor found all 22 required real-store files, no missing
  files, and no non-passing mapped scenarios. All ten mapped families are
  `VERIFIED` for their named exercised scenarios at this exact head.
- This is an evidence-integrity and coverage reconciliation only. The overall
  Phase 14 disposition remains `CONTINUE`; deterministic-contract fixtures
  remain excluded from destructive proof, and broader clustered process-state
  and final-replay closure remains open. Phase 15 remains unauthorized.

## Current exact-head governance reconciliation - 2026-09-05

The current governed head is `2f1c45231355578f33fe737708a4c94f63596887`,
matching `origin/main`, with exact-head hosted CI `34004155779` passing and
artifact `9980525065` published. Artifact metadata confirms the exact tested
SHA. This governance-only checkpoint reconciles the active handoff with the
README, `.agent/CURRENT.md`, and qualification matrix; it does not change
runtime behavior or self-accept Phase 14. The exact-head ledger reports all 22
required evidence files and all ten mapped families `VERIFIED` for their named
exercised scenarios, while deterministic-contract fixtures remain excluded
from destructive proof. Phase 15 remains unauthorized.

## Latest exact-head packet reconciliation - 2026-09-05

The current governed head is `9c26fdc3f371cd867a925e4b1a081835fc1d1913`,
matching `origin/main`, with exact-head hosted CI `34004675040` passing and
artifact `9980681769` published. Artifact metadata confirms the exact tested
SHA. This governance-only checkpoint supersedes the stale `2f1c452…` pointer
in the packet/status records; it does not change runtime behavior or
self-accept Phase 14. The evidence ledger remains a named-slice coverage
record with deterministic-contract fixtures excluded from destructive proof.
Phase 14 remains `CONTINUE` and Phase 15 remains unauthorized.
