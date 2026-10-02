# CODEX RESULT — existing 027A / R5F Stage1 source bundle

## Verdict

PARTIAL — REVIEW_PENDING. Source/test bundle only. No deployment or recovered
runtime is claimed. Governance acceptance is sourced from the parent-owned
[NATIVE-ARCHITECT-REVIEWS.md](NATIVE-ARCHITECT-REVIEWS.md); this does not accept
the Coder's product work or complete the full goal.

## Retrieval confidence

ADEQUATE for bounded socket/startup/status/deployment source changes.
Installed graph was read independently; root enforcement/actual recovery remains
unqualified. No new agents, threads, model setting, goal or worktree.

## Technical state discovered

- Local heads/branches preserved: ANIMA main c8ea05efe8c5a6ae5def4a1c75834910aa519d44;
  SENTRY feature/v0.4-personal-continuity e2ab3b75781ec293f8830d910cb7622f34bd82cb.
  Source-loaded Core module is the local src/anima_ha/sentry_service.py, not GVFS.
- Canonical execution state checked OWNED, parent session
  01a052d8-2511-7382-a1ef-b0a080514788, generation/fence4. Coder never acquired,
  released or wrote the execution state.
- Existing Core startup unlinked live sockets and upserted identity registration.
  OwnerBoundary probed listeners but only after credential/registration work.
- Installed anima-pc and voice/supervisor have After=default.target; default
  target orders after wanted services. Boot's dropped Core/Wi-Fi jobs are
  independently reproduced governance evidence, not recovered operation.
- Installed voice 10-atlas-storage.conf only adds After=local-fs.target.
  Shared enabled/active atlas-storage-mount.service has Before= eight SENTRY
  services, creating inverse After=atlas-storage-mount.service on voice.
  Shared mount, its source/drop-ins and other projects are untouched.
  Local path rendering is NOT proof of mount-independent startup.
- UI accepted arbitrarily old diagnostic JSON and overwrote desired sleep from
  observed sleep. Missing sensor service was presented as an empty registry.
- Profile inference correction: enabled-server-only listing showed sentry_office,
  but configured servers include anima_household, intentionally enabled=false.
  Actual installed private profile is
  /home/sketch/.local/share/sentry/codex-home/sentry-resident.config.toml,
  SHA256 04b2d03d19356a628c03d84ff7d69e88f7898ab9b6cdc1118b438c7dde0b12ee.
  Its ANIMA args match copied client path, env_vars=[ANIMA_PREBOUND_FILE], exact
  five prebound tools, network=false, default_permissions=sentry-resident.
  Existing config/token/turn-root denies all pass filesystem_denies; autonomous
  override construction validates. This is installed configuration/source proof,
  not an effective live voice launch or model/consumer outcome.
- The unnecessary new bind-anima helper/tests were removed after correction.
  tools/sentry_codex_profile.py and tests/test_sentry_anima.py have no task diff.
  Existing generator/install --anima-config remains available; regeneration is
  not necessary for this qualified installed binding. No profile write.
- All four actual binderfs names exist (anbox-binder, anbox-hwbinder,
  anbox-vndbinder, binder-control), root:root0600. Tool NoNewPrivs=1.
  Installed root unit active since Sept30, nodes recreated Oct1; ExecStartPost
  chmod has n/a execution metadata under currently loaded configuration.
  Parent reproduced root daemon EPERM and driver-probe mount accumulation,
  stopped only user session/supervisor; count stabilized at8247 (parent evidence).
  Existing bounded root helper uses sudo -n waydroid shell. This tool cannot
  obtain that privilege; passwords/new agents/new privileged units are not fixes.

## Work performed

- Persistent lifetime flock and inode-owned Unix socket cleanup shared by both
  entry points; stale socket recovery only after refused listener and inode check.
  Duplicate process fails before migration/watchers/registration. Initialization
  failure and SIGTERM/INT normal stop clean only own socket; stop own watcher.
- Restart uses INSERT ON CONFLICT DO NOTHING + current active-binding validation.
  Revocation/rotation cannot be undone; OwnerBoundary retains
  OWNER_CLIENT_REVOKED_OR_ROTATED classification.
- PC UI explicit external mode avoids credential minting/private lock access/
  duplicate bind across Core UID1000 and UI UID10001/GID1000. Reports
  EXTERNAL_UNVERIFIED, not fabricated READY; no credential permissions widened.
