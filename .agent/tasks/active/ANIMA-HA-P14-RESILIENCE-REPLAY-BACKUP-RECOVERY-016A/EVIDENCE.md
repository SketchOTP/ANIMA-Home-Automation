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
