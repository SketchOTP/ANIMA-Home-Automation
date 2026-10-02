# CODEX RESULT — 027A/R5F Stage9

## Verdict

NEEDS_ARCHITECT_DECISION — current-caller investigation, 2026-10-02T19:48Z.
Implementation and qualification are NOT COMPLETE. This is not a frozen product
bundle or source acceptance. Same sole Coder; no descendants.

## Retrieval confidence

ADEQUATE for the observed launch, pending-approval, host broker, and current
Core audio/enrollment interfaces. UNCERTAIN for the authority disposition of
later broad Office access to an existing shared resident thread and the absent
Core route for the six existing audio controls. Do not invent those dispositions.

## Technical state discovered

Exact clean detached source:

- ANIMA `/tmp/anima-stage9-development.uaXhQt`,
  `8396c7eb261c6c0ee51c96d24b4012966d216768`.
- SENTRY `/tmp/sentry-stage9-development.UFN3qc`,
  `6eafe70dcf0674ca66a8df866105965705dff841`.

Parent canonical `.git/anima-ha-execution-state.json` read-only validation:
OWNED, session `01a052d8-2511-7382-a1ef-b0a080514788`, generation4/fence4,
last-confirmed activity19:40Z. Lock directory present; neither acquired nor
released. Git status in both assigned product roots is empty. Parent publication,
CI and runtime outcomes are distinct from this source investigation.

Current SENTRY source confirms:

1. `tools/sentry_anima.py:134–141` conflates missing configuration and any
   `enabled != True` as `None`. Thus lack of binding does not prove explicit
   standalone intent. `ResidentAnimaTurn.prepare` opens/starts a direct request
   and fails closed for the household capability, but the caller currently
   retains an independent Office fallback.
2. `tools/sentry_codex_agent.py:974–987` queries/resolves Office pending work
   before the voice-origin/direct household preparation. The autonomous branch
   applies `autonomous_turn_overrides`; a direct bound turn does not receive
   equivalent native/MCP restriction. These confirm the accepted audit findings,
   not a newly reproduced owner effect.
3. `CodexNativeAgent` uses one `CodexSessionStore` for ordinary requests and
   resident events. `ask` resumes its existing thread; `run_resident_event` uses
   the same agent/session lock and saves its pointer. Existing session metadata
   has no trusted household-exposure/standalone-history eligibility field.
   Restricting a later launch cannot erase private context retained in that
   thread. No transcript or private session was read to infer actual exposure.
4. The six audio tools at `tools/sentry_mcp_server.py:271–310` call host volume
   or projection executors. Reads bypass the Office Tier1 mutation broker;
   mutations use local current-request matching/audit, not Core identity/OPA.
   Enrollment at208–241 similarly calls the local enrollment manager after a
   recognized-operator observation at start; that is not equivalent to current
   Core request/principal authorization.
5. `tools/sentry_execution_authority.py` has no trusted scope in
   `RequestContext`. Its path guard lacks the engineering/service/.codex/bare.env
   distinctions identified by the accepted audit, and desktop execution checks
   exact window ID, not terminal/editor/browser privilege. These are E1 findings;
   no executor was invoked.

Current ANIMA source preservation interfaces:

- `src/anima_ha/sentry_voice_settings.py:43–66` validates exactly voice ID,
  speech speed, sleep flag and active SENTRY instance. It does NOT implement
  system volume/mute or USB/HDMI routing. `SentryControlNativePlugin` exposes
  only `enter_sleep_mode` in the current typed catalogue.
- `src/anima_ha/ui_runtime.py:757–837` has the existing current-household
  enrollment bridge: active household membership, invocation of
  `anima.household-users.authorize_face_profile` under current policy, then
  fixed SENTRY identity client operations. `src/anima_ha/users.py:214–236`
  declares `identity.configure` / SECURITY_SECURE_ACTION. Reuse this authority;
  do not substitute the local Office observation for it.
- `src/anima_ha/sentry_identity_profiles.py` implements fixed loopback routes
  with a host-owned credential; it is transport, not model or operator authority.
