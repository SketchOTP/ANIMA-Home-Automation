# 027A evidence

Status: `IN_PROGRESS`

## Retrieval

- Repository/runtime/Notion retrieval confidence: `ADEQUATE`.
- ANIMA repository started clean at `97f0b672c20e556ced27f5c22b6499bb9d870ea7` with `main == origin/main`.
- SENTRY repository started clean at `ed8cbab98be1a34444d2514f38e94dc8b0244272` on its published feature branch.
- Accepted exact-head hosted CI was re-read from the Architect directive and Git history.
- The Notion permanent Goal and current 027A authority were retrieved before implementation.

## Deployed-build reconciliation

- Critical ANIMA Core source hashes in the healthy owner UI container match the accepted ANIMA checkout.
- Installed `anima-household` client/MCP source hashes match the accepted ANIMA checkout.
- `sentry-voice.service`, `anima-household-worker.service`, and the Android relay are active from the accepted clean SENTRY checkout/runtime files.
- The RPi projection services are active and their deployed projection/voice file hashes match the accepted SENTRY checkout.
- Active output instance is `office`; playback ownership for this qualification is therefore the Linux-PC SENTRY audio process.

## Pre-event baseline

- Front Door Lock has an active `UNLOCKED / ALWAYS / 00:00–23:59 / America/New_York` rule.
- Latest qualified Tapo lock journal position before the requested physical event: `12688`.
- Qualified Tapo lock event count: `42`.
- Trial ledger record count: `28`.
- Trial ledger mode: `0600`; current digest:
  `sha256:746c081973d1364c4205f3ffb991323f1839a1c29635ac68ed6caf4a6b8af296`.
- The ledger schema is content-free and records only timing/status metadata.

## Open evidence

- Fresh exact-build physical Tapo unlock: `OWNER-ACTION GATE` until observed.
- Event-to-playback latency and duplicate/provider-start counts: pending that event.
- Goal residual matrix and software closure: in progress.
- Three-day household trial: `ELAPSED-TIME GATE` until at least `2026-09-12T02:21:00Z`.

## Coherent software residual: personality configuration

- Added durable household-scoped free-form SENTRY personality profiles with
  create/edit/activate/delete owner controls and an explicit built-in fallback.
- The live UI retained the same authenticated browser session and active
  profile across a real UI-container restart. Temporary qualification records
  were deleted afterward.
- The installed credential-isolated SENTRY client read the server-owned active
  profile contract; SENTRY prompt regressions prove the text remains
  presentation-only and cannot replace ANIMA authority or mandatory factual
  alert behavior.
- Complete ANIMA and SENTRY regression suites passed locally. The published
  consolidated owner checkpoint is exact-head hosted green; see the R4
  publication section below.

## R3 continuous household learning

- Implementation and boundary: deterministic source-linked pattern candidates,
  exact review packets, provider-start-fenced structured SENTRY outcomes,
  versioned Memory correction/supersession, Obsidian hierarchy, incremental
  durable review tasks, owner inspection and later sparse-context retrieval.
- Live source inventory at final local qualification: 121 raw eligible event
  rows across four qualified device-event classes and four local dates; all
  source identities were unique. There were zero qualified presence
  transitions, so no arrival/departure or household-member attribution was
  inferred.
- Explicit live catch-up: six candidates, one
  `LEARNED_ROUTINE_SUGGESTION`, five `TENTATIVE_HYPOTHESIS`, zero declared
  routines/automations/permissions/identity assertions/actions. Request and
  packet are represented by sanitized SHA-256 digests only:
  `79ef1ce30af8d23f4dacf2052877f86a613cc410eb6a56b3e46a8faea788dd19`
  and `652364fcc97ae37704223aa1b044895e163838bd9e627d6626b7a4375c4e1b3d`.
- Continuous tasks: one daily 86,400-second review and one multi-day
  259,200-second review are active. Catch-up remains explicitly separate from
  scheduled due-run evidence.
- Later-use live trace: an ordinary UI-originated SENTRY request retrieved one
  relevant learned-routine suggestion and two tentative hypotheses alongside
  explicit owner context. The request is represented only by digest
  `98087e4961509f5d0ee09b2033f6d1a93e6c6aefc573901956a439d331b2aa6f`.
  Internal review packet/config/completion records were absent; SENTRY preserved
  uncertainty and did not infer actor, cause, policy or routine certainty.
