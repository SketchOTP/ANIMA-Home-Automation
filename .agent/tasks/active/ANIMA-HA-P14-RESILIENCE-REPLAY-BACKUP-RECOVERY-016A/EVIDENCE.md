# Evidence - Phase 14

Status: IN PROGRESS

Starting ANIMA SHA:
f0456d24fa09ed6873e882c89a9dce759f73a619

Accepted SENTRY shadow compatibility patch:
00aa9ac3a35b7b012581160b961e01a9480bbbdf

This file is append-only evidence. Results use the labels PASSED, FAILED,
NOT RUN, NOT APPLICABLE, or BLOCKED and identify exact commands and artifacts.
Full provider payloads, credentials, and restricted content are never written.

## Initial state

- Phase 13: Architect accepted.
- Phase 14: active.
- Phase 15: unauthorized and unimplemented.
- Baseline and exact-head results: pending this execution.

## Initial deterministic target - 2026-09-05

- PASSED: full pytest on the current Phase 14 worktree, including the new
  resilience tests. Result: 219 tests passed.
- PASSED: targeted Ruff for src, tests, and Phase 14 verifier.
- PASSED: strict mypy for src and tests.
- PASSED: deterministic verifier
  scripts/verify_phase14_resilience.py. Artifact is a secret-free JSON ledger
  with digest
  efa4b3d8320395827cc565bdfb2ee0827f0876687b8bd801200df1ba3e71fb62.
- PASSED scenarios: PROVIDER_PRESTART_CRASH_RECLAIM,
  PROVIDER_STARTED_CRASH_NO_REPLAY, PROVIDER_RESULT_DURABLE_NO_RERUN,
  BACKUP_SECRET_SAFE, and RESTORE_NO_SIDE_EFFECT_REPLAY. Evidence level:
  DETERMINISTIC.
- NOT RUN by this target: PostgreSQL pg_dump/pg_restore, live HA outage and
  reconciliation, SENTRY provider outage, and native ARM64 execution. These
  remain open Phase 14 targets and are not promoted by inference.
- No credentials, restricted provider payloads, or private household data were
  placed in the ledger.

## Reconstructed state

- main was at the governed starting SHA and clean before this continuation.
- Phases 0-13 were Architect accepted; Phase 14 was active; Phase 15 remained
  unauthorized and unimplemented.
- The protected SENTRY V0.4 worktree was inspected separately and not modified.

## Real execution evidence - 2026-09-05

- PASSED / POSTGRES_OPA_CORE: disposable PostgreSQL 16/pgvector and OPA were
  started on isolated ports 55433/18182, all 22 migrations applied, and the
  Phase 1 PostgreSQL integration passed: duplicate logical inserts collapsed
  to one record, append-only enforcement held, projection retry worked, and
  rebuild replayed the journal.
- PASSED / POSTGRES_OPA_CORE: provider lifecycle checks against the real store
  covered pre-provider crash reclaim, provider-start ambiguity without blind
  replay, durable result without a second model run, one concurrent claim
  winner, and stale-fence rejection across provider writes.
- PASSED / POSTGRES_OPA_CORE: Phase 4 real OPA integration passed with 15
  decision records and 15 audit events; an OPA outage failed closed with zero
  provider dispatch.
- PASSED / ISOLATED_HA: scripts/verify_phase9_action_execution.py passed
  with real PostgreSQL advisory-lock contention, contradictory requests,
  isolated Home Assistant action, observed verification, and idempotent replay.
- PASSED / POSTGRES_OPA_CORE: scripts/verify_phase10_durable_tasks.py
  passed task lifecycle parity, stale worker rejection, cancellation before
  dispatch, one concurrent claim, lease recovery, fresh scheduled context,
  fresh external read, and future Phase 9 action routing.
- PASSED / ISOLATED_HA: scripts/verify_phase6_home_assistant.py passed
  against Home Assistant 2026.8.2. It covered discovery, registry mapping,
  known/unknown/unavailable truth, OPA denial/confirmation/strong-auth gates,
  verified action, deliberate acknowledged-but-unobserved
  VERIFICATION_FAILED, disconnect/reconnect/reconcile, invalid-token
  failure, plugin disable/restore, PostgreSQL restart, and secret
  non-persistence. The current-version registry write is verified through the
  adapter's explicit reconciliation boundary when no legacy registry event is
  emitted.
