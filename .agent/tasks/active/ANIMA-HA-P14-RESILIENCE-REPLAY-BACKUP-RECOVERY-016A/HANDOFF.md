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