- Tracked actual PC stack unit, removed default.target reverse edges from nine
  affected SENTRY service templates. Stack waits Compose health then actual OPA
  HTTP response; Core ExecStartPost requires authenticated /v1/health response.
  Optional integrated voice/supervisor drop-ins require/After that ready Core.
- Bounded deployment planners copy exact unit/client manifests only, default
  dry-run, no enable/reload/start or secret provisioning. Docker ignores Graft
  and governance/local tooling. Existing source Dockerfile build remains the
  reviewed mechanism; no images built/installed in this turn.
- Voice consumers reject missing/naive/future/stale (>60s) observed timestamps.
  UI/projection/CLI share observation semantics. Supervisor publishes fresh,
  ephemeral readback of canonical desired sleep/instance separately. UI does not
  fabricate observed SLEEPING/STARTING from intent; orb design unchanged.
  Unavailable sensor snapshot hides stale rows and differs from CURRENT empty.
- Android access guard blocks only positive BINDER_PERMISSION/SOURCE_ACCESS
  faults before session/container start; no control-node user-access prerequisite.
  Missing drivers/stopped container/empty getprop remain transitional and
  self-healing. Session ExecCondition and bounded start limit prevent hot retry;
  supervisor no longer Wants session before its guard. Status is NOT_READY,
  owner_root_gate=true, no recovery_attempted, vendor state UNKNOWN, not a
  false login/permission diagnosis. Current stopped runtime remains untouched.
- Review-only root fragment adds DeviceAllow=char-binder rw to existing unit.
  systemd255 /proc/devices binder major509 future minors is a supported targeted
  candidate, not proof of corrected cgroup enforcement. Owner/root must review
  and apply/restart existing unit legitimately; no new privilege infrastructure.

## Files / areas changed

Every path below is relative to the stated absolute repo root. Stage1 changes
only; earlier accepted governance changes remain in the same dirty tree.

ANIMA root: /home/sketch/Projects/ANIMA Home Automation

- .dockerignore
- compose.pc.yaml
- deploy/systemd/user/anima-pc.service (new)
- deploy/systemd/user/anima-core.service
- deploy/systemd/system/waydroid-container.service.d/anima-binder.conf (new, review candidate)
- scripts/check_pc_readiness.py (new)
- scripts/install_pc_runtime.py (new)
- scripts/install_waydroid_vendor_runtime.py
- scripts/waydroid_notification_supervisor.py
- src/anima_ha/owner_boundary.py
- src/anima_ha/sentry_service.py
- src/anima_ha/ui_api.py
- tests/test_sentry_socket_ownership.py (new)
- tests/test_pc_runtime_deployment.py (new)
- tests/test_startup_ordering.py (new; integrated graph requires sibling checkout)
- tests/test_waydroid_notification_supervisor.py

SENTRY root: /home/sketch/Projects/SENTRY

- deploy/systemd/user/sentry-alarms.service
- deploy/systemd/user/sentry-perception.service
- deploy/systemd/user/sentry-proactive.service
- deploy/systemd/user/sentry-projection-status.service
- deploy/systemd/user/sentry-routines.service
- deploy/systemd/user/sentry-state-api.service
- deploy/systemd/user/sentry-voice-supervisor.service
- deploy/systemd/user/sentry-voice.service
- deploy/systemd/user/sentry-weather.service
- perception/voice_status.py (new)
- tools/sentry_install_stage1.py (new)
- tools/sentry_projection_status.py
- tools/sentry_ui.py
- tools/sentry_voice_status.py
- tools/sentry_voice_supervisor.py
- tests/test_stage1_deployment.py (new)
- tests/test_voice_status_freshness.py (new)
- tests/test_sentry_ui.py

Records in BOTH roots: .agent/INDEX.md, CURRENT.md, DIRECTIVES.md, OUTCOMES.md,
RECORD.md. In ANIMA existing027A only: DIRECTIVE.md, EVIDENCE.md, HANDOFF.md and
this new STAGE1-CODER-RESULT.md. Parent-owned GOAL-COVERAGE.md and
NATIVE-ARCHITECT-REVIEWS.md not edited. Goals, profile/kernel role contracts and
prior directive/evidence bytes preserved.

## Validation