- PASSED / POSTGRES_OPA_CORE: 80 task records and 80 calendar records were
  reachable from the real stores. Task pause/resume/cancel passed. Calendar
  update advanced the version, stale update raised CalendarConflict, and
  versioned cancellation passed.
- PASSED / REAL_BACKUP_RESTORE: actual pg_dump -Fc and pg_restore completed
  into a clean pinned PostgreSQL container, followed by migration verification.
  Dump size was 217705 bytes and its secret-scan SHA-256 was
  f044742805867bad15df32cb8c88cb273597b99bc200677d87d6ec3844a6a10c.
  Restored schema/history continuity included 322 journal records, 131 truth
  records, 2 action records, and all 22 schema migrations. The restore
  manifest recorded raw_secrets=false,
  physical_truth=UNKNOWN_UNTIL_REOBSERVED, and
  executed_effects_replayed=false.

## Contract evidence

- PASSED / DETERMINISTIC_CONTRACT: scripts/verify_phase14_resilience.py
  executed five contract scenarios. Its result digest was
  7f78731782ccceacea58e2acf5e110d746f4bc15dc58d21526938836df3b909c.
  These five results are explicitly contract evidence and are not promoted
  to destructive system evidence.

## Still open

The following software-controllable Phase 14 targets were not completed by
this bounded continuation and remain open: approval/continuation crash
windows; full Phase 9 concurrent/manual-change matrix; duplicate and
out-of-order SenseGuard/event replay; HA outage recovery with no redispatch;
plugin-by-plugin isolation; SENTRY bridge outage/restart and no-fallback
matrix; external-content attack matrix; full process restart matrix; real
store replay regression detection; and ARM64 build/runtime qualification.
Native Pi 5 hardware remains an external resource gate only after ARM64
qualification.

Phase 14 is not accepted. No claim of complete resilience or backup/restore
qualification is made from the open targets.

## R2 real-store qualification - 2026-09-05

- PASSED / POSTGRES_OPA_CORE: `scripts/verify_phase14_r2.py` executed against the disposable PostgreSQL 16/pgvector store on the exact implementation head `616964f395f9808ac3453b3eddc8cb8b84372767`. The 13-scenario ledger is `R2_REAL_STORE_LEDGER.json`, SHA-256 `579643f2545dcda5feb92a3f7d74f984b978a8911b8e0437892882ff5c636092`.
- PASSED: provider pre-start reclaim, provider-started ambiguity to `UNKNOWN_RESULT`, durable result without rerun, one concurrent claim winner, and stale-fence rejection across renew/transition/result.
- PASSED: real Journal duplicate suppression, newer Truth sequence selection, duplicate guaranteed Attention/SenseGuard trigger suppression, and real-store replay digest equality plus deliberate machine-readable divergence detection.
- PASSED: 250 task and 250 calendar records were traversed with stable timestamp/UUID cursor pagination at page size 37; all 500 IDs were unique and discoverable. Concurrent calendar optimistic-version update produced one winner and rejected the stale writer.
- PASSED / local: full pytest, Ruff, strict mypy, Python package build, frontend TypeScript/tests/Vite build, Phase 4 OPA integration, Phase 5 plugin integration, and the new R2 ledger. Hosted CI for this implementation head is recorded separately after completion.
- PASSED / hosted configuration: the workflow now includes the R2 real-store target and a QEMU-backed `linux/arm64` UI image build. The local host lacks ARM64 emulation, so the local attempt is recorded only as an environment failure, not as a pass.

## R2 status and carry-forward

Phase 14 remains `CONTINUE` and is not accepted. R1's accepted real backup/restore, isolated-HA Phase 9, Phase 6 HA, OPA, and durable-task evidence remains carry-forward. The following R2-required software-controlled matrices remain open unless independently rerun: approval/continuation crash windows; full action/manual-change concurrency; HA outage with no redispatch; SENTRY bridge/provider restart and outage; three-class plugin failure isolation; external-content attack matrix; complete process restart matrix; five-scenario real-store replay from clean state; and ARM64 runtime/replay beyond image build. Native Pi 5 remains an external gate only after software qualification. Phase 15 was not implemented.

## R2 carry-forward defect disposition

