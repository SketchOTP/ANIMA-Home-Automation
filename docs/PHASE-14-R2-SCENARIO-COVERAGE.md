# Phase 14 R2 scenario coverage audit

This audit maps the explicit R2 acceptance scenarios to the latest published
real-store evidence at `c7cd9b0ee7f7b62e0aed427f89697b0337eecd8f`, hosted CI
`34006015292`, artifact `9981079823`, digest
`sha256:f015301d6a796594ec777602170b8f6a554150c76ff826ef29e9f14f06aaaf5d`.
It is an evidence reconciliation record, not a Phase 14 acceptance claim.
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
| `REJECTION_NOT_POLICY_DENIAL` | `UNKNOWN` | The durable approval row is `REJECTED`, but the action projection is `POLICY_DENIED`; a distinct end-to-end user-facing rejection result is not separately proven. |
| `STRONG_AUTH_NOT_CONFIRMATION` | `UNKNOWN` | Strong-auth behavior exists in retained Phase 6/12 evidence, but this R2 real-store artifact has no explicit destructive scenario proving it cannot be downgraded to ordinary confirmation. |
| `STALE_FENCE_CONTINUATION_REJECTED` | `VERIFIED` | `phase14-continuation-r2.json`; stale result/transition rejected and continuation enters recovery-required without dispatch. |
| `RESOURCE_OPPOSING_ACTIONS` | `VERIFIED` | Exact Phase 9 isolated-HA output records opposing requests, PostgreSQL resource locking and conflict resolution before connector dispatch. |
| `USER_VS_AUTONOMOUS_RACE` | `VERIFIED` | Same Phase 9 output records distinct principals issuing opposite requests and deterministic lock/conflict handling. |
| `MANUAL_CHANGE_BEFORE_AUTHORIZATION` | `UNKNOWN` | Policy change before approval is proven, but a separate manual physical-state change before authorization is not identified in the artifact. |
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
| `TASK_DUE_CANCEL_RACE` | `UNKNOWN` | Due-task restart evidence exists, but a real concurrent cancel-versus-due-claim race is not separately identified. |
| `CALENDAR_CONCURRENT_VERSION_WINNER` | `VERIFIED` | `phase14-r2-real-store.json`; one optimistic-version winner and stale writer rejection. |
| `REAL_STORE_REPLAY_MATCH` | `VERIFIED` | `phase14-clean-replay-r2.json`; two fresh PostgreSQL runs match behavior and durable fingerprints. |
| `REAL_STORE_REPLAY_DIFF_DETECTED` | `VERIFIED` | Same output; intentional expected divergence produces a machine-readable difference. |
| `CORE_RESTART_INFLIGHT` | `UNKNOWN` | Current process matrix proves service continuity, but not an in-flight Core/UI restart at each required lifecycle boundary. |
| `OPA_RESTART_INFLIGHT` | `UNKNOWN` | OPA continuity and fail-closed outage are proven, but an in-flight OPA restart scenario is not separately identified. |
| `HA_RESTART_INFLIGHT` | `UNKNOWN` | HA outage/reconnect and isolated action evidence exist, but an in-flight HA process restart is not separately identified. |
| `POSTGRES_RESTART_INFLIGHT` | `VERIFIED` | `phase14-inflight-restart-r2.json`; real container restart spans pending, claimed, provider-running, result-received and due-task states. |
| `PLUGIN_RESTART_INFLIGHT` | `VERIFIED` | `phase14-plugin-process-r2.json`; real child-process replacement and failure isolation are observed. |
| `ARM64_BUILD_RUNTIME` | `VERIFIED` | Exact CI runs the pinned `linux/arm64` image build, import smoke and deterministic replay contract; native Pi 5 remains external. |

## Residual closure bundle

The current explicit audit therefore has 33 `VERIFIED` scenarios and 7
`UNKNOWN` scenarios. The next implementation batch should be one real-store
closure bundle for those seven items, reusing the existing PostgreSQL, OPA,
isolated-HA, task, approval, and process seams. It must emit these exact
scenario IDs, tested SHA, evidence level, durable identifiers/digests, process
identity where applicable, dispatch count, and terminal status. No grouped
scenario may be relabeled as an exact scenario without those fields.

Until that bundle passes at the final governed head, Phase 14 remains
`CONTINUE`; the deterministic contract fixtures remain excluded from this
audit, and Phase 15 remains unauthorized.