- Complete final ANIMA suite: PASSED 1229/76 skipped in177.26s, after final
  startup and permission-classification regressions. Command: .venv/bin/python
  -m pytest. Bare pytest executable initially failed pre-existing scripts imports;
  module invocation supplies the repository path without source workarounds.
- Focused socket/owner/deployment/Android/startup: PASSED 27 before the final
  classification test; that added regression passes in the final complete suite.
- Worker/autowake/boundary: PASSED 78, 31 skipped, 43 subtests; PostgreSQL opt-in
  coverage skipped, not live eligibility proof.
- Complete current SENTRY: FAILED baseline debt; 565 run, 564 pass, 1 failure,
  0 errors/0 skips. test_resident_runtime.ResidentRuntimeTests.
  test_units_use_accepted_paths_and_isolated_services expects literal
  "both SENTRY faces are display-only" absent from committed UI too.
  Re-running that test with committed UI text reproduced exactly one failure,
  zero errors. No assertion weakened/comment added to mask it.
- Focused SENTRY UI/freshness/supervisor/deploy/profile/ANIMA/MCP: PASSED 148.
- Changed ANIMA files Ruff: PASSED; source sentry_service/owner_boundary strict
  mypy: PASSED. Existing broad lint debt not mass-formatted.
- Both compileall and git diff --check: PASSED.
- systemd-analyze --user verify tracked PC/Core/worker/Wi-Fi/voice/supervisor:
  PASSED. Cross-repo tracked graph acyclic; old default-target edges independently
  reproduce cycles. Installed/reloaded recovery graph: NOT RUN.
- Deployment dry-run manifests: PASSED, no writes/reloads/restarts.
- Actual installed profile deny/args/override checks: PASSED, no model call.
- Actual queue age/eligibility at recovery time: NOT RUN by Coder. Source excludes
  AUTONOMOUS_ATTENTION from household-worker claims; resident autowake uses <=120s
  window, enable epoch, pristine pending provenance/no invocation, no blind backlog
  replay. Parent must recheck actual ages/sleep before explicit deployment approval.
  134 PENDING /33 RECOVERY_REQUIRED /13 UNKNOWN_RESULT are attributed parent
  observations, not changed/recounted here.
- Installed units, copied worker/runtime, credential/profile/model/thread/persona,
  ambiguous work, physical devices, Git staging/commit/push, Notion writes:
  NOT MUTATED by Coder. No installed readiness/recovery/browser acceptance.
- Ignore files and ANIMA Graft fence match baseline fingerprints; both staged
  path lists are empty. SENTRY Graft matches baseline digest. SENTRY raw index
  hash changed at final check (no staged content); not byte-preservation evidence.
- Initial dirty ledger/task prefixes: PASSED byte-prefix SHA256 comparison for
  all nine append-only files against the original Coder baseline snapshot.
- ANIMA Graft internal cache preservation: FAILED; see exception below.

## Evidence level

E4_REGRESSION_PROTECTED for bounded implemented/tested source behavior, with
explicit complete-SENTRY baseline debt and skipped database tests.
Installed Android and unit observations E1/E2; runtime recovery E5 NOT REACHED.

## Acceptance results

Source socket collision/cleanup/registration and negative mixed-UID path: PASSED.
Source ordering/readiness/manifest/status and fault/coldboot regressions: PASSED.
Governance acceptance navigation: PASSED, sourced independent disposition.
Byte-identical ANIMA Graft cache: FAILED. Complete SENTRY green: FAILED baseline.
Actual installed recovery/owner workflow/physical/full-goal: NOT RUN.
Product independent review remains PENDING.

## External discovery

Python3.12 official socketserver and fcntl references informed safe server shutdown
and lifetime flock. https://docs.python.org/3.12/library/socketserver.html ;
https://docs.python.org/3.12/library/fcntl.html .
Installed systemd255 resource-control documentation and parent upstream Waydroid
1.6.2 driver evidence support the narrow dynamic Binder candidate. No strategic
replacement. Official online systemd255 page access failed; local manual and
parent evidence remain the stated boundary.

## Assumptions confirmed

Dedicated Core must own provider socket; ready means authenticated service response.
Existing prebound disabled-at-rest ANIMA stanza is intentional and qualified.
Shared mount supplies inverse startup ordering; removing path prefixes cannot
prove independent startup. Root permission failures do not authorize bypasses.

## Assumptions disproven

