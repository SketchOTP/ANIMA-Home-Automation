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