- `PROVIDER_AMBIGUITY`: CLOSED for the exercised real PostgreSQL provider lifecycle; full SENTRY bridge restart coverage remains open.
- `APPROVAL_CONTINUATION_CRASH_WINDOWS`: OPEN; not rerun by the R2 target.
- `PHASE9_ACTION_MANUAL_CHANGE_CONCURRENCY`: OPEN for the full R2 matrix; the accepted R1 isolated-HA lock/verification evidence is retained.
- `EVENT_DUPLICATION_ORDERING`: CLOSED for the exercised Journal/Truth/Attention/SenseGuard duplicate and newer-sequence cases; restart-between-append-and-projection remains open.
- `HA_OUTAGE_NO_REDISPATCH`: OPEN; R1 reconnect/reconciliation evidence is retained but the explicit outage/no-redispatch matrix was not rerun here.
- `PLUGIN_ISOLATION`: PARTIAL; the accepted Phase 5 plugin failure/restore evidence is retained, but the three-class R2 outage matrix remains open.
- `EXTERNAL_CONTENT_ATTACKS`: OPEN; no new R2 attack matrix was executed.
- `TASK_CALENDAR_BOUNDED_READS`: CLOSED for the fixed defect; stable cursor pagination passed over 250 tasks and 250 calendar records.
- `BACKUP_RESTORE`: RETAINED from accepted R1 real `pg_dump`/`pg_restore`; the R2 run did not falsely relabel that prior evidence as a new execution.
- `PROCESS_RESTART_AND_ARM64`: OPEN for the complete process matrix and runtime/replay qualification; hosted CI separately exercises the ARM64 image build, while native Pi 5 remains an external gate.

This reconciliation supersedes the earlier generic `Still open` summary above only where R2 explicitly records a closure; no open target is promoted by inference.

## R2 supplemental qualification - 2026-09-05

- PASSED / POSTGRES_OPA_CORE: the real PostgreSQL approval ownership race was
  rerun by `scripts/verify_phase14_approval_r2.py`. Concurrent APPROVE and
  REJECT claims produced exactly one durable winner, with zero provider
  dispatches. The target uses the existing PostgreSQL pending-approval store
  and challenge issuer; it is not a contract-only fixture.
- PASSED / REAL_BACKUP_RESTORE: a fresh custom-format PostgreSQL dump was
  created from the isolated Phase 14 database using the pinned PostgreSQL
  client in the database container. Dump SHA-256 was
  `1d3f26f0e8dd90707191afe821944142c632c1b7b21392d67d753207b8fa807f`.
  Restore into a clean `pgvector/pgvector:pg16-bookworm` container completed
  successfully; restored counts were 1910 journal, 142 truth, 1256 tasks, and
  1255 calendar records. The restore container was removed after validation.
- PASSED / POSTGRES_OPA_CORE: PostgreSQL and OPA were independently restarted
  and returned healthy; journal query continuity remained available after the
  restarts. This is bounded service restart evidence, not the complete
  in-flight process matrix.
- PASSED / POSTGRES_OPA_CORE: the accepted H5U confirmation and H5V resume
  targets were rerun against disposable PostgreSQL/OPA. Approval continuation
  produced one action dispatch and SUCCEEDED; rejection produced no provider
  dispatch. These remain carry-forward continuation evidence, while the full
  crash-window matrix remains open.

The approval race is now included in hosted CI after the R2 real-store target.
The complete Phase 14 destructive closure is still open: SENTRY bridge and
provider restarts, HA outage/no-redispatch, three-class plugin isolation,
external-content attacks, full process restart coverage, clean-store replay
coverage, and ARM64 runtime/replay qualification remain to be executed.

## R2 external failure qualification - 2026-09-05

- PASSED / POSTGRES_OPA_CORE: `scripts/verify_phase14_external_r2.py` drove the
  existing bounded SearXNG adapter through timeout, malformed JSON, and HTTP
  5xx responses. Each failed explicitly; none became a successful result.
- PASSED / POSTGRES_OPA_CORE: hostile provider text remained
  `EXTERNAL_UNTRUSTED`, and a UPCitemdb-like result remained
  `EPHEMERAL_RESTRICTED`. The hostile/restricted sentinel appeared only in
  the in-memory provider result; the six persisted `external.request.audit`
  events contained no raw sentinel and retained only accepted request digests
  and metadata.
- PASSED / POSTGRES_OPA_CORE: a SearXNG 5xx did not prevent an independent
  Overpass adapter from returning a normalized place result. This is provider
  independence evidence, not the complete three-class plugin outage matrix.