- `src/anima_ha/sentry_service.py:1060–1092` voice settings reads authenticate
  the service principal but supply no equivalent six-control mutation route.
  No private token/configuration was read.

## Work performed

Read full issued Stage9 assignment, prepared packet, applicable Authority
instructions/kernel and relevant Stage8 acceptance/history, owner takeover
section9, and cited permission/sandbox evidence. Inspected exact current callers
and reusable Core interfaces. Cached Graft absent: exact-source fallback only,
no refresh/build/npx. No application imports, model/camera/audio/network/owner
fixture invocation. Investigation distinguishes actual omissions from inherited
audit claims and production outcomes.

## Files / areas changed

Product: NONE. Only this authorized canonical Stage9 Coder result created.
All old product roots/results/manifests and private runtime configuration remain
untouched. No source manifest claimed for a nonexistent implementation bundle.

## Validation

- Assigned HEAD and clean-worktree checks: PASSED (read-only).
- Parent execution ownership/session/generation/fence check: PASSED (read-only).
- Exact current source/caller and Core preservation-interface inspection: PASSED,
  E1 only.
- New focused tests, PostgreSQL/current OPA, installed inert sandbox, frontend,
  full regressions and final custody: NOT RUN; no product implementation exists.
- Prior accepted sidecar E2/sandbox evidence: READ, not rerun or upgraded here.

Diagnostic negatives retained in the native tool history: exploratory searches
used obsolete `household_users.py`, `ui_read_model.py`, `safety.py`, `policies/`,
and `sentry_anima_resident_events.py`; actual paths were resolved with `rg`.
The state file is the sibling `.git/anima-ha-execution-state.json`, not
`anima-ha-execution.lock/state`. Initial result existence check used product cwd;
the subsequent exact canonical check confirmed no preexisting Stage9 result.
None of these search errors is a test failure or absence proof. No diagnostics
were rewritten/deleted and no full-suite pass is implied.

## Evidence level

E1_OBSERVED — current exact-source inspection. No new E2/E3/E4/E5 claim.

## Acceptance results

- Investigation of current authority/caller surfaces: PASSED, E1.
- Complete useful household/standalone isolation with preserved audio/enrollment:
  BLOCKED on the material dispositions below; NOT implemented/tested.
- All remaining Stage9 product/qualification criteria: NOT RUN.

## External discovery

NONE. No new external solution, dependency or framework proposed. Read existing
installed inert-sandbox evidence; did not invoke Codex or inspect its private
configuration/authentication.

## Assumptions confirmed

- Direct household launch and host tools require separate guards.
- Explicit standalone Office is legitimate and must not be deleted globally.
- Host wake/STT/TTS/projection transport does not need broad model Office powers.
- Existing UI enrollment has a Core policy boundary worth preserving/reusing.

## Assumptions disproven

- Current typed voice settings alone cannot preserve the six host audio controls.
- A per-turn permission overlay alone cannot qualify retained shared-thread
  history for a later broad standalone turn.

## New durable learnings

Permission narrowing, host-executor authorization, and persistent-history
eligibility are distinct contracts. A fixed local transport or recognized camera
observation is not a current Core authorization receipt.

## Risks / blockers

Two explicit dispositions are needed before claiming the complete bundle:

1. **Shared-thread history / explicit standalone.** Recommend preserving the
   exact thread and failing closed for broad Office whenever household exposure
   is established or legacy exposure is unknown; keep it useful for restricted
   household operation. This conservatively restricts previously available
   Office use of that shared history and therefore needs Architect disposition.
   Restoring broad standalone on the same possibly private history cannot be
   justified by `enabled:false` or a caller label alone. If broad standalone must
   remain available immediately on that history, the Architect must supply its
   approved history-eligibility boundary; an unauthorized reset/new thread or
   guessed sanitization is not an acceptable alternative.