Enabled-server-only listing implied missing ANIMA binding (corrected; no edit).
Root-only binder-control is a user listener prerequisite (false).
Every failed getprop means nontransient SOURCE_ACCESS (false; coldboot supported).
Graft ask is always non-mutating (false after changed source).

## New durable learnings

Default target ordering cycles, bind-before-mutation single ownership and desired/
observed status separation are regression-covered. Cache retrieval itself can
auto-refresh; do not claim byte preservation from omission of explicit build.

## Risks / blockers

Independent parent product review and later explicit deployment approval.
Fresh actual queue/sleep validation; no ambiguous reset or historical storm.
Root/owner legitimate access and targeted Binder unit repair; containment persists.
Mixed-UID UI provider readback is explicitly unverified, not fabricated ready.
Inherited shared mount ordering and current installed/source drift remain.
SENTRY complete-suite literal assertion debt and skipped DB tests.
ANIMA Graft cache changed; prior exact bytes were not snapshotted by this Coder.

## Deviations from directive

Mandatory Graft ask auto-refreshed six source entries at2026-10-02T01:34:30Z.
No build requested. At that time internal ask-index/extract/fingerprint/wiring
files were refreshed; markdown nodes retain their original Sept11 mtimes.
No further Graft command, manual reconstruction or rollback without exact original
bytes. Counts alone are not preservation evidence. No other expanded authority.

## Project records updated

Both mutable CURRENT/INDEX and append-only DIRECTIVES/OUTCOMES/RECORD.
Existing027A DIRECTIVE/EVIDENCE/HANDOFF link parent acceptance and this result.
Notion: NOT UPDATED by Coder. Parent owns review and full GOAL-COVERAGE map.

## GitHub state

Commit NONE; push/PR NONE. Original local heads/branches and dirty assessment/
tooling retained. Parent-reported remote heads/Notion updates are not Coder checks.

## Recommendation to Architect

Review source and negative tests; adjudicate baseline test/cache exception.
Then independently check actual queue ages/canonical sleep and approve a bounded
PC/Core/SENTRY deployment using manifest planners (no default restart). Rebuild
UI with the existing Dockerfile after approval; compare deployed bytes, refresh
units, and test authenticated readiness/current truthful status without model/
physical calls. Root Binder candidate is a separate essential-access gate.
Keep both Android user session/supervisor stopped until reviewed root repair.
Do not remove shared mount or regenerate the already-qualified resident profile.

## Review disposition

PENDING — product source only. Coder cannot accept itself; governance acceptance
is separate. No whole-goal completion, model outcome or owner workflow claimed.

## Exact instruction loading

Explicit reads, not client automatic reload. Under BOTH absolute repo roots:
AGENTS.md; .agents/skills/authority/SKILL.md; .agent/INDEX.md;
.agent/PROJECT_GOAL.md; .agent/PROJECT_PROFILE.md; .agent/CURRENT.md;
.agents/skills/authority/references/{evidence,result-contract,state-files}.md;
relevant027A DIRECTIVE/EVIDENCE/HANDOFF and parent NATIVE-ARCHITECT-REVIEWS.
Project external-discovery SKILL was read for proportional discovery.
No ancestor/nested AGENTS applying to these source paths was found.
Owner directive full230 lines was already read, SHA256
403d0c5f0115f71854cda6eb43f5f2977635e7b9b2ae681eb611334ff32c48cd.
Earlier ChatGPT Architect/relay constraints are superseded by owner transfer,
preserving historical bytes. Inherited development model unchanged.

Read-time SHA256, prior to CURRENT/INDEX Stage1 pointer updates:
| File | ANIMA | SENTRY |
| --- | --- | --- |
| AGENTS.md | 988796145f52244a3290c7668db535e2885fc9e3ccfb05af0ce8edd93016d5b6 | 1b294f894ea0fba4f2a9fb828d21eaf529a3b6fc47eda36f8030461f9dfffe0f |
| Authority SKILL.md | e3f979d47b7d2b1b5a324bb3120e599fea296e9900dcc3818d1530df0f0bfdf7 | ae6c3b75a99b7aec4d89eb43c6524595392da09e340e016344b7b408b8079ad6 |
| PROJECT_GOAL.md | cb4fd4fd55a14d368d180a09699e26507fe199d1441bd16d8354c36f14e10be3 | 6604783f1fdfbde61dcd56e19d56d724c2e3b71a722a96aeb321b1d6039b8c5a |
| PROJECT_PROFILE.md | 6cc318c07545351777aff489a179df646a5ff0e12e3ce4529082bb4b45767ab2 | edb923077fdfd3971f77d7fa1a6566678d00b749778a60e321b119bc38b12bea |
| CURRENT.md | 4a522992891f7bc908297379d1e4a91bcc58838c24474bbb902b4af802c38217 | 27c78778b4e26c2597842b9affe8e09d7aa9e8be233882c1f0b86cebee0958b5 |