The external target is now included in hosted CI. HA adapter outage,
notification-side-effect outage, full plugin lifecycle isolation, SENTRY
bridge/provider restart, and process-level recovery remain open.

## R2 service-restart qualification - 2026-09-05

- PASSED / POSTGRES_OPA_CORE: `scripts/verify_phase14_service_restart_r2.py`
  restarted the actual PostgreSQL and OPA Compose services, waited for both
  health checks, and queried the real journal afterward. Container identities
  remained stable while service start timestamps advanced; journal continuity
  remained available with 1924 records before and after the restart.

This target is included in hosted CI. It covers idle service continuity only;
the required in-flight Core, SENTRY bridge, HA, plugin, approval, verification,
and due-task restart states remain open.

## R2 action recovery qualification - 2026-09-05

- PASSED / POSTGRES_OPA_CORE: `scripts/verify_phase14_action_recovery_r2.py`
  exercised the real PostgreSQL action store with the actual coordinator and
  OPA policy client. A planned pre-dispatch crash recovered as
  `RECOVERY_REQUIRED` without dispatch; an executing/started crash recovered as
  `UNKNOWN_RESULT` without dispatch; connector acknowledgement followed by a
  mismatching fresh Truth observation produced `VERIFICATION_FAILED`; a
  possibly-dispatched provider failure produced `UNKNOWN_RESULT`; and a
  durable `SUCCEEDED` action was not dispatched again on replay.

The action-recovery target is included in hosted CI. Full approval continuation
crash windows, manual-change races, HA outage/no-redispatch, and process-level
in-flight restart coverage remain open.

## R2 event replay and plugin isolation - 2026-09-05

- PASSED / POSTGRES_JOURNAL_TRUTH_ATTENTION: the new
  `scripts/verify_phase14_events_plugins_r2.py` ran against the real
  PostgreSQL stores. Duplicate event IDs and duplicate source IDs collapsed
  to one journal record. An out-of-order pair resolved to the higher source
  sequence, independent of journal arrival order.
- PASSED / POSTGRES_JOURNAL_TRUTH_ATTENTION: a durable journal append was
  followed by projector reconstruction and pending projection; the unique
  observation was persisted exactly once. A duplicate guaranteed
  SenseGuard-style event produced one Attention trigger.
- PASSED / POSTGRES_JOURNAL_TRUTH_ATTENTION: three separately registered
  failing plugin classes (Home Assistant, external read, and notification
  side-effect) entered `FAILED`, while an unrelated healthy plugin remained
  `HEALTHY` and retained its tool. `plugin.failed` audit events were durable
  in the PostgreSQL journal.

The target is now included in the hosted CI workflow on the next pushed head.
This closes the exercised real event-deduplication/projection-restart and
three-class plugin-isolation slices, but does not close the remaining HA
outage/no-redispatch, SENTRY restart, full process matrix, or clean-store
replay requirements.

## R2 clean-store replay - 2026-09-05

- PASSED / REAL_STORE_REPLAY: `scripts/verify_phase14_clean_replay_r2.py`
  created two independent disposable PostgreSQL 16/pgvector containers,
  applied all 22 repository migrations in each, and ran the existing
  PostgreSQL-backed 13-scenario R2 verifier from a fresh database twice.
  Normalized durable behavior fingerprints matched with digest
  `06b1ed74d115f5fdc7ca2b2847fc134e0f5131cb6067724a2df7fea5ffcac806`.
- PASSED: the replay comparator detected a deliberate expected terminal-state
  divergence for `PROVIDER_PRESTART_CRASH_RECLAIM` as a machine-readable
  difference. UUIDs and timestamps were excluded from the comparison; the
  scenario behavior, transitions, recovery classification, side-effect
  counts, and evidence level were compared.

This target is included in hosted CI on the next pushed head. It materially
closes the clean-store replay subset but does not claim the full Phase 14
process-restart or SENTRY/HA outage matrices.

## R2 SENTRY bridge restart - 2026-09-05

- PASSED / POSTGRES_PROCESS: `scripts/verify_phase14_sentry_bridge_restart_r2.py`
  appended a unique guaranteed user event, started the actual
  `anima_ha.sentry_bridge --once` process, verified one durable SENTRY
  intelligence request, then restarted the bridge process against the same
  PostgreSQL store. The second pass left the request count at one, proving
  Attention/request idempotency across this bridge restart boundary.