2. **Six audio controls and voice enrollment.** Recommend an exact request-bound
   Core route using existing identity/access, frozen catalogue, current OPA and
   fixed host transports, with direct-only admission and zero host execution on
   missing/denied/revoked authority. Enrollment should reuse the current UI bridge
   policy rather than raw Office methods. Confirm that this bounded extension of
   current Core control/enrollment interfaces is the intended preservation path
   (including current policy risk/assurance semantics), since the six audio
   operations are absent there today. Do NOT preserve them by retaining the full
   Office server or silently adding a local-broker exception. If no extension is
   approved, their household voice invocation must remain explicitly unavailable;
   that is a contract shortfall, not completion.

Safe scope/permission/broker corrections remain within this Stage9 assignment,
but this handoff requests disposition before committing to a preservation design
that would silently choose one of the material authority alternatives. No second
packet, phase, agent or framework requested. Existing eight synthetic audit
originals/classification are untouched; no project/provider zero-usage inference.

## Deviations from directive

NONE — assignment explicitly requires escalation for material standalone-history
or audio/enrollment authority choices. No speculative neighboring implementation.

## Project records updated

- `.agent`: only authorized `STAGE9-CODER-RESULT.md` (this investigation handoff).
- Notion/kernel/parent records: NOT UPDATED; parent owned.

## GitHub state

- Commit: NONE by Coder.
- Assigned roots: detached exact published Stage8 baselines listed above.
- Push/PR/CI/deployment: NONE by Coder; parent owned.

## Recommendation to Architect

Dispose the two bounded preservation choices above, then continue the same
Stage9 source bundle in the existing assigned roots. No owner fixtures, real
models/media or extra authority exceptions are needed for synthetic qualification.

## Review disposition

PENDING Architect. Stage9 implementation remains open; investigation is not
source acceptance and not full Goal completion. Native handoff supplied directly.

---

# CODEX RESULT — 027A/R5F Stage9 actual frozen implementation final

2026-10-02T20:52Z. This append supersedes the investigation's implementation
status, not its history. Original 10,757-byte prefix SHA256
`30cc0a07ed70da5e71674ee9b990fec5ce79634f060da70e93ef2127c7bcec1d`
is preserved. Same sole native Coder; independent acceptance remains parent-owned.

## Verdict

PARTIAL — bounded source bundle implemented, frozen and ready for independent
review. Source regression qualification is complete. Installed effective native
sandbox qualification is BLOCKED by the inert readiness timeout below; spoken
enrollment retains the explicit OWNER/AUTHENTICATED gate. Neither runtime
deployment nor whole-Goal/physical/improvement completion is claimed.

## Retrieval confidence

ADEQUATE for current caller composition, Core policy/identity/catalogue,
host executors, durable relative-effect reservation and preservation controls.
Installed candidate sandbox behavior remains NOT QUALIFIED, not inferred from
permission arguments or documentation.

## Technical state discovered and dispositions

The initial two authority questions were explicitly disposed by Architect in
the native conversation: retain the shared thread/history, fail closed for broad
Office permission after household exposure or unknown legacy eligibility, and
retain standalone Office only for demonstrably eligible trusted standalone
context/history. Thin adapters for the six existing audio controls were approved
under current principal/access/OPA/frozen catalogue and direct-only admission.
No invented UIIdentity, AUTHENTICATED inference, policy lowering or voice
enrollment exception was approved. Existing authenticated UI enrollment stays.

Parent execution state was read-only revalidated: OWNED, session
`01a052d8-2511-7382-a1ef-b0a080514788`, generation4/fence4, latest observed
activity20:44Z. No ownership acquisition/release. Assigned baselines remain
ANIMA8396c7eb261c6c0ee51c96d24b4012966d216768 and
SENTRY6eafe70dcf0674ca66a8df866105965705dff841; no Coder commits.
Parent's Stage8 hosted/deployment checkpoint is separate from Stage9 proof.

## Work performed

1. Trusted caller/config establishes intended household versus explicit
   standalone scope before Office pending approvals or executor use. Missing or
   failed intended-household preparation is honestly unavailable with no Office
   fallback/model launch. Unknown surfaces fail closed; always-on voice requires
   explicit valid disabled household configuration for standalone intent.