- Obsidian: learning outcomes use managed `300.1`–`300.5` note types and
  digest-checked correction. Fourteen total managed notes were observed after
  catch-up and later decision logging; all observed note modes were `0660`.
- PASSED locally: full ANIMA validation `1169 passed / 76 skipped`, Ruff,
  strict mypy (147 source files), focused migrated-PostgreSQL learning tests,
  main Playwright `115 passed / 14 intentional smaller-viewport skips`, focused
  responsive browser `42 passed`, frontend `14 passed`, TypeScript/Vite, and
  complete qualified SENTRY `542 passed`.
- The aggregate `scripts/validate.sh` wrapper initially failed because `uv` was
  absent from the shell PATH; direct `.venv/bin/anima-validate` ran the same
  governed Python validation successfully. A first SENTRY run under the host
  interpreter failed because it lacked the qualified media/ML libraries; it was
  rerun successfully under `/home/sketch/.venvs/sentry-ubuntu/bin/python`.
- `.venv/bin/python -m build` was unavailable because the optional `build`
  module is not installed in that environment. The repository-pinned
  `.venv/bin/uv build --sdist --wheel` completed both artifacts successfully.
- Full architecture/evidence boundary: `docs/GOAL-027A-HOUSEHOLD-LEARNING-R3.md`.
- Implementation head `6ddee068dfa18e1623d9deacdb91cff0d0cbbdae`
  published successfully, but exact-head CI `34423847476` is retained as
  `FAILED`: every backend/policy/build/frontend gate passed before one tablet
  Playwright stream-quota test failed because `pauseAt(new Date())` raced the
  installed fake clock and attempted to move backward. The test now starts at
  a fixed epoch and pauses one second forward; the same scenario passes on
  desktop, tablet and phone. This is a test-only correction.
- Correction head `01433593f18247f181cc7a601a049e6bb10ec262` then
  passed the formerly failing main browser suite and every earlier hosted gate.
  Exact-head CI `34425286338` is nevertheless retained as `FAILED` because the
  later owner-product Memory suite still expected the superseded phrase
  “system-authored audit records.” The product now describes all managed
  decision/learning records as “system-authored, evidence-linked”; the test was
  aligned to that existing behavior. The complete owner-product browser
  verifier subsequently passed locally (`42 + 15 + 3 + 33` scenarios).
- Final implementation/correction head
  `9b84d3aaa8fbf853ecb9812080f4ea667a696e07` is exact-head hosted green:
  CI `34426846774` `PASSED`. Artifact `10133392831`, digest
  `sha256:adf82cd694063ed43ae01f8f3f2090cbece604572a28ba4783233012490788df`.
  The run includes the full ANIMA validation, OPA, real Core/PostgreSQL and
  accepted resilience qualifications, public-safety scan, ARM64 image/runtime,
  container health, main Playwright and the complete owner-product browser
  verifier. R3 is hosted-qualified at E4, with the live catch-up/later-use paths
  retaining E5 operational evidence.

## R4 residual closure — 2026-09-10

### Personality decision isolation

- `PASSED` locally: direct and autonomous operational prompts now discard the
  owner profile before prompt construction and use neutral built-in operational
  guidance. The obsolete profile-to-operational prompt helper was removed.
- `PASSED` locally: only a completed, harmless, tool-free, non-autonomous
  result is eligible for a separate ephemeral presentation pass. The renderer
  uses a bounded JSON schema and read-only/no-tool/ignore-user-config Codex
  execution. Its only mutable field is `answer`; it cannot change structured
  status, facts, tools, authorization, notification requirements or terminal
  outcomes. Renderer failure falls back to the neutral answer.
- `PASSED` locally: existing action/event regressions and new focused tests
  prove tool-bearing, autonomous, limited, failure and consequential paths do
  not enter the personality renderer. Mandatory first alert speech remains
  outside this path.
- `PASSED` locally: an active custom profile changes a harmless ordinary answer
  only through the second renderer call while the operational invocation input
  contains no profile text and structured result fields remain unchanged.

### Profile lifecycle correction

- `PASSED` locally: ANIMA PostgreSQL and owner API profile creation now always
  saves `active=false`; the first profile is not implicitly selected.
- `PASSED` locally: `Built-in SENTRY` is an explicit UI/API operation that
  deactivates custom profiles without deleting them. Version-checked activation
  remains atomic and household-scoped; the profile version is refreshed after
  built-in fallback before reactivation, preserving optimistic concurrency.

### Wake and identity evidence boundaries