- The bridge now accepts a bounded `--consumer-name` for isolated test
  consumers; the default remains `sentry-attention`. No model was invoked and
  no embedded AgentRuntime fallback was used, so this is bridge-process
  restart evidence rather than live SENTRY model evidence.

The target is included in hosted CI on the next pushed head. Full SENTRY
provider-running ambiguity, model outage, and in-flight process coverage
remain open.

## R2 isolated HA outage - 2026-09-05

- PASSED / ISOLATED_HA_POSTGRES_OPA: `scripts/verify_phase14_ha_outage_r2.py`
  used a newly provisioned Home Assistant container, the real HA adapter,
  PluginManager, ActionExecutionCoordinator, PostgreSQL action store/resource
  lock, and live OPA. After establishing an observed `off` state, HA was
  stopped before a governed `on` action. The coordinator recorded
  `UNKNOWN_RESULT` before provider dispatch (`provider_dispatches=0`).
- PASSED: HA restarted and the adapter reconnected to `ONLINE`; replaying the
  same action returned the durable unknown result with `duplicate=true`, still
  at zero dispatches, and the fresh observed state remained `off`.

This closes the exercised HA outage/no-redispatch boundary. It does not close
the complete in-flight HA/process restart matrix or SENTRY provider outage.

## R2 SENTRY provider crash boundary - 2026-09-05

- PASSED / POSTGRES_PROCESS: `scripts/verify_phase14_sentry_provider_crash_r2.py`
  ran the actual `SentryBridgeWorker`, `CoreSentryBoundary`, and PostgreSQL
  intelligence store in a child process. The durable transition to
  `PROVIDER_RUNNING` was present before the deterministic provider callback
  started; the child then terminated before submitting a result.
- PASSED: after the lease was expired, the real store classified the request as
  `UNKNOWN_RESULT`; no reclaimer claim was returned and no second provider
  callback occurred. This is provider-started crash/no-blind-replay evidence,
  not live Codex/SENTRY model evidence.

The new target and the isolated-HA outage target are queued for the next exact
head hosted run. The full SENTRY provider outage and process matrix remain
open.

## R2 service process restart matrix - 2026-09-05

- ADDED / POSTGRES_PROCESS: `scripts/verify_phase14_process_matrix_r2.py`
  restarts the actual Compose PostgreSQL, OPA, SearXNG, and ANIMA UI services
  independently. It captures container identity/start time before and after
  each restart, waits for the service-specific health condition, and checks
  PostgreSQL Journal continuity.
- This target is intentionally continuity evidence for service processes; it
  does not claim the pending/claimed/provider-running/confirmation in-flight
  matrix, which remains open.

The first hosted attempt on `59a72fe6352f819dd008ee83da6b357ac283dea3`
(`33980726478`) reached this target but failed during setup because the prior
UI health-check step's cleanup trap had already stopped the UI container. This
was a workflow-ordering defect, not a process-recovery result. The workflow is
corrected to keep UI running through the matrix and stop it afterward with an
always-run cleanup step; the failed attempt is retained as harness evidence.

## R2 exact hosted qualification checkpoint - 2026-09-05

- PASS / exact governed head: `631d6de89ca6591ade1afe273aa1fe2c98a4d352`.
  Hosted CI `33983789113` passed all configured validation, real-store,
  isolated-HA, SENTRY bridge/provider, external-content, replay, process,
  container, frontend, safety, and ARM64-image targets. Artifact `9974663615`
  (`phase12-h5-evidence-631d6de89ca6591ade1afe273aa1fe2c98a4d352`) was
  published. Key artifact file digests include
  `phase14-opa-outage-r2.json` =
  `c4a90cd36aaadd2116f1fe052bcd97be659540690b8167aa00ba3e3ab158487e` and
  `phase14-r2-real-store.json` =
  `abeab186bfe90241c242b5d5dcef4e05d2c70c3376194673cc8ae8a869dee917`.
- PASS / `POSTGRES_PROCESS`: `OPA_OUTAGE_FAIL_CLOSED` stopped and restored
  the real Compose OPA service. The action ended `POLICY_DENIED`, the durable
  policy audit reason was `POLICY_UNAVAILABLE`, and provider dispatch count was
  zero. The existing isolated-HA Phase 9 harness also passed with real
  opposing requests: Alex's `on` completed after observed verification, Sam's
  concurrent `off` returned `RESOURCE_BUSY`, and replay produced no second
  dispatch.