2. Household direct turns reuse the restrictive per-turn permission composition
   without becoming autonomous or losing the direct identity/request/catalogue.
   Read-only inheritance is explicit (`extends=:read-only`); no search/native
   engineering escape is retained. Private persistent profile is not edited.
3. Session exposure is monotonic before potentially ambiguous household launch.
   Existing/legacy ineligible history blocks broad Office without reset, rotation,
   guessed sanitization or transcript/private-config inspection. Explicit trusted
   standalone controls remain supported with the same model/persona/history.
4. The existing host authority broker independently rejects non-standalone
   Office execution. All 39 existing Office MCP tools, including reads, camera
   enrollment and raw audio, carry that gate. Source/policy/service/credential/
   bare.env and symlink routes are guarded; terminal/editor/browser input is
   rejected. File move uses no-follow directory/file descriptors, exclusive
   destination creation and source inode checks, not overwrite-prone shutil.move.
   This is bounded broker protection, not proof of a complete OS sandbox or
   unforgeable active-window identity.
5. Six existing audio operations are typed Core tools, direct current-principal
   only. Core current OPA/access/frozen catalogue precede fixed authenticated
   host transport. LIMITED reads survive; LIMITED mutations and autonomous
   audio commands remain denied. RECOGNIZED remains RECOGNIZED. Fixed workstation
   volume/mute and Pi USB/HDMI helpers are reused, not generalized into shell or
   arbitrary transport. Host replies are bounded normalized audio metadata.
6. The late independent finding disproved the initial relative-volume KEYED
   assumption: identical InvocationContext twice dispatched twice (55 then60)
   with scripted audio. Preserve that E2 negative; no physical effect was tested.
   The corrected relative path now carries a Core-owned ActionRequest generated
   from the real current identity/request/ordinal into the existing action ledger.
   Atomic claim precedes EXECUTING persistence and HTTP dispatch. Duplicate
   success projects the recorded result; PLANNED/EXECUTING/unknown/recovered
   attempts never dispatch again or claim success. Argument/key conflicts and
   stale worker fences execute zero additional calls. Missing durable binding
   fails closed. There is no new store, worker, retry or authority engine.
   Absolute setters remain idempotent operations, distinct from relative delta.
7. Existing Core-authorized authenticated UI face transport remains unchanged.
   Voice recognition alone cannot authorize enrollment; there is no fabricated
   authenticated spoken approval path. Stage8 direct-result/task/approval/alert
   channels, Stage7 RICH-only feedback, Truth/current OPA and private isolation
   remain intact. No historical task/ambiguity/receipt cleanup occurred.

## Files / areas changed — exact frozen custody

Twenty files: seven ANIMA, thirteen SENTRY. Final manifest:
`/tmp/anima-stage9-evidence.NP1oUT/source-manifest-refrozen.sha256`, SHA256
`734b3ce76340bc89f83cf9fe0c29a1e310f89643189f11919e117d931a3a9c4f`.
Whole 503-file src/tests/policy/integrations/scripts/UI/tools/perception/workflow/
dependency-declaration selection:
`/tmp/anima-stage9-evidence.NP1oUT/refreeze-whole.sha256`, SHA256
`f4df3783051374fa9b1d7422a00f271e774a81d0ba6cb3f5c0aee4e49b1b62fa`.
All twenty and all503 checked unchanged after final qualification in
`manifest-final-check.log` and `custody-final.log`. No source edits after this
corrected freeze. Initial20 manifest f9f31b57… and whole dc43dfce… retained.

Paths below are relative to their assigned roots; complete hashes are in the
manifest (also reproduced here for durable packet custody):