- `PASSED` (`E1_OBSERVED`): the completed ten-minute metadata-only observation
  of the live office instance showed repeated `LISTENING`,
  `last_segment_outcome=non_wake`, empty Vosk class, no wake-chime request, no
  command dispatch and no Codex dispatch. This qualifies the unattended ambient
  interval only and contains no audio or transcript.
- `OWNER-ACTION GATE`: three exact spoken `Sentry` wakes plus the confusing
  negative phrase remain to be performed against the running instance. No live
  wake pass is fabricated.
- `OWNER-ACTION GATE` / nonblocking UX follow-up: the permanent goal requires a
  demonstrable voice software path, not final whole-home face hardware. Corrected
  eight-capture face enrollment is therefore not a permanent-goal acceptance
  gate; a fresh owner enrollment remains unobserved.

### Tooling and remaining gates

- `PASSED`: `DO_NOT_TRACK=1 npx --yes @nanonets/graft telemetry status` reports
  telemetry `off`. Repository-local Graft `AGENTS.md`, `.gitignore` and ignored
  `graft/` remain intentionally outside product commits.
- Full exact residual matrix: `docs/GOAL-027A-R4-RESIDUAL-CLOSURE.md`.
- Remaining gates are a fresh exact-build physical Tapo unlock latency sample,
  the three-day household trial no earlier than `2026-09-12T02:21:00Z`, and
  owner spoken wake/face follow-ups. Permanent-goal completion is not claimed.

### R4 published qualification

- `PASSED`: ANIMA head
  `20fb54f37ac2775e3c0498f2a206193462d99572` has exact-head CI `34431369009`
  `PASSED`. The run completed deterministic, PostgreSQL/OPA, Phase 13/14,
  ARM64, container, browser, safety and artifact gates.
- GitHub artifact `10134892070`, named
  `phase12-h5-evidence-20fb54f37ac2775e3c0498f2a206193462d99572`, was
  published. The GitHub artifact API exposes no native digest; the downloaded
  evidence-tree aggregate digest is
  `sha256:b4fc65f1cacbad7e0450a586976255e7e4c884cfa507965ec8a16199ea6cdba0`.
- `PASSED`: SENTRY head
  `8e459ad1c62b46ea3c51003f8df984fd14480004` has exact-head CI `34431379452`
  `PASSED` (deterministic and security-focused jobs).

## R5A deployment reconciliation and live qualification — 2026-09-10

- `PASSED` (`E4` deployment evidence): the stale ANIMA UI container was
  replaced from accepted ANIMA source `9658f2b0686b0e6e949df62b8810d71efdb812b3`.
  The rebuilt image digest is
  `sha256:2f81a673b91845f6b2ad5ce74e7be7c60b14920eec6ec5c4206b3f8b89da3122`;
  the deployed source-tree fingerprint is
  `5df385b0bdff83bbbec5b8008991c1daf7e5d4b69c9a3c6ebf36c9098cdd062d`.
  The running container is `anima-pc-ui-1` (ID prefix `ccd77a7ea040`) and
  `/healthz` is healthy. PostgreSQL and OPA were preserved in place.
- `PASSED` (`E5` operational observation): durable state remained present after
  redeployment, including 1 active personality profile, 21 Memory records, 15
  durable tasks, 5 calendar records, 63 Truth resources, and 3,873 Truth
  observations. No active approval/action or provider-running work was present
  at the final pre-redeploy check, and no duplicate dispatch was observed.
- `PASSED` (`E5` operational observation): the live R4 profile checks succeeded.
  A temporary profile saved inactive, Built-in SENTRY deactivated custom
  profiles without deleting them, the existing custom profile was restored, and
  the temporary record was removed.
- `PASSED` (`E4`): the live SENTRY wake correction is published at
  `5ac4bd56cdd367770a9fd36f8abe7956bc7bf5bf` with exact hosted CI
  `34466535061` `PASSED`. A post-fix wake-only observation recorded one
  corroborated positive with no model dispatch, and the confusing phrase
  `twentieth century` recorded no wake/chime/command/model activity. The
  earlier two wake attempts occurred before the correction and are not valid
  positive qualification evidence; three post-fix positives are therefore not
  claimed.