- The prior exact-head run `33982491397` on `da930ed...` remains retained as
  an earlier pass; the failed `33983161135` and `33983378308` attempts remain
  harness-failure evidence only. They do not alter the current result.

## R2 current carry-forward reconciliation

Phase 14 remains `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`; this packet
is still active and Phase 15 remains unauthorized. R2 now has real hosted
evidence for provider fencing/crash, action recovery, approval ownership race,
OPA outage fail-closed, isolated-HA outage/no-redispatch, Phase 9 concurrency,
event/Truth/Attention replay, three-class plugin isolation, external failure
and attack handling, 250-record stable pagination, clean-store replay with
machine-readable divergence detection, bridge restart, service continuity,
and the ARM64 UI image build. The remaining software-controllable closure
items are explicit rather than inferred: full approval/continuation crash-window
coverage, SENTRY outage/local-platform continuity, the complete in-flight
process restart matrix, broader external-content/restricted attack coverage,
and ARM64 replay/runtime beyond the image-build evidence. R1's real backup/
restore evidence remains valid carry-forward but was not relabeled as a new R2
execution. Native Pi 5 hardware remains an external gate only.

## R2 latest exact hosted publication checkpoint

The current governed head is `194079699b9c55e5e4311fd5a0454729ecd4cac3`, and
`origin/main` matches it. Exact-head hosted CI `33984850396` passed. Artifact
`9974957442` is the current reviewable output. Selected evidence hashes are:

- `phase14-opa-outage-r2.json`:
  `c4a90cd36aaadd2116f1fe052bcd97be659540690b8167aa00ba3e3ab158487e`;
- `phase14-r2-real-store.json`:
  `c0670fd42946cd472d8cfbc4faf1112f677f9e4b27f5fc54241fbbd906c6d0f2`;
- `phase14-process-matrix-r2.json`:
  `d3087fa5c06e485629601d54240d64dd9b52ab42d3a53e3a5377205c2ce75b4a`.

This exact run passed the corrected `linux/arm64` runtime import smoke after
the ARM64 UI image build. It also passed the real OPA outage target, where
`POLICY_UNAVAILABLE` produced `POLICY_DENIED` with zero provider dispatch, the
13-scenario real-store ledger, and the service-continuity process matrix. This
supersedes `631d6de...` as the current hosted checkpoint without removing its
historical evidence.

The honest disposition remains `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`.
The active packet remains active and Phase 15 remains unauthorized. Open
software-controllable work is the complete approval/continuation crash matrix,
SENTRY outage with local-platform continuity, full in-flight process restart
coverage, broader external-content/restricted-content attack coverage, and
ARM64 replay/runtime evidence beyond the import smoke. R1 backup/restore is
retained as accepted carry-forward evidence. Native Pi 5 remains an external
gate only.

## R2 exact-head harness correction and hosted qualification - 2026-09-05

- PASS / exact governed head: `0283b648620e18ae4b771b9099673ec4d81eac88`;
  `main == origin/main`; hosted CI `33991073890` passed in 9m36s. Artifact
  `9976506229` was published.
- The SENTRY provider-crash target was corrected to use the real queue-level
  expired-provider reclaim pass while asserting against its own request ID.
  This keeps recovery semantics unchanged, makes the target deterministic on
  accumulated stores, and proves the child-process callback reached only after
  durable `PROVIDER_RUNNING`; recovery is `UNKNOWN_RESULT` with zero second
  provider callbacks. Unrelated pending SENTRY work, when present, is not
  counted as this scenario's reclaim.
- Local reruns also passed SENTRY outage/local-platform continuity, SENTRY
  bridge restart idempotency, Journal/Truth/Attention replay, and three-class
  PostgreSQL plugin isolation. The exact hosted run passed the configured
  validation workflow, including actual backup/restore, clean-store replay,
  ARM64 image/runtime smoke, process continuity, frontend/container checks,
  and safety scans.
- Phase 14 remains `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`; this packet
  remains active. The correction does not claim completion of the remaining
  full continuation/action crash matrix, broader action/manual-reality matrix,
  complete in-flight SENTRY/HA/plugin/process coverage, wider external-content
  coverage, or ARM64 replay/runtime beyond the hosted smoke. Phase 15 remains
  unauthorized and unimplemented.

## Out-of-process plugin qualification increment