## Baseline / dirty preservation and Graft reproduction

Baseline/governance snapshot before Coder mutations included ANIMA CURRENT/
OUTCOMES/.gitignore/AGENTS dirty plus .ignore and prior SYSTEM-ASSESSMENT;
SENTRY CURRENT/OUTCOMES/.gitignore plus .ignore. All preserved.
No worktree/reset/staging. Parent-created goal coverage/review records preserved.
Full prior baseline/dirty inventory stays in earlier027A EVIDENCE result.

Graft algorithm recovered verbatim from this worker's initial recorded tool input:
walk repo-relative "graft" recursively, including hidden directories, regular
files only (Dirent.isFile; symlinks skipped); append
relativePath + ":" + SHA256(rawFileBytes). Sort entire strings with JavaScript
Array.sort() (default lexical), join with LF and NO FINAL NEWLINE; hash UTF8 bytes.
Paths have "graft/" prefix, not paths relative to Graft root.

Read-only reproduction from the repo root, without npx/cache changes:
```js
const f=require("fs"),c=require("crypto"),p=require("path");
const sha=b=>c.createHash("sha256").update(b).digest("hex");
let rows=[];
function walk(d) {
  for(const e of f.readdirSync(d,{withFileTypes:true})) {
    const n=p.join(d,e.name);
    if(e.isDirectory()) walk(n);
    else if(e.isFile()) rows.push(n+":"+sha(f.readFileSync(n)));
  }
}
walk("graft");
console.log({count:rows.length,sha:sha(rows.sort().join("\n"))});
```

Original baseline:
ANIMA274 /8496a306fcc91927a67ce19c0df1b4a5a8146f99be441a8ac65dde589bd9ce97
SENTRY117 /a1d70a51c972dda89bb207ed53215523a7111412aa8314075f01ac4700fdf559
Stage1 observed:
ANIMA274 /f032acd05f22e3c6bc184987d2331c1852d26c0a73de7fceef4a1a7c6fed0d87
SENTRY117 /a1d70a51c972dda89bb207ed53215523a7111412aa8314075f01ac4700fdf559
Original cache bytes not available in this Coder's aggregate-only snapshot.
Same counts DO NOT establish ANIMA byte preservation.
Graft reported approximately52986 saved tokens for the retained Stage1 ask.

Protected file hashes still match initial snapshot:
ANIMA .gitignore cd3a8023f50c0a355940696a9b88a94b32a3d61d66233d848610c268f5a9c387
SENTRY .gitignore daf585728b846a5ab13dc2914d34010dbd7f17995dd2873df7afe3d502d031f0
Both .ignore 5b345696ac9daf0b07ce5b9c56d5ec914815e395286f4c9f9ac3ec8ec83bf507
ANIMA index14432287e9c102b651b774c4dc25737524558aa3812fc12a1054a25e1729f8d5.
SENTRY index baselinef8b3cc13bcb15541da68a708e8bcd665e2b2f02ab29b33f4301debb655a771f7;
final0b1958751b873c95b2cfbca8092791cbb6616f6370d519e6bd8eb0ce20670f53.
Staged-path lists remain empty; index bookkeeping is not a staged source edit.

Installed-byte boundary (no apply):
anima-pc installed7d17f2c7042a0a4a46a323d2364d55bb9d4bcd1d454ce207070c713e9778600d;
new source manifestcb176231686fc061a64ceef0198ab896ec5f6c31aabd5dc77c587e48a18d82b8.
Core installed4613e5da2575f642ad65c5efc54a8cc9b8fd36d750fd2f2ea907e928ea48f567;
new source0cfc103d1af13dcb2b4eab2714da3ded4b40072a1fbcd762c0eb40cc7db6c421.
Copied household_worker.py f1e6f7cf20effd264c2e7b93cf969dfc1e8f388ed629fa6913a40df0797f385d
already matches source; deployment covers all seven client/support files, not a
single-worker copy inference. Installed voice/supervisor still old units;
exact plan manifests are reproducible with the two planners, no Graft required.