```text
ANIMA
15c81bc06f3a19ecf2a1a57c486045e1abba33201a9bb0da342a438c8b399046 .github/workflows/ci.yml
6d15e7de9863411127a4daf2b9372849ecf2db6f0498dc619b726c0992c4f938 src/anima_ha/plugins.py
b2b0476717130b984976dd96dc335ac997690e06a2cec88f8c21c31dcb53b383 src/anima_ha/sentry_boundary.py
ff62030fc3866246458f470142e8c8d3a3ab7fcb2bcd78eafe0e78f007c389ee src/anima_ha/sentry_identity_profiles.py
b0e12f68291234fc98da9e74b3b85a392b349d18e87fb0e2033f8326f44499a6 src/anima_ha/sentry_voice_settings.py
40f0040730bfa8faa2373a31a7d9d60a8df6898cf41bc7538ce72cb42e320f21 src/anima_ha/ui_runtime.py
e0718ea9efdb7295b8a6e3906b2b9c214711db1665723f8c55082ffbb0339174 tests/test_stage9_audio_postgres.py
SENTRY
8f3ea22cf9bea3ff7990a3f26a1fdc525958b9c684041e8bd91631ec4123dfb1 .github/workflows/ubuntu-tests.yml
82e8fea53ee3e1baff0d421dff63b015bec80f981bb5a42f85310901b5cc78be tests/test_codex_native_agent.py
e26a3a16e5e6c26ec0005f20993d393016de40ac179c67bd9d231d48a72fdb11 tests/test_conversation_bridge.py
e41f3d038cda6dfd6ae137cdd3e79d50f9bd409998f28ed99c64dd1aa488f52b tests/test_sentry_anima.py
35fbe7b3505755233cd3a21e7c68306665509d2a4a9b07579c1b6dedf7f3bee6 tests/test_sentry_mcp.py
170af55aa289cb5c5be4a39bc15d95261208ac534f65589b50a57420457d6c23 tests/test_stage9_scope.py
4a0e372ddc942bdc4f42a5893fadc3c7a7af4a1994b7dbbf3dac32b7ba3e0731 tools/sentry_anima.py
a187c88cdb4a751aa353cb574ee113fadeff4b72a818ced6d7028c5936c62bf5 tools/sentry_anima_events.py
f82276ef73414a1712b3d6805be84d1849180dc57b0f013194994a3b86065792 tools/sentry_codex_agent.py
4154625d6f6a7fc7eee8b5fe8116cef775fc67f4e442bb75f30a4c826e05663d tools/sentry_codex_profile.py
e1bce82c3a247a15408a3cd7a71ddb28e63b71a1a1f3a0df429f81a473503718 tools/sentry_execution_authority.py
0f5fb79e8d998b9cbc27834b19721aa33d0195af3f4932ac8a332fc25ece1a40 tools/sentry_mcp_server.py
7274f7cd3e06fb8b79917f9775bdcab69bbe159a57eec0f2c1cc8ba2855c5d4c tools/sentry_state_api.py
```

Only intentional setup symlink is SENTRY perception-data/models to the existing
original cached models. It is excluded from source manifests; no asset copies or
downloads. No UI files, requirements, private profiles, Graft or global files
changed. Both detached `git diff --check` checks passed.

## Validation — actual commands, results and boundaries

Evidence root throughout: `/tmp/anima-stage9-evidence.NP1oUT`.
All model-caller fixtures have temporary HOME/SENTRY_AUTHORITY_ROOT/workspace/
CODEX/XDG bindings, including the clear-environment conversation fixture.
`anima-source-binding.log` and `sentry-source-binding.log` confirm actual imports
from the assigned roots, not original editable main.

- Complete ANIMA final: PASSED. Actual command is
  `/bin/bash /tmp/anima-stage9-evidence.NP1oUT/run-full-pg.sh anima-full-complete`.
  It runs env-i, explicit provider=sentry, worktree src/tests PYTHONPATH, explicit
  Stage8 second SENTRY source, restricted disposable PG/current OPA, BOTH
  ANIMA_STAGE2_TEST_DATABASE_URL and ANIMA_VENDOR_TEST_DATABASE_URL, pytest `-q
  -o addopts=` over `tests/` AND
  `integrations/sentry/anima-household/test_household_worker.py`.
  Actual log: **1531 parent passes,81 skips,43 successful subtest reports,
  549.51s**, zero failure/error. XML has **1612 testcase elements** (1531+81),
  **60 worker testcase elements**, all five Stage9 cases/no skip. Suite counter
 1655 includes43 successful subtest reports; these are NOT43 additional
  independent parent cases. `final-counts.json` records the exact boundary.
  Final XML SHA256
  `181b48ea4b6c837b1a74ea2ca313aefa2dba514e6520c58dcda9dcd2710d118f`;
  log SHA256
  `88d2d4224264d6f5223a7908841c02ad4c0bd00bc05b0dcd8753f3ed68ccaa15`.
  Selected before/after custody hashes both
  `648e2839bd79a9a7e56be7f8709969330ecf465ea834e52eb9fdd5abc13ed461`;
  wrapper exit0/DRAFT_SELECTED_SOURCE_UNCHANGED; whole503 separate anchor also
  covers integrations/workflows omitted from that narrower wrapper selection.