- The pushed implementation head is `f713be88e844a8d4d663e32f7289b14a5190f0da`.
  It adds a test-only stdio MCP fixture and exercises the production
  `PluginManager` with `McpRuntime(RuntimeKind.MCP_STDIO)`, rather than an
  in-process callback substitute.
- Local result: `PASS`, scenario
  `PLUGIN_PROCESS_RESTART_AND_FAILURE_ISOLATION`, evidence level
  `POSTGRES_MCP_PROCESS`. The healthy child was invoked, disabled/re-enabled,
  and replaced with a distinct process identity. A failing child exited with
  a nonzero status; its plugin became `FAILED`, its tools were removed, a
  durable `plugin.failed` audit was written, and the independent healthy
  plugin remained `HEALTHY`.
- Hosted exact-head CI `33992570340` is in progress on this head. This is a
  bounded plugin-process result only; it does not close the remaining Phase 14
  approval, action ambiguity, event breadth, SENTRY/HA/process matrix,
  external-content, or ARM64 replay/runtime gates. Phase 15 remains
  unauthorized.

## Durable continuation exact-head qualification

- Published head: `d9de9a11abc21700a93abb5c0297bf1a382ed70a`, matching
  `origin/main`; exact-head CI `33994352076` passed. Artifact `9977709643`,
  digest
  `sha256:19ba41615602200f9a15db47248442094019b107e8d7a34b7246eec52c49d536`.
- Real PostgreSQL/process result: `PASS`,
  `CONTINUATION_POST_ACTION_DURABLE_NO_DUPLICATE_RESULT`, evidence level
  `POSTGRES_PROCESS_OPA`. The child crashed after the action store durably
  recorded `SUCCEEDED` and before continuation completion. A wrong principal
  could not resume the approved continuation; the correct recovery reused the
  terminal action. Total dispatches were exactly one and recovery dispatches
  were zero.
- This closes only the exercised post-action durable-result window. The full
  Phase 14 approval/continuation matrix, ambiguous action/HA, in-flight
  SENTRY/HA/plugin/process, external-content, and deeper ARM64 replay/runtime
  closure remain open. Phase 15 remains unauthorized.

## Exact-head hosted publication

- Published head: `75a8a9b94b89cbc53be577e935b1cfb2552eff5f`, matching
  `origin/main`.
- Hosted CI `33993069173`: `PASS` on that exact head. Artifact `9977351837`,
  digest
  `sha256:b287820e12898642f5e23b780d3c99c6fad596a579cd777eea85420c0cd021bf`.
- The run passed the configured Phase 14 real-store, backup/restore, OPA,
  isolated-HA, SENTRY, plugin, external-content, replay, restart, ARM64,
  frontend/container, H5, safety, and artifact-publication targets. The
  out-of-process plugin result is present as
  `PLUGIN_PROCESS_RESTART_AND_FAILURE_ISOLATION` at
  `POSTGRES_MCP_PROCESS`.
- The immediately preceding head `f713be8...` failed only in ARM64 runtime
  smoke because `grep -q` closed a pipeline while the replay process was
  still writing (`broken pipe`). The workflow was corrected to capture stdout
  before checking the marker; the corrected exact-head run passed ARM64 replay.
- This is a publication checkpoint, not Phase 14 acceptance. Approval/action
  ambiguity, event/action breadth, full in-flight process coverage,
  external-content breadth, and deeper ARM64 replay/runtime evidence remain
  open; native Pi 5 remains an explicit external gate. Phase 15 remains
  unauthorized.

## Isolated HA ambiguous-dispatch qualification - 2026-09-05

- PASS / exact governed head: `2a0bb87eb140883f7ccb824c1344767f07d47b38`;
  hosted CI `33995910836` passed. Artifact `9978159486`, digest
  `sha256:23ae7c69bcd17dc5abe5e9c3d4950fc3f3004c8eedcc1996c581d72e6dc7a619`.
- PASS / `ISOLATED_HA_POSTGRES_OPA`: the real isolated Home Assistant service
  call dispatched once and changed the device, while a test-only observation
  wrapper forced post-dispatch verification to remain stale. The authoritative
  Phase 9 result was `VERIFICATION_FAILED`; replaying the durable idempotency
  key returned that terminal result with one total gateway call and one total
  HA service call.
- The first hosted attempt is retained as harness evidence because it counted
  the baseline state-establishing `turn_off` call. The corrected harness resets
  counters after baseline setup. The local run lacked OPA and is not claimed as
  a pass.