- `OWNER-ACTION / EXTERNAL-RESOURCE GATE`: no fresh Tapo
  `external.android.lock_reported` event was received after the live
  qualification arm. The latest qualifying journal record remains event
  `0466c014-cc86-5936-84d3-5cbbb06685dc` at journal position `13576` from
  `2026-09-09T19:14:40.562235Z`; the relay counters and content-free trial
  ledger did not advance for this attempt. The exact-build latency chain is
  consequently `NOT RUN`, with current-event/request/claim/provider-start/TTS
  counts `0/0/0/0`. No synthetic or app-generated event was substituted.
- The household trial remains active from `2026-09-09T02:21:00Z`; its earliest
  eligible review remains `2026-09-12T02:21:00Z`. This redeployment did not
  reset the trial clock.

## R5B exact wake correction and Tapo ingress diagnosis — 2026-09-10

- `PASSED` (`E3` actual-model qualification): the installed Vosk model was
  exercised in memory with separate restricted and full-vocabulary recognizers.
  The restricted grammar is now `sentry`, `century`, `[unk]`; only an exact
  restricted `sentry` token can authorize wake. Actual probes for `Sentry`,
  bare `century`, `century fox`, `century twenty one`, and `twentieth century`
  produced the expected restricted/full decoder classes. The evaluator produced
  one wake for `Sentry` and zero wakes for every `century`-led negative. No audio,
  transcript, or raw decoder text was written.
- `PASSED` (`E4` publication): SENTRY wake correction commit
  `feb9c567de2abd4913f14794aecf611d9ae3a354` was pushed to
  `feature/v0.4-personal-continuity`; exact hosted CI `34477770364` passed both
  security-focused and deterministic jobs. Local focused tests passed 83/83 and
  the full suite passed 548/548. Ruff was `NOT RUN` because the qualified SENTRY
  environment has no `ruff` module; compileall and diff checks passed.
- `OWNER-ACTION GATE`: a metadata-only live qualification window was armed for
  the three spoken `Sentry` positives and the bare/phrase/`twentieth century`
  negatives. It expired without owner speech (`wake_count=0`), so no live owner
  positive or negative is claimed. The prior single post-fix positive remains
  historical evidence only; it does not satisfy the three-positive gate.
- `PASSED` (`E5` operational boundary): after a controlled Waydroid
  container/session restart, Android received its expected static `eth0` policy
  routes and a hostname ping passed. The Tapo package remained installed
  (`com.tplink.iot`, `3.20.154`), not force-stopped, with Android 13 notification
  permission granted and enabled notification channels. The app was launched to
  its main activity; no credentials or vendor payloads were recorded.
- `EXTERNAL/VENDOR NOTIFICATION GATE` / `OWNER-ACTION GATE`: the owner’s latest
  physical lock/unlock attempt still produced no new Tapo notification. The
  relay remained healthy (`DELIVERED`, received 76, accepted 72, rejected 4,
  failed 0); the latest qualifying journal event remains
  `0466c014-cc86-5936-84d3-5cbbb06685dc` at position `13576`. Therefore the
  exact-build physical latency chain is `NOT RUN`; no event/request/claim,
  provider-start, TTS or playback timestamp is counted.
- Network diagnosis: the failure was initially a missing Android policy route,
  not an ANIMA Journal/relay rejection. A transient route repair restored the
  gateway, DNS and external reachability; a clean restart restored the expected
  static routes after boot settled. Android notification-listener permission is
  not claimed for ANIMA because the qualified path is Waydroid’s private D-Bus
  notification bridge. Tapo internal door-event delivery remains unverified until
  a fresh vendor notification arrives.
- The household trial remains active from `2026-09-09T02:21:00Z`; earliest
  eligible review remains `2026-09-12T02:21:00Z`. Phase 15 remains unauthorized.
- `NOT RUN`: Notion update/readback, because no Notion connector was available
  in this session. This is reported explicitly rather than inferred.

## R5D alert-route compatibility and deployment — 2026-09-10

### Retrieval and publication

- Retrieval confidence: `ADEQUATE` for the local ANIMA checkout, deployment,
  route implementation and persisted owner configuration. The ambient SSHFS
  mirror is an older dirty checkout and was not modified.
- ANIMA source and `origin/main`: `20917337580520221a362a5b18b89d65cb2b5093`.
- Exact-head hosted CI: `34530665233` — `PASSED`.
- SENTRY source was not changed; accepted branch remains
  `dcc37bac24adf4ae110ea1e13aa7c97e1de3fa63` with prior accepted exact CI
  `34524787155`.
- Repository-local Graft changes remain outside product staging. No global
  Graft configuration was changed.

### Route contract evidence