- Focused corrected PG/OPA: PASSED, `run-pg.sh pg-relative-corrected`,
  **7PASS/0skip/failure/error,13.145s**: five real-PG/current-OPA Stage9 cases plus
  two existing household-user deterministic tests. The existing authenticated
  UI face positive uses its preexisting mocked AllowEvaluator/graph/client:
  it is E2 preservation evidence, NOT a new real-PG/OPA enrollment positive.
  New recognized enrollment denial is real-PG/current-OPA. Audio Core tests use
  scripted transport; separate SENTRY tests exercise actual authenticated HTTP
  dispatch with scripted media. No physical/audio/camera receipt is claimed.
  XML SHA256
  `cc8492884328521dfddecad8af41b3c19718e7f4c1fbe82bcbd485bbdd3e3321`.
  Current scope/access/argument/revocation, duplicate/conflict/nested concurrent,
  lost reply/reconstructed plugin/recovery/stale fence cases pass.
- SENTRY final: PASSED, env-i temporary HOME/audit/workspace/CODEX/XDG,
  SENTRY_HOST_SCOPE=STANDALONE, assigned PYTHONPATH, explicit existing interpreter,
  `python -B -m unittest discover -s tests -p 'test_*.py' -v`.
  **603run/596PASS/7skip,113.537s**, no failure/error; not603 passes.
  `sentry-full-frozen.log` SHA256
  `a90d8819a092b5e7be69f7bc807c7f7379bd309272b9d0639a90eb352cdb317f`.
  All138 SENTRY files in the original whole-source freeze still match, subset
  SHA256 `3679e9d43f7f707ee5d82d277c119aead72bc25f5ac0d858fd294da63659b27b`,
  recorded in `sentry-final-custody.json`. ANIMA-only correction does not require
  another SENTRY run. Earlier focused86run/85PASS/1skip retained separately.
- ANIMA Ruff `check src tests`: PASSED, `ruff-refrozen.log`.
- Strict mypy `src tests`, explicit worktree PYTHONPATH and temporary cache:
  PASSED, **196 source files**, `mypy-refrozen.log`.
- Python compile src/tests and both SENTRY integration directories: PASSED,
  temporary pycache; `compile-refrozen.log`, `integrations-compile.log`.
  SENTRY tools/perception/tests compile: PASSED, `sentry-compile.log`.
- SENTRY lint: FAILED as a clean-lint claim. Repository tools/tests F,E9 found38
  existing findings. Changed twelve Python files have four F401 findings, all
  exactly present in baseline sentry_mcp_server.py; read-only baseline comparison
  PASSED with **0 added findings**, `sentry-lint-baseline.jsonl`. Original full
  and changed lint failures preserved; no scope-expanding style cleanup.
- Current OPA policy tests: PASSED **9/9**, cached pinned image, read-only mounted
  actual `policy/phase4`; `opa-policy.log` SHA256
  `e7c12b58f1d06969ee4204ed7321a51a421028da1a5e4271940af5f90d4c2e5e`.
- Workflow YAML/shell/no-skip interpretation guards: PASSED,
  `workflow-static-corrected.log`: actual parsed YAML, bash -n all49 ANIMA and
  seven SENTRY run bodies, Stage9 five-case/no-skip JUnit guard, older Stage2–8/
  worker/vendor URL/immutable second source/dedicated Stage8 browser retained.
  Stage9 hosted targets wired, NOT EXECUTED by Coder. Parent retains mechanical
  accepted paired SENTRY pin/publication responsibility; existing Stage8 pin is
  still6eafe70, not a mutable branch. No new browser discovery surface.