Phase 14 remains `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`; this closes
only the real isolated-HA possible-dispatch/no-retry slice. Phase 15 remains
unauthorized and unimplemented.

## SENTRY process lifecycle matrix

- PASS / exact governed code head:
  `62533e8673a25ece7079595bd73bb3a650cb1d8c`; hosted CI `33998969482` passed
  on that exact head. Artifact `9979026256`, digest
  `sha256:7cab468a7a6915bad3a94fcd103104a4759583f3c368aa751a496bfe3b305225`.
- PASS / `POSTGRES_PROCESS`:
  `SENTRY_PROCESS_LIFECYCLE_MATRIX_NO_BLIND_REPLAY` ran four real child
  processes against the production PostgreSQL intelligence store. A child
  that exited before claim was safely claimable; post-claim loss was
  reclaimable; provider-started loss became `UNKNOWN_RESULT` with no claim;
  and a durable response completed without a new claim. Machine output
  captured child PIDs, `provider_replays=0`, and
  `embedded_agent_runtime_fallback=false`.
- This is a shared-runtime process-boundary result, not completion of the
  remaining approval/action, outage/restart, external-content, final replay,
  or deeper ARM64 Phase 14 families. Phase 15 remains unauthorized.

## HA manual-change race qualification - 2026-09-05

- PASS / exact governed head: `10830755f2f449b5c2a64b1f095f52a1fafb04d4`;
  hosted CI `33996868220` passed. Artifact `9978452041`, digest
  `sha256:1bc74e5ebf694e7107b6eec706aa31e912a400a1adb44fb9f605cc186de495b9`.
- PASS / `ISOLATED_HA_POSTGRES_OPA`: after one real ANIMA-governed HA
  dispatch, a test-only external actor changed the same isolated resource
  back to `off` and the harness waited for that state to be observable. The
  authoritative result was `VERIFICATION_FAILED`. Replay preserved that
  terminal status without another governed dispatch; machine output recorded
  one manual external change and one action-period service dispatch.

This closes only the exercised manual-reality race slice. Phase 14 remains
`CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`; Phase 15 remains unauthorized
and unimplemented.

## Policy reauthorization qualification - 2026-09-05

- PASS / exact governed code head: `cc8b0107ca9615750a580a41fc95dcbdc3722f74`;
  hosted CI `33998136623` passed; artifact `9978800620` was published.
- PASS / `POSTGRES_ACTION_POLICY`: `POLICY_CHANGE_BEFORE_APPROVAL_NO_DISPATCH`
  created a real PostgreSQL confirmation row under an initial
  `REQUIRE_CONFIRMATION` decision. Before the approved continuation was
  consumed, the test-only policy transition returned
  `POLICY_DENIED`; the coordinator performed two policy evaluations and the
  provider dispatch count remained zero. The approval outcome remained
  durably recorded. This does not modify the Phase 4 Rego bundle.

## Phase 14 clustered matrix

The current consolidated status is recorded in
`docs/PHASE-14-QUALIFICATION-MATRIX.md`. Provider lifecycle/fencing,
Journal/Truth/Attention/SenseGuard replay, plugin isolation, backup/restore,
and 250-record history traversal are verified within their exercised slices.
Approval/continuation, HA action reality, outage/process, external-content,
and deeper ARM64 families remain partial or open. The matrix is a planning and
evidence reconciliation record, not Phase 14 acceptance. Phase 15 remains
unauthorized and unimplemented.

## Consolidated evidence ledger checkpoint - 2026-09-05

- PASS / exact governed head: `d68f8205787d67b2f21ea9a7bba690b3e37f145c`;
  hosted CI `34000279143` passed. Artifact `9979391397`, digest
  `sha256:1a45b144e9cf001aad7beeef459d5517636769f7b619a68b309cce9880f5073e`.
- PASS / `PHASE14_EVIDENCE_LEDGER`: all 22 required real-store evidence files
  were present, valid JSON evidence was consolidated, and the mapped provider,
  approval, action, event/Truth/Attention, plugin, external-content,
  backup/replay, process, SENTRY, OPA, and history slices were observed.
- The ledger deliberately records `ledger_disposition=CONTINUE`. It is an
  integrity and coverage consolidation, not Phase 14 acceptance. The five
  `DETERMINISTIC_CONTRACT` scenarios are explicitly excluded from destructive
  evidence. Native Pi 5 remains an external gate; Phase 15 remains unauthorized.
