# Phase 14 R2 scenario coverage audit

This audit maps the explicit R2 acceptance scenarios to the final bounded
closure evidence at `6a61e38276a086535fa933b38d5b69cabdb0a167`, hosted CI
`34012962667`, artifact `9983142603`, digest
`sha256:d6cb85b3234f1cb70ac2132bff6dcdc5baf8af05fa14e74d9621ed8e8348970e`.
It is a retained evidence reconciliation record for the accepted Phase 14 gate.
`VERIFIED` includes a grouped evidence mapping only when the cited output
contains the required observable invariant. `UNKNOWN` means the current
artifact does not prove the required scenario at the requested boundary; it
must not be inferred from a related unit or contract fixture. Phase 15 remains
unauthorized.

## Explicit scenario ledger

| Required scenario | Status | Evidence and boundary |
| --- | --- | --- |
| `APPROVAL_CONCURRENT_ONE_WINNER` | `VERIFIED` | `phase14-approval-race.json`; real PostgreSQL race, one winner and durable approval. |
| `CONTINUATION_POST_ACTION_RESTART_NO_DUPLICATE_RESULT` | `VERIFIED` | `phase14-approval-durable-r3.json`; equivalent published scenario `CONTINUATION_POST_ACTION_DURABLE_NO_DUPLICATE_RESULT`, action result durable before process loss, one dispatch, zero recovery redispatches. |
| `CONTINUATION_PRINCIPAL_REVALIDATION` | `VERIFIED` | Same durable continuation evidence records `wrong_principal_rejected=true`; continuation authority is rechecked before reuse. |
| `REJECTION_NOT_POLICY_DENIAL` | `VERIFIED` | `phase14-final-closure-bundle-r2.json`; real PostgreSQL approval rejection projects the bounded user result `REJECTED`, preserves `POLICY_DENIED` as the action status, and records zero provider dispatch. |
| `STRONG_AUTH_NOT_CONFIRMATION` | `VERIFIED` | `phase14-closure-bundle-r2.json`; real OPA returns `REQUIRE_STRONGER_AUTH` for a security-access intent and creates no ordinary confirmation row or dispatch. |
| `STALE_FENCE_CONTINUATION_REJECTED` | `VERIFIED` | `phase14-continuation-r2.json`; stale result/transition rejected and continuation enters recovery-required without dispatch. |
| `RESOURCE_OPPOSING_ACTIONS` | `VERIFIED` | Exact Phase 9 isolated-HA output records opposing requests, PostgreSQL resource locking and conflict resolution before connector dispatch. |
| `USER_VS_AUTONOMOUS_RACE` | `VERIFIED` | Same Phase 9 output records distinct principals issuing opposite requests and deterministic lock/conflict handling. |
| `MANUAL_CHANGE_BEFORE_AUTHORIZATION` | `VERIFIED` | `phase14-closure-bundle-r2.json`; fresh required off/version 1 changes to on/version 2 before continuation and the real action store returns `PRECONDITION_FAILED` with zero dispatches. |
| `MANUAL_CHANGE_BEFORE_VERIFICATION` | `VERIFIED` | `phase14-ha-ambiguous-r3.json`; one isolated-HA dispatch followed by observable external change yields `VERIFICATION_FAILED` with no replay dispatch. |
| `POSSIBLE_DISPATCH_NO_RETRY` | `VERIFIED` | `phase14-action-recovery-r2.json` and `phase14-ha-ambiguous-r3.json`; possible dispatch remains unknown/failed and replay does not redispatch. |
| `HA_DUPLICATE_EVENT_DEDUP` | `VERIFIED` | `phase14-events-plugins-r2.json`; duplicate HA event has one effective journal row. |
| `HA_OUT_OF_ORDER_TRUTH` | `VERIFIED` | Same output; newer source sequence wins and stale observation cannot overwrite Truth. |
| `ATTENTION_DUPLICATE_DEDUP` | `VERIFIED` | Same output; one guaranteed Attention trigger is effective. |
| `SENSEGUARD_DUPLICATE_DEDUP` | `VERIFIED` | Same output; duplicate SenseGuard source event produces one logical event. |
| `JOURNAL_APPEND_RESTART_REPLAY` | `VERIFIED` | Same output; projection restart/rebuild restores the effective Truth projection. |
| `HA_OUTAGE_NO_REDISPATCH` | `VERIFIED` | `phase14-ha-outage-r2.json`; disconnect/recovery is explicit and prior action is not redispatched. |
| `SENTRY_PRECLAIM_RESTART` | `VERIFIED` | `phase14-sentry-process-matrix-r3.json`; pre-claim work is claimable after child-process loss. |
| `SENTRY_PRESTART_RECLAIM` | `VERIFIED` | Same matrix; post-claim/pre-provider-start work is reclaimed. |
| `SENTRY_RUNNING_NO_REPLAY` | `VERIFIED` | Same matrix; provider-started work becomes `UNKNOWN_RESULT` and provider replays remain zero. |
| `SENTRY_RESULT_DURABLE_NO_RERUN` | `VERIFIED` | Same matrix; durable result completes without a new claim or provider replay. |
| `SENTRY_OUTAGE_PLATFORM_CONTINUES` | `VERIFIED` | `phase14-sentry-outage-r2.json`; local ANIMA capabilities continue while SENTRY is unavailable. |
| `NO_EMBEDDED_FALLBACK` | `VERIFIED` | SENTRY process/in-flight evidence records `embedded_agent_runtime_fallback=false`. |
| `HA_PLUGIN_FAILURE_ISOLATION` | `VERIFIED` | `PLUGIN_FAILURE_ISOLATION_THREE_CLASSES` covers HA failure and unrelated-plugin health. |
| `EXTERNAL_READ_PLUGIN_FAILURE_ISOLATION` | `VERIFIED` | Same three-class plugin scenario covers external-read failure and unrelated-plugin health. |
| `SIDE_EFFECT_PLUGIN_FAILURE_ISOLATION` | `VERIFIED` | Same three-class plugin scenario covers notification/side-effect failure and unrelated-plugin health. |
| `PROMPT_INJECTION_NO_AUTHORITY` | `VERIFIED` | `phase14-external-r2.json`; hostile external text remains untrusted and cannot grant authority. |
| `FAKE_PERMISSION_NO_AUTHORITY` | `VERIFIED` | `phase14-external-attack-r2.json`; fake permission text does not alter policy or authority. |
| `RESTRICTED_CONTENT_ZERO_DURABLE` | `VERIFIED` | External attack and Phase 11 restricted-content evidence show zero prohibited durable sentinel content. |
| `TASK_CALENDAR_250_RECORD_PAGINATION` | `VERIFIED` | `phase14-r2-real-store.json`; 250 tasks and 250 calendar records traverse stable cursors with unique IDs. |
| `TASK_DUE_CANCEL_RACE` | `VERIFIED` | `phase14-closure-bundle-r2.json`; real PostgreSQL concurrent due-claim/cancel produces at most one run and zero dispatches. |
| `CALENDAR_CONCURRENT_VERSION_WINNER` | `VERIFIED` | `phase14-r2-real-store.json`; one optimistic-version winner and stale writer rejection. |
| `REAL_STORE_REPLAY_MATCH` | `VERIFIED` | `phase14-clean-replay-r2.json`; two fresh PostgreSQL runs match behavior and durable fingerprints. |
| `REAL_STORE_REPLAY_DIFF_DETECTED` | `VERIFIED` | Same output; intentional expected divergence produces a machine-readable difference. |
| `CORE_RESTART_INFLIGHT` | `VERIFIED` | `phase14-final-closure-bundle-r2.json`; the real UI/Core process restarted during a pending approval, the original approval remained durable, and the resumed action dispatched once and reached `SUCCEEDED`. |
| `OPA_RESTART_INFLIGHT` | `VERIFIED` | `phase14-final-closure-bundle-r2.json`; the real OPA process restarted during governed action execution, recovered, and the action reached `SUCCEEDED` through the current policy path with one dispatch. |
| `HA_RESTART_INFLIGHT` | `VERIFIED` | `phase14-final-closure-bundle-r2.json`; isolated Home Assistant restarted after dispatch and before verification, the adapter reconnected, terminal verification remained authoritative, and replay dispatched zero additional times. |
| `POSTGRES_RESTART_INFLIGHT` | `VERIFIED` | `phase14-inflight-restart-r2.json`; real container restart spans pending, claimed, provider-running, result-received and due-task states. |
| `PLUGIN_RESTART_INFLIGHT` | `VERIFIED` | `phase14-plugin-process-r2.json`; real child-process replacement and failure isolation are observed. |
| `ARM64_BUILD_RUNTIME` | `VERIFIED` | Exact CI runs the pinned `linux/arm64` image build, import smoke and deterministic replay contract; native Pi 5 remains external. |

## Final bounded closure bundle

The final bounded closure bundle at `6a61e382...` adds four real-store/process
scenarios: rejection-vs-policy-denial projection, in-flight Core restart,
in-flight OPA restart, and in-flight isolated-HA restart. All four passed in
hosted CI `34012962667`; the bundle tested the exact implementation SHA and
reported `provider_dispatches=0` for rejection and one dispatch for each
governed restart action. The HA restart terminal state was
`VERIFICATION_FAILED`, and replay returned the same durable result without a
second dispatch.

The explicit audit is now 40 `VERIFIED` and 0 `UNKNOWN` for the mapped R2
scenarios. The prior provisional/negative records remain historical evidence;
they are not deleted or rewritten.

The implementation head was ready for the Architect Gate and was accepted at
the governed checkpoint recorded above. Deterministic contract fixtures remain
excluded from destructive proof, native Pi 5 remains an external hardware gate,
and Phase 15 remains unauthorized.