- New frontend/browser/type/Vite checks: NOT APPLICABLE; no UI touched.
  Existing full browser/platform scripts and standalone MCP certification script
  NOT RUN separately here; do not infer new installed-client coverage from unit
  tests or inherited hosted Stage8 evidence.

The81 ANIMA skips are declared missing separate family/routines/preferences/
late-binding/bridge-review fixtures, explicit user-systemd sandbox qualification
and one sibling-graph check. No Stage9 target skip. Exact messages/counts in
`final-counts.json`. SENTRY seven skips: one unavailable sibling ANIMA client,
four installed-CLI parser/feature checks unavailable under isolated PATH, two
explicit opt-in no-model CLI/private sandbox qualifications. These are limits,
not successful negative/security controls.

## Fixture isolation / privileges / negatives retained

PG cached pin:
`pgvector/pgvector:pg16-bookworm@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`.
OPA cached image:
`sha256:39daf255ae7f25d81103f03a0c18308a50b7b5bb67907bed6166f70e24a970ff`.
Fresh owned-label --rm/tmpfs containers/random loopback ports. Disposable
fixture_admin is privileged ONLY for extension/bootstrap/role/database setup.
Actual test role stage2 is NOSUPERUSER/NOCREATEDB/NOCREATEROLE; all three flags
false in final logs. Owner database/credentials are never used. Cleanup validates
exact container ID and own label before stopping; final own-label listing empty.

Preserved diagnostic/test history is not overwritten or promoted:

- `scope-first.log`:8run/one error, incorrect assertion expecting status rather
  than security_handler on the existing security response.
- `focused-first.log`:86run/one failure30errors/one skip; temporary HOME did not
  exist, plus new-scope fixture assumptions. `focused-second.log`:four failures/
  one error/one skip. Existing standalone controls were corrected to declare
  valid synthetic disabled-household config and eligible synthetic standalone
  history; scope guards were not weakened. Clear-env HOME/audit bindings retained.
- ANIMA Ruff initial29 errors and later long SQL string diagnostic retained,
  corrected only imports/formatting. Prior mypy success retained.
- `anima-full-first.xml`:1352PASS199skip, no PG, tests-only/pre-freeze. NOT final.
- `anima-full-frozen.xml`:1469PASS82skip, tests-only, but source changed during
  the mandatory late relative-effect correction; wrapper exit3. NOT final-source
  qualification and omits worker60/vendor input; preserve both limitations.
- `pg-relative.xml`:6PASS/one fixture assertion failure. Query accidentally
  included retained audio actions from the preceding random-household fixture;
  corrected household scoping only. Corrected seven-case artifact is separate.
- `anima-full-refrozen.log/xml`: tests-only command superseded early by parent's
  explicit worker/vendor coverage correction. Exact own pytest PID/argv validated
  before SIGINT; KeyboardInterrupt/exit2. Incomplete counters are NOT qualification.
- First copied-runner patch context mismatch and initial workflow guard's wrong
  long spelling (`--config` versus existing `-c`) retained in tool/log evidence.
  YAML/bash parsing already passed; corrected guard artifact is separate.
- Prior SENTRY full-first/full-final logs remain prequalification history;
  only full-frozen plus matching SENTRY source custody is the final full anchor.
- Existing eight owner synthetic receipts/classification remain untouched. No
  total project/billing-zero or model/provider-runtime-zero inference is made.

## Evidence level and acceptance results

E4_REGRESSION_PROTECTED for the bounded implemented source/guard/audio-relative
reservation paths; E3 actual restricted-PG/current-OPA targets; separate E2
authenticated HTTP/scripted host and existing UI enrollment preservation.
No E5 owner/runtime/physical/audio/voice/model/isolation claim.

- Intended household launch/failed binding/no Office fallback: PASSED source/
  composed mocked caller tests, including mandatory zero-invocation failure.
- Trusted standalone/history preservation and cross-scope pending work isolation:
  PASSED source/fixtures; legacy/household history fails closed unchanged.