## CODEX RESULT — 027A/R5F Stage1 independent-review corrections — 2026-10-01

### Verdict

PARTIAL / REVIEW_PENDING. This is a correction of the existing Stage1 source
bundle, not a new directive, phase, acceptance or deployment authorization.
The original result, baseline failures and preservation exception above remain
unchanged. Independent governance acceptance remains linked in parent-owned
`NATIVE-ARCHITECT-REVIEWS.md`; Stage1/runtime acceptance belongs to the parent.

### Retrieval confidence

ADEQUATE. Explicit rereads: both local root `AGENTS.md`,
`.agents/skills/authority/SKILL.md`, `.agent/INDEX.md`, goal/profile/current
kernel and relevant Authority result/evidence/state-file references. Loading
paths are rooted at `/home/sketch/Projects/ANIMA Home Automation` and
`/home/sketch/Projects/SENTRY`, not the inherited GVFS cwd. Root/skill hashes
remain ANIMA `988796145f52244a3290c7668db535e2885fc9e3ccfb05af0ce8edd93016d5b6` /
`e3f979d47b7d2b1b5a324bb3120e599fea296e9900dcc3818d1530df0f0bfdf7`,
SENTRY `1b294f894ea0fba4f2a9fb828d21eaf529a3b6fc47eda36f8030461f9dfffe0f` /
`ae6c3b75a99b7aec4d89eb43c6524595392da09e340e016344b7b408b8079ad6`.
These prove explicit reads, not automatic instruction reload. The direct
Architect correction authorizes bounded type/format reconciliation and forbids
further Graft cache writes; this supersedes automatic Graft retrieval/refresh
for this follow-up. Existing cached nodes were read only; no npx ask/build.
Canonical state was revalidated as parent OWNED generation/fence4 before edits;
Coder did not acquire/release the lock or mutate ownership state.

### Technical state discovered

Committed ANIMA HEAD `c8ea05efe8c5a6ae5def4a1c75834910aa519d44` independently
reproduces 40 strict-mypy errors in five files and six Ruff-format failures.
The pre-correction Stage1 tree reproduces 80 errors in nine files and nine
format failures; introduced delta is 40 errors across the four new/extended
Stage1 test modules and three format failures. Full Ruff lint passes both
the committed baseline and Stage1 tree. This supersedes any inference of
full strict-mypy qualification from earlier focused-only checks.

Baseline reproduction: ordinary `git archive HEAD` export, not a worktree,
retained at `/tmp/anima-stage1-head-validation.BcdIDS`. From that directory,
run `/home/sketch/Projects/ANIMA Home Automation/.venv/bin/python -m mypy src tests`
and the corresponding `-m ruff format --check src tests` / `-m ruff check src tests`.
Mypy checked 153 files. Inherited error paths:
`src/anima_ha/knowledge.py`, `src/anima_ha/sentry_boundary.py`,
`src/anima_ha/ui_runtime.py`, `tests/test_sentry_sensor_status.py`,
`tests/test_sentry_service_learning_lifecycle.py`.
Inherited formatting paths: `src/anima_ha/journal.py`,
`src/anima_ha/learning_review_runner.py`, `src/anima_ha/sentry_sensor_status.py`,
`src/anima_ha/wifi_presence.py`, `tests/test_sentry_sensor_status.py`,
`tests/test_wifi_presence.py`. Baseline source/export was not rewritten.

Committed SENTRY UI at `e2ab3b75781ec293f8830d910cb7622f34bd82cb` was injected
read-only into the original resident-runtime test before editing that test:
one test, one failure, zero errors, at the original line220 assertion requiring
the absent comment `both SENTRY faces are display-only`. The original broader
565-test/one-failure result above is preserved; it is not retroactively green.

### Work performed

Replaced that comment assertion with execution of the actual native window
`_build` method, extracted from its nested class for a headless test. Both
office and projection branches execute against display-only GTK doubles;
legacy local settings/enrollment construction would raise rather than silently
pass. The window attaches its native face, returns before local controls,
and only the office branch attaches read-only sensor inspection. No production
comment was injected and no authority boundary was deleted.