The server-side `compatible_sentry_path()` normalizer is used by Core
notification disposition and by device-rule persistence/legacy payload
loading. The effective matrix is:

| Alert obligation | Allowed effective route |
| --- | --- |
| `ALWAYS` | `IMMEDIATE_ANNOUNCEMENT_ONLY` or `ANNOUNCEMENT_AND_CONTEXTUAL_REASONING` |
| active `TIME_WINDOW` | `IMMEDIATE_ANNOUNCEMENT_ONLY` or `ANNOUNCEMENT_AND_CONTEXTUAL_REASONING` |
| `CONTEXTUAL` | `ANNOUNCEMENT_AND_CONTEXTUAL_REASONING` |
| `NEVER` | `NO_SENTRY_REASONING` |
| Attention aggregate | `AGGREGATED_REASONING`, Attention-owned |

Required alerts cannot become `NO_ACTION` through an invalid route. `NEVER`
cannot reactivate speech/reasoning through stale route metadata. A malformed
required route fails safe to immediate announcement; malformed optional route
uses the configured safe default. Device-level aggregate override remains
rejected for new configuration and legacy aggregate payloads are normalized
to the safe route for their alert mode. The UI route selector is derived from
the selected alert obligation and does not offer incompatible choices.

Focused route matrix, legacy normalization, attention and household-learning
tests passed. The full ANIMA suite, Ruff, strict mypy, formatting, Python
compilation, UI tests, TypeScript check, Vite build and `git diff --check`
passed. No active invalid persisted combinations were found: the live store
has one active configuration and six valid rules (four `ALWAYS`, two
`TIME_WINDOW`, all on the default compatible route).

### Deployment correspondence and preservation

- Built from the accepted source without a source commit beyond the route
  correction and recreated only the ANIMA UI container.
- Running container: `anima-pc-ui-1`, ID prefix
  `9bb6813ebfb0020f894cb92956f8d94cf389f58249e108b79511a9be6b61fb80`.
- Image: `sha256:7cca65dbcc2bc6bf09ed564bea6b00899fef5a08cb5fe955343644dc1d1e91d9`.
- `/healthz`: `PASSED`; container health: `healthy`.
- Changed source hashes for `attention.py`, `household_initiative.py`,
  `household_learning.py` and `ui_api.py` match host checkout copies.
- PostgreSQL, OPA, Searxng and Home Assistant were not recreated. The active
  personality profile, household state, learning state and provider recovery
  records remain present. Pre-redeployment state had no in-flight claims or
  provider-running requests; 43 historical ambiguous results were preserved.

### R5C readiness carried forward

The settled metadata-only readiness document reported `READY`: Android
container/session/boot, network/DNS/clock, FCM marker, private notification
bridge, relay heartbeat and both vendor packages were observed. This is
readiness evidence only; vendor account and in-app setting state remain
`NOT_EXPOSED`, and no genuine post-deployment vendor event was inferred.

### R5D remaining evidence gates

- `NOT RUN / OWNER-OPERATIONAL GATE`: full Linux host reboot. It was not
  performed during this deployment checkpoint because the active development
  host and owner sessions were not silently interrupted.
- `NOT RUN / OWNER + VENDOR GATE`: fresh physical Tapo DL110 vendor receipt;
  exact-build event-to-playback latency therefore has no qualifying event.
- `NOT RUN / OWNER + VENDOR GATE`: fresh physical Wansview motion receipt.
- `OWNER-ACTION GATE`: three post-correction spoken `Sentry` positives plus
  bare `century`, a century-led phrase and `twentieth century` negatives.
- `NOT RUN`: exact-build Tapo playback-owned `tts_start_at` measurement; no
  source event, request, provider-start or speech count is substituted.
- `NOT RUN`: Notion update/readback; no Notion connector was available in this
  session. This is not inferred as success.
- Household trial continuity is preserved from `2026-09-09T02:21:00Z`; the
  earliest eligible review remains `2026-09-12T02:21:00Z`.

## R5C persistent Android notification appliance — 2026-09-10

### Architecture and readiness

- The owner-local Android notification substrate is now supervised as a
  persistent subsystem:
  `Linux boot → enabled waydroid-container → Android user session → network /
  DNS / clock → Google Play Services/FCM marker → Tapo/Wansview packages →
  private notification bridge → relay → ANIMA ingress`.