- Host independent scope/path/input/no-overwrite guards: PASSED bounded synthetic
  controls/regression; not whole-OS security proof.
- Six direct current-principal audio controls/current access/OPA/frozen catalogue:
  PASSED scripted executor/current Core targets. Relative KEYED effect no replay:
  PASSED corrected actual-PG duplicate/unknown/restart/fence controls.
- Enrollment authority preservation: PASSED authenticated UI source/preexisting
  E2 workflow; RECOGNIZED voice denial PASSED real-PG/current-OPA. Spoken enrollment
  completion BLOCKED on genuine OWNER/AUTHENTICATED authority, as disposed.
- Stage8 result/task/approval/alert, Stage7 rich-only feedback/private boundaries:
  PASSED complete exact-source regression including60 helper tests; remaining
  missing optional fixtures explicitly skipped, no historical/physical claims.
- Installed effective native sandbox/client isolation: BLOCKED/NOT QUALIFIED.
  Fresh inert synthetic HOME/CODEX only, installed CLI `sandbox -p read-only -P
  audit-effective -C <syntheticworkspace> -- python -I -B probe.py read ...`.
  Legitimate read readiness timed out15s, empty stdout/stderr, helper terminated
  (-9) by bounded fixture. Synthetic bytes unchanged. Subsequent write/create/
  outside-write/network probes NOT RUN. No real model/provider/auth/audio/media
  request. `sandbox.log` retains the exact command and negatives. Parent's prior
  six inert controls are historical context, not upgraded candidate proof.

## External discovery

OpenAI Docs guidance and official Codex configuration reference checked for
permission profile inheritance:
https://learn.chatgpt.com/docs/config-file/config-reference .
Used existing client composition and read-only profile, no dependency/framework
replacement. Documentation/argv correctness does not resolve the actual inert
helper timeout. Authority skill drove explicit source/review-pending boundaries,
append-only history and escalation of the two material preservation choices;
parent's direct dispositions, not the skill, authorized the thin adapters.
Cached Graft absent: exact-source fallback, no refresh/build/npx/global mutation.

## Assumptions confirmed / disproven / durable learnings

Confirmed: host-established scope and host executor gates are independently
necessary; six fixed audio controls can reuse current Core authority and host
transport without broad Office; recognized identity is not authenticated.
Disproven: absence of household binding proves standalone intent; model permission
argv alone proves installed isolation; KEYED metadata alone durably deduplicates
an internal governed relative tool. A relative host effect requires a committed
attempt reservation and conservative unknown projection before any retry/replay.
Explicit immutable source custody and parent/subtest count boundaries are needed
for reliable full-suite handoff, not just a green log tail.

## Risks / blockers / deviations

Runtime sandbox readiness remains the concrete operational qualification gate;
do not accept a stronger isolation claim from this Coder report. Voice enrollment
requires existing genuine authenticated authority; no exception implemented.
Four unchanged changed-file lint findings remain. Browser/installed MCP runtime
were not newly qualified. No physical sound/camera/USB/HDMI trial, household
prospective improvement, root Android/Binder closure or full-Goal claim.
No strategic scope expansion. Late relative-effect correction and worker/vendor
input reconciliation were explicit same-assignment parent requirements. All
product work is frozen; no further feature or speculative neighboring work.

## Project records updated / GitHub / recommendation / review disposition

Only original canonical STAGE9-CODER-RESULT.md append authorized; initial prefix
preserved. Kernels/coverage/Notion/current/acceptance/lock remain parent owned.
No commit/push/PR/CI/deployment/restart/root by Coder. Both product roots remain
detached at their assigned baselines with exactly the twenty manifested changes.

Recommend independent review of this exact frozen bundle and disposition of the
explicit sandbox qualification limit before controlled deployment. Parent owns
paired immutable pin, staging/publication/CI/runtime and any remaining owner
authority gate. No next feature/agent/phase is proposed or authorized here.
Review PENDING Architect; this actual native final is a report, not self-acceptance.
Permanent full Goal remains ACTIVE.