Added an end-to-end deterministic authority test through the actual supervisor
`reconcile_once`, canonical `client.voice_settings()` response, ephemeral
desired-status publication, native `read_voice_status`, and actual nested
`_refresh_status`. Both faces reflect ANIMA awake/office or sleep/living-room
intent while missing observed voice remains UNAVAILABLE. All systemd/client
operations are test doubles; no runtime writes, service calls or local setting
authority are exercised.

Confirmed existing healthy-idle freshness: `AlwaysOnVoiceLoop.process_chunk`
updates `VoiceDiagnostics` on every valid chunk, including silent PCM; ordinary
512-sample/16kHz capture supplies chunks about every32ms. Added a regression
with silence/no wake/no model at simulated wall times0,30,61,121,181,241 seconds.
Every persisted timestamp remains fresh and LISTENING across four TTLs; absent
further chunks, age61 becomes UNAVAILABLE. No new heartbeat thread, timer,
status fabrication or production voice change was needed. Live idle voice is
still NOT OBSERVED because deployment/recovery is not authorized.

Annotated new/extended tests, precisely typed the Unix HTTP server path
constructor (TCP-only base stubs need a narrow adapter), removed four now-unused
address ignores, and reconciled inherited types without excludes/file ignores:
nullable errno lookup; nullable untrusted initiative before existing dict
validation; stable narrowed initiative callback; typed sensor/lifecycle fakes
and explicit loader returns instead of relying on `list.append` expressions.
Formatting is mechanical within authorized `src/tests`; no mass lint rewrite,
dependency/policy/goal/model/profile/permission change.

### Files / areas changed in this follow-up

ANIMA product/test paths (relative to its local root):

- `src/anima_ha/knowledge.py`
- `src/anima_ha/sentry_boundary.py`
- `src/anima_ha/ui_runtime.py`
- `src/anima_ha/sentry_service.py`
- `src/anima_ha/owner_boundary.py`
- `src/anima_ha/journal.py` — formatting only
- `src/anima_ha/learning_review_runner.py` — formatting only
- `src/anima_ha/sentry_sensor_status.py` — formatting only
- `src/anima_ha/wifi_presence.py` — formatting only
- `tests/test_sentry_sensor_status.py`
- `tests/test_sentry_service_learning_lifecycle.py`
- `tests/test_sentry_personality.py` — obsolete address ignore only
- `tests/test_sentry_autowake.py` — obsolete address ignore only
- `tests/test_pc_runtime_deployment.py`
- `tests/test_startup_ordering.py`
- `tests/test_sentry_socket_ownership.py`
- `tests/test_waydroid_notification_supervisor.py`
- `tests/test_wifi_presence.py` — formatting only

SENTRY: `tests/test_resident_runtime.py`, `tests/test_always_on_voice.py` only.
No SENTRY production source or service file changed in this correction.
Original Stage1 and dirty-file inventory above remains the cumulative boundary.

### Validation

- SENTRY focused resident/voice: PASSED79 tests.
- SENTRY full declared unittest discovery: PASSED567 tests in87.726s;
  zero failures/errors/skips. Non-fatal unclosed-socket ResourceWarning and
  multithreaded-fork DeprecationWarning remain visible, not hidden.
- ANIMA `PATH="$PWD/.venv/bin:$PATH" bash scripts/validate.sh`: PASSED;
  locked uv sync checked56 installed packages without changes; full Ruff format
  and lint; strict mypy all156 source/test files;1229 passed/76 skipped in177.28s;
  pinned OPA policy tests PASS9/9. This is the repo's full validation wrapper,
  not merely focused mypy. Final annotation narrowing was separately rechecked
  with full format/lint/mypy, all PASSED; an exact-current wrapper repeat follows.
- ANIMA focused socket/deployment/ordering/supervisor/sensor/lifecycle: PASSED30.
- Both `git diff --check`: PASSED; staged-path lists empty; heads unchanged.
- Ignore/goal fingerprints: PASSED against original baseline.
- Graft digests: PASSED unchanged from the acknowledged auto-refresh checkpoint:
  ANIMA274 `f032acd05f22e3c6bc184987d2331c1852d26c0a73de7fceef4a1a7c6fed0d87`,
  SENTRY117 `a1d70a51c972dda89bb207ed53215523a7111412aa8314075f01ac4700fdf559`.
  No blind restoration and no further cache writes. Earlier ANIMA refresh remains
  historical evidence, now explicitly acknowledged as regenerable-cache-only.