- `waydroid-container.service` is enabled and active through the existing
  `sudo -n` installation path. `loginctl show-user sketch` reports
  `State=active`, `Linger=yes`, and two sessions. The owner user units
  `anima-android-bus`, `anima-android-compositor`,
  `anima-android-session`, `anima-vendor-notification-relay` and
  `anima-android-notification-supervisor` are enabled and active.
- The supervisor writes `/run/user/1000/anima-android-notification-readiness.json`
  with owner-only mode `0600`. It contains only bounded states, reasons,
  timestamps, package booleans and relay counters; no notification text,
  credentials, FCM tokens or household payload.
- Current settled readiness at `2026-09-10T14:08:46.927532Z` was `READY`:
  Android boot/session/container, network, DNS, clock, FCM marker, private
  notification bridge, relay heartbeat and both vendor package states were
  ready. Both packages were installed, notification permission/channels were
  present, and process presence was observed. Account and vendor in-app setting
  state remains explicitly `NOT_EXPOSED`.

### Live restart qualifications

- `ANDROID_SESSION_RESTART`: `PASSED` (`E5_OBSERVED`). The user session was
  stopped without a manual start; it returned active and the final readiness
  document returned `READY` with FCM, relay, listener and both vendors ready.
- `WAYDROID_CONTAINER_RESTART`: `PASSED` (`E5_OBSERVED`). The container was
  restarted; the Android session and dependent readiness chain returned to
  `READY` without manual session or vendor-app launch.
- `RELAY_PROCESS_RESTART`: `PASSED` (`E5_OBSERVED`). Stopping the relay also
  stopped its declared Android-session dependency; the enabled supervisor
  restored the chain and readiness returned to `READY`.
- `TAPO_PROCESS_RECOVERY`: `PASSED` (`E5_OBSERVED`). A live Tapo process was
  terminated by package-qualified PID selection. The supervisor first wrote
  `DEGRADED / NOT_READY / PROCESS_NOT_OBSERVED` at
  `2026-09-10T14:07:53.655623Z`, then independently relaunched the app and
  reached `READY` at `2026-09-10T14:08:10.927362Z`.
- `WANSVIEW_PROCESS_RECOVERY`: `PASSED` (`E5_OBSERVED`). The live Wansview
  heartbeat process was terminated by package-qualified PID selection. The
  supervisor first wrote `DEGRADED / NOT_READY / PROCESS_NOT_OBSERVED` at
  `2026-09-10T14:08:28.614094Z`, then independently recovered the app and
  reached `READY` at `2026-09-10T14:08:46.927532Z`.
- The supervisor's readiness fix makes missing process presence part of vendor
  readiness, so a pre-relaunch snapshot cannot claim `READY`. Startup-failure
  relaunches remain cooldown-bounded; an observed healthy-to-dead transition
  bypasses that cooldown for prompt recovery.

### Validation and remaining gates

- `PASSED`: focused supervisor/relay tests (`9 passed`), changed-file Ruff,
  strict mypy, Python compilation, complete `.venv/bin/anima-validate`
  (`1171 passed, 76 skipped`), pinned OPA `9/9`, and `git diff --check`.
- `NOT RUN`: the checked-in `scripts/validate.sh` wrapper because `uv` is not
  on this host PATH. Its underlying venv validation and pinned OPA checks pass.
  Frontend/build checks were not rerun because R5C changed only host runtime
  scripts/tests; prior accepted frontend evidence remains historical.
- `NOT RUN / OWNER-OPERATIONAL GATE`: a full Linux-host reboot. It was not
  performed silently; no app/session restart is being mislabeled as a host
  reboot. Native Pi5 qualification is outside this host's R5C run.
- `NOT RUN / EXTERNAL-VENDOR AND OWNER GATE`: no fresh genuine Tapo vendor
  notification and no genuine Wansview motion notification were received.
  Tapo app/account/in-app setting checks are not exposed through the bounded
  host diagnostics, and no receipt is inferred from package readiness.
- `OWNER-ACTION GATE`: three post-correction spoken `Sentry` positives plus
  bare `century`, a century-led phrase and `twentieth century` negatives remain
  unperformed. No ambient transcript or audio was stored.
- `NOT RUN`: exact-build Tapo event-to-playback latency; there is no fresh
  source event, Journal entry, request, provider-start or playback-owned
  `tts_start_at` to measure. The existing three-day trial remains active from
  `2026-09-09T02:21:00Z` and cannot be reviewed before
  `2026-09-12T02:21:00Z`.
- `NOT RUN`: Notion update/readback, because no Notion connector was available
  in this session. This is reported explicitly rather than inferred.