- Hosted CI: NOT RUN (no publish/commit authorization). Service installation,
  restart/deploy, authenticated owner browser and live voice recovery: NOT RUN.
- Android root correction/recovery: BLOCKED by reviewed legitimate root gate.

### Evidence level

E4_REGRESSION_PROTECTED for the corrected source/authority/freshness boundary;
no E5 live recovery claim. Skipped ANIMA opt-in/integration tests remain limitations.

### Acceptance results

- Equivalent native UI behavior/authority assertion: PASSED.
- Committed-baseline failure and original result preserved: PASSED.
- Introduced types and authorized inherited validation debt reconciled: PASSED.
- Full SENTRY and ANIMA validation/OPA: PASSED as detailed above.
- Existing idle freshness, without unnecessary heartbeat: PASSED deterministically.
- No deploy/restart/model/household action/cache rewrite: PASSED.
- Actual runtime recovery, root repair and whole-goal completion: NOT RUN/BLOCKED.

### External discovery

NONE triggered for this annotation/test correction. No external writes or model calls.

### Assumptions confirmed / disproven

Confirmed: ANIMA owns settings; voice's chunk diagnostics are its existing idle
heartbeat; baseline failures are real; focused mypy was not full qualification.
Disproven: the old source-comment assertion proves display-only behavior; a new
heartbeat is necessary just because TTL is60. Historical inferences stand only
as history and are superseded by the direct evidence above.

### New durable learnings

Behavior-based headless execution protects nested GTK authority without needing
an installed desktop, but is not an owner-visible visual/browser acceptance.
Exact-head exports distinguish inherited type/format debt from introduced errors.

### Risks / blockers

Android remains contained/root-gated; reviewed `char-binder rw` candidate is not
installed. Shared Atlas mount/reverse ordering is unchanged. Parent reports fresh
SQL zero active claims/provider runs,134 old PENDING with zero younger than120s,
and46 ambiguity rows unchanged. This is parent evidence, not Coder SQL recount;
preserve it, freshness guards and explicit approval before any recovery.
Resident model/thread/profile/persona/voice/orb/memory and household authority
remain untouched. Source tests do not prove provider/voice/UI deployed readiness.

### Deviations from directive

NONE in this correction. Mandatory Graft refresh is superseded by the explicit
no-more-cache-writes instruction. Existing cache exception is neither hidden
nor blindly restored. No new worktree, agent, thread, directive or phase.

### Project records updated

Both `.agent/CURRENT.md` and append-only `.agent/OUTCOMES.md`; this existing027A
result, EVIDENCE and HANDOFF appended. Parent-owned reviews/GOAL-COVERAGE untouched.
Notion: NOT UPDATED (parent-owned).

### GitHub state

Commit: NONE. Heads remain ANIMA main `c8ea05efe8c5a6ae5def4a1c75834910aa519d44`
and SENTRY feature/v0.4-personal-continuity `e2ab3b75781ec293f8830d910cb7622f34bd82cb`.
Push/PR: NOT RUN. Existing dirty work and goals preserved.

### Recommendation / review disposition

Parent independently review this corrected bundle and full validation evidence,
then explicitly authorize any bounded deployment/recovery. REVIEW_PENDING;
Coder does not accept Stage1 or declare the active027A/whole goal complete.

### Final exact-current verification checkpoint

After the last annotation-only edits, the full `scripts/validate.sh` repeat
PASSED with exit0: locked sync checked56 packages without changes;156 files
already formatted; full Ruff lint PASS; strict mypy no issues in156 files;
1229 tests PASSED/76 skipped in177.41s; pinned OPA PASS9/9. SENTRY567-test result
above is already the exact-current SENTRY source (no subsequent product/test edits).
All five append-only pre-correction prefixes (both OUTCOMES plus ANIMA result,
EVIDENCE and HANDOFF) independently hash-match, including the original failure
history. Both diff checks pass and staged-path lists remain empty. Read-only
baseline export remains available to the Architect. No introduced validation
failure or remaining ANIMA format/type/lint debt under the required src/tests
contract; hosted CI and deployed/runtime acceptance remain NOT RUN.
