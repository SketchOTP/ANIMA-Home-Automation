# 026A — owner connection and visual console evidence

## Unattended SENTRY, presence, memory and trial start — 2026-09-08 UTC

- Actual request `75378ca5-ab63-5d38-9f35-d9d173d2692a` reached
  `PROVIDER_RUNNING` before the model and terminated `UNAVAILABLE` when the
  model chose an unavailable governed notification path. No TTS or success was
  claimed and the request was not replayed.
- The SENTRY autonomous guidance now identifies host TTS as `decision=speak`
  and reserves `notify` for a successfully invoked governed notification tool.
  Focused SENTRY event tests pass 51/51.
- Fresh request `0dcaff7c-3af4-5a17-8939-4f05b25afcdb` used the real Journal,
  Attention, ContextPacket, auto-wake claim, persistent Codex thread and warm
  Kokoro worker. Core recorded `ALWAYS_NOTIFY`; SENTRY returned `speak`; the
  host ledger records `RESPONSE` and `DELIVERED`.
- The event was explicitly synthetic operational qualification, not a fabricated
  physical SenseGuard observation. The real opening policy now has one active
  all-day SENTRY cognition route for both SenseGuards; the duplicate historical
  opening rule is disabled.
- `person.tym` is commissioned and bound to canonical Tym. Twenty-two opaque
  Nmap/HA candidates remain unassigned because ownership cannot be inferred.
- A real SENTRY model created one governed Obsidian note and later corrected it
  in place with its current digest and provenance. Daily and routine review
  tasks are scheduled but their due executions are not yet observed.
- The private content-free trial ledger is mode `0600`; initial report shows two
  unique attempts, one retained negative result, one required TTS delivery and
  zero duplicate records. The minimum three-day trial remains in progress from
  `2026-09-09T02:21:00Z`.
- Heartbeat `anima-household-trial-check` is active for daily content-free
  inspection and the minimum three-day summary. It is prohibited from changing
  household policy or inferring phone ownership.
- The SENTRY event source now distinguishes healthy idle `EMPTY` from actual
  `NOT_READY` gates and was observed `LISTENING` with Kokoro warm after restart.
- Local regression evidence: ANIMA validate passed with 1,142 pytest tests/74
  skips and OPA 9/9; the primary browser matrix passed 112/112 applicable
  scenarios with 14 viewport skips; isolated routines/context/initiative/
  knowledge fixtures passed 90/90; SENTRY passed 525/525.
- Hosted publication: ANIMA exact head
  `c16919271d748d28de76494405d3b37518f4a03c` passed CI `34307221255` and
  published artifact `10087481883`, digest
  `sha256:5396f6931d0289401fff0811d577b3385aaa192eb904bcaebb099a150fabf69b`.
  SENTRY exact head `b2de5913d939b2cfa05ad75bc0fd7984005a579c` passed CI
  `34306897931`. The ANIMA implementation run `34307062432` is retained as a
  failed CI-environment attempt and was corrected without rewriting history.

## Owner UI workflow convergence — 2026-09-07 UTC

The owner requested a complete usability pass, one catalogue containing native
HA/Ring and private Tapo/Wansview resources, per-device SENTRY notification
choices, and natural-language administration without leaving ANIMA. The
implemented bounded slice is documented in
`docs/OWNER-UI-WORKFLOW-AUDIT-026A.md`.

- The navigation is reduced to 15 owner outcomes. Notifications is part of
  Alerts; integration and capability status are part of Connections; SENTRY is
  the single assistant surface.
- The Devices catalogue projects commissioned `android_notification` resources
  without pretending they are HA registry devices. A regression covers the
  event-only projection.
- Versioned initiative configuration now contains per-device `ALWAYS`,
  `TIME_WINDOW`, `NEVER`, or `CONTEXTUAL` rules. Existing configs missing the
  field remain valid and inherit household defaults.
- SENTRY chat uses `/api/v1/conversation` and polls the durable request result.
  It is browser-memory-only and exposes no raw CLI/provider/HA boundary.
- Advanced normalized-event rules remain under Alerts and are explicitly
  distinguished from the everyday per-device choices on Devices.

Validation: full `anima-validate` PASSED (Ruff, strict mypy, 1125 pytest pass,
73 opt-in skips); OPA 9/9; frontend static 7/7, TypeScript and production Vite;
primary browser 100 pass/14 viewport-specific skips; initiative/Ring 42/42;
preferences 39/39; vendor connections 36/36; package wheel; `git diff --check`;
and tracked public-safety patterns. The rebuilt PC image
`sha256:1079c7b8f8ddb57b26446b79a14a4b4f5f8b653922a9d6e63565a610abe47246`
is running healthy on port 18090 and `/healthz` returned `ok`. This is E4 regression evidence for the
bounded owner-console slice, not proof of notification receipt or unrestricted
Home Assistant administration.

## Ring / initiative extension — 2026-09-07

Current report: `docs/RING-LEARNING-OWNER-INCREMENT-026A.md`. Healthy deployed
image edd377d00075; Python1094/72 opt-in skips, separate PG/OPA154, browser42+3,
SENTRY229, static/frontend/OPA/Docker/health checks pass. Ring live setup/events
and automatic resident SENTRY delivery remain unqualified. No seeded household
facts; no new commit/hosted CI. Earlier image/test counts below remain historical.

## Household context extension — 2026-09-07 UTC

Preferences, knowledge, presence setup and black/white/purple UI are deployed
on the PC. Final image, local regression boundaries, source references and
real resident read/memory receipts are recorded in
`docs/HOUSEHOLD-CONTEXT-AND-INITIATIVE-026A.md`. Python993/47 opt-in skips,
separate real PG/OPA46, presence71 and contextual browser evidence pass. No
hosted publication is claimed for these dirty local changes. One guided real
SENTRY memory lesson is now in the owner vault; no personal data was fabricated.
Actual phones/router sources and unattended event/TTS qualification remain;
automatic polling is OFF. Notion ANIMA/integration/SENTRY pages read back with
these exact limitations. Tapo/Wansview stay paused.

## Latest owner Routines completion — 2026-09-07 UTC

Tapo/Wansview development is paused. The Routines owner workflow is now deployed;
see `docs/FAMILY-ROUTINES-OWNER-GUIDE.md` for changes, real PostgreSQL/OPA versus
fixture browser evidence, final image/source checks and uncommitted-state limits.
Full Python784/8 opt-in skips; separate routine/API67; browser126 (42 routines);
Ruff/mypy104/OPA9/frontend/Docker/pattern scans passed. No owner data seeded.
This supersedes the earlier worker-only Routines source freeze, not historical
negative evidence. No whole-goal, automatic wake/TTS or vendor completion claim.

## Scope and current disposition

This is an owner product increment, not a new resilience phase. Phases 0–14
remain Architect accepted. No whole-goal or resident SENTRY acceptance is made.
Publication identifiers are supplied in the final handoff/Notion after hosted
qualification; this record distinguishes runtime observations from fixtures.

Starting SHA: `11265fb6a9d84c7b4a0cf1d9dae99a570c32d7ed`.
Starting exact CI `34063086056` failed its stale frontend login-copy assertion.
That historical failure is retained.

First owner-console implementation: `435815855ffda8ff917406daeb063ca498b7b9c7`.
Exact-head CI `34067802116` passed. Artifact `9999684628`, digest
`sha256:7e864843e026a87f0bc2f2bc12f733a4934fb17b010bc8b33c498810ef4949bc`.
This checkpoint predates the following focused live-use corrections and does
not qualify those later source changes.

## Real owner runtime observations

- HA 2026.9.0 is connected through the server-owned private credential volume.
  The actual owner was verified through HA OAuth and commissioned in a distinct
  household. No sample identity was used for these operations.
- Eight devices, five HA areas and eighteen registry entities were discovered.
- Four canonical ANIMA rooms were created through the owner UI.
- Both SONOFF SenseGuard devices were commissioned through UI → Core → policy
  → HA integration, with matching Basement/Kitchen canonical room assignments.
  PostgreSQL readback confirmed both relationships.
- At the initial state check, both upstream devices had zero registry entities;
  the HA browser itself reported “This device has no entities” for Basement.
  Commissioning does not qualify a functioning door-state feed or physical alert.
- At 23:49:05 UTC on 2026-09-06, one authorized normal targeted ZHA config-entry
  reload had recovered twelve registry entities and eight current-state entries
  (previously zero). The entry was loaded before/after, HTTP 200, no restart
  required. No re-pairing, reset, deletion, firmware, configuration/source edit,
  or request retry occurred. This is operator maintenance through the existing
  private connection, not proof of an ANIMA agent-selected repair or a physical
  trigger. The initial registration fault's root cause remains unproven.
- A real owner UI → external Codex Luna helper → ANIMA read → browser response
  passed for request `b9c5b3ec-0fef-56c7-9b33-9bd40a454f6a`.
  Provider-start was recorded and the durable lifecycle reached COMPLETED.
  This is not resident SENTRY voice or persistent-persona evidence.
- A private workstation client and Unix SSH tunnel were provisioned without
  moving HA/DB/OPA or Codex login credentials. User services keep the helper
  separate from protected SENTRY. Worker failure is not automatically restarted.

## Negative results retained

- `086b964a-a023-56df-bf8a-736ce45e6a04`: Core completed the read, but the UI
  originally polled the journal event ID instead of the intelligence request ID.
  This was corrected and regression-tested before the subsequent browser pass.
- First device commission: KeyError from the generic power-control handler.
  The trusted household invocation-context adapter was missing; the correction
  passed real UI commissioning and focused legacy/current-registry tests.
- `b89d05af-d8ad-57bb-aad4-d2d83fe8381d`: conditional room creation ended
  UNKNOWN_RESULT/ANIMA_TURN_UNAVAILABLE. No Bedroom room existed on readback.
  This request was not replayed.
- `ce878704-0d24-5014-8e8d-9cc9b67c811c`: a new checked request ended
  UNKNOWN_RESULT at TOOL_INVOKE/AnimaHouseholdError. Neither failed request is
  counted as successful agent-driven configuration.
- A ten-second aggregate snapshot timeout hid successful device changes behind
  old counts. Successful mutation and failed refresh were displayed separately;
  retry recovered. A backend read-only profile did not support a single slow
  Home query as the cause. The UI's all-or-nothing refresh was a confirmed
  contributor to stale presentation, not proof of the transport-delay cause.
- The published Cnn frontend failed one fresh isolated Core browser scenario:
  calendar save returned HTTP 200/SUCCEEDED with the saved version, but the edit
  form waited on unrelated task reads. Eight other H4 desktop scenarios and
  both H5V scenarios passed. The correction projects only Core's returned saved
  event/version after SUCCEEDED, then refetches in the background. A generation
  guard rejects older list overwrites; refresh failure remains explicit. Fresh
  H4 9/9, H5V 2/2, graphical desktop 24/24, static 5/5, TypeScript and Vite passed
  with unchanged calendar timeout assertions. No optimistic success was added.
- After ZHA recovered its entities, inventory refresh correctly discovered them
  but the already-commissioned devices still had zero EXPOSES/Truth bindings.
  The existing commission path now attributes genuine pre-binding observations
  to canonical keys through causally linked journal events. It preserves original
  age, uncertainty, source and immutable original records, emits no physical
  event/Attention callback, and does not invent absent observations. A disposable
  PostgreSQL regression covers six late entities, repeated commission, journal
  rebuild, stale/unknown status and a later genuine observation. The disabled
  helper baseline reproduced the missing canonical observations.
- The owner browser subsequently timed out on all fifteen snapshot routes on
  port 18090, despite fast server probes. Restarting the transport did not cure
  it. The same browser/session against the same backend through a temporary
  port loaded immediately. Origin-shared connection pressure is under focused
  investigation; this is not evidence of an authentication failure or a cure.

## Validation evidence levels

- Deterministic backend: full pytest, strict mypy, Ruff and package build.
- Deterministic worker: subprocess isolation, exact catalogue schemas,
  sequential planning budgets, restricted-content stop, safe diagnostics and
  no automatic ambiguous replay. JUnit is published in the CI artifact.
- Browser fixtures: all fifteen redesigned sections, responsive layout,
  settings application and semantic outcomes; synthetic screenshots only.
- PostgreSQL/OPA/Core browser harness: conversation, tasks, calendar,
  confirmation/rejection, restricted reload and existing accepted scenarios.
- Real owner deployment: OAuth connection, inventory, room creation,
  SenseGuard commissioning, and the real Codex read/browser response above.

Exact hosted results supersede local counts at publication. A fixture or
isolated-provider test is never promoted to physical household evidence.

## Boundaries

No arbitrary raw HA administration, model shell/code editing, firmware updates,
resident voice, persistent SENTRY conversation memory, fabricated telemetry,
notification receipt, or whole-house automation completion is claimed.
Existing history and the protected SENTRY worktree are preserved. Private owner
screenshots, raw provider payloads and credentials are excluded from Git and CI.

## 2026-09-07 UTC vendor/SENTRY continuation

Current local deployment and full validation/negative evidence are recorded in
`docs/VENDOR-SENTRY-CONTINUATION-026A.md`. 759 backend tests passed/7 optional
skipped; isolated PostgreSQL vendor target45 passed; browser36 passed with
explicit synthetic fixtures. Final image is healthy, HA ONLINE, receiver
disabled without producer configuration. Official Android boot passed, but
official apps, notification capture and vendor events did not run. SENTRY's
event lease tests do not qualify an automatic wake/TTS connection. No new hosted
CI, publication or full-integration acceptance is claimed by this checkpoint.

## 2026-09-09 UTC push-first mandatory-alert latency closure

- Implemented an authenticated long wait backed by PostgreSQL `LISTEN/NOTIFY`.
  Enqueue sends an empty wake only after a new durable request row exists;
  subscribe-then-query prevents the listener race. Empty waits do not claim,
  call provider-start or invoke a model.
- Request ordering uses the frozen integer Attention priority before creation
  order. A real disposable PostgreSQL test proved priority 100 is returned
  before priority 10 and a waiting authenticated Unix HTTP request woke in
  under three seconds after enqueue.
- Core creates an actor-free canonical factual announcement only for fresh,
  qualified events whose owner disposition is `ALWAYS_NOTIFY`. It uses the
  canonical Graph name and a bounded event-kind phrase; untrusted notification
  prose remains excluded.
- SENTRY begins warm TTS after the durable provider-start fence while its
  low-effort contextual turn runs in parallel. Health, sparse context and the
  frozen request catalogue are mode-0600 preloads, eliminating Core discovery
  round trips without widening the tool set.
- `scripts/validate.sh`: PASSED, 1153 tests passed/76 optional skipped, strict
  mypy and Ruff passed, OPA 9/9. Real PostgreSQL autowake target: PASSED, 31.
  Docker UI/Core build and local deployment health: PASSED. Physical event to
  audible playback objective: NOT RUN on this exact source.

## 2026-09-08 UTC owner page guidance alignment

- Replaced the remaining slogan-style introductions on Automations, SENTRY,
  Alerts, Tasks & Calendar, Activity, Users, Connections, Backups, Preferences
  and Settings with exact descriptions of the implemented owner workflow and
  its authority, persistence and evidence boundaries.
- Notification-only connection resources are excluded from the On/Off
  automation trigger picker. The existing automation runtime remains bounded to
  normalized On/Off observations and one verified semantic power action.
- Supporting controls now explicitly distinguish durable task lifecycle,
  optimistic calendar versioning, bounded recent Activity, route-priority
  filtering, integration management, capability availability, household
  preferences and presentation-only interface settings.
- PASSED locally: frontend source contracts 11/11; TypeScript and production
  Vite build; desktop Playwright 33/33; focused automation/UI Core pytest 40/40;
  Ruff; `git diff --check`; live container health and bundle-content inspection.
- Deployed image:
  `sha256:3e7d0730a564120fd8f4b9ce6bfb7acad86f0e84a20942b2f3d96671b7b5b3af`.
  No commit, hosted CI or new backend capability is claimed.

## 2026-09-08 UTC owner Routines guidance and workflow alignment

- Routines now explains its actual durable model: existing household member,
  days, local time window, timezone, optional room/zone, descriptive context,
  enable/disable and versioned edits.
- The page explicitly states that routine records may inform SENTRY alongside
  presence, preferences, memory and events but are not proof of presence,
  authentication, an automation or a scheduled action.
- The duplicate `Add household member` browser form was removed. A bounded
  `Manage household users` action opens Users, the owner surface for identity,
  SENTRY access, Wi-Fi hints and face profiles. The backend compatibility tool
  was not removed.
- Household presence now explains assignment of qualified HA phone-geofence and
  supported Wi-Fi signals, freshness/conflict handling and its non-authentication
  boundary.
- PASSED locally: frontend source contracts 11/11; TypeScript and production
  Vite build; dedicated PostgreSQL/OPA Routines Playwright 42/42 across
  desktop/tablet/phone; focused Routines/UI Core pytest 100 passed with 3
  optional skips; Ruff; `git diff --check`; live health and deployed-bundle
  phrase/absence inspection.
- The first dedicated browser-server start was `FAILED` before test execution
  because the disposable `anima_family_routines_test` database did not exist.
  The exact disposable database was created, after which the full 42-scenario
  matrix passed. The failed launch is not counted as a pass.
- Deployed image:
  `sha256:3cb54a638824dcf101571c5870404fffb13f3374011dbc6cfdbc528db0aa3be8`.
  No commit, hosted CI or authenticated owner-browser screenshot is claimed.

## 2026-09-08 — SENTRY owner-operations chat and precise event rules

- Added the targeted `anima.household-learning.set_device_notification` typed
  operation. It updates one canonical device/event rule using the current
  optimistic config version and preserves unrelated household learning and
  notification settings. Supported event selectors are bounded to any,
  unlocked, locked, opened, closed, motion and doorbell.
- Initiative delivery now applies a device rule only when its event selector
  matches the qualified source event. A nonmatching signal falls back to the
  household default instead of accidentally inheriting the device rule.
- The Devices notification UI exposes the same event scope, so an owner can see
  and edit a chat-created `UNLOCKED -> ALWAYS` rule.
- The actual `gpt-5.6-luna` bounded planner was run without dispatch. Round one
  chose canonical resource discovery plus current initiative status; supplied
  synthetic read results caused round two to choose exactly
  `set_device_notification(resource_id, ALWAYS, UNLOCKED, expected_version)`.
- The persistent household worker now backs off and continues after transient
  Core/client failures. The user service uses `Restart=on-failure`; this is safe
  because provider-start is durably fenced before model execution and a
  replacement worker cannot reclaim ambiguous started work.
- Live deployment: image
  `sha256:79580a2bf635a84095d1f00d4a04394b81ada18862f2feda4d1a48b4d90ef66b`
  is healthy on port 18090. The worker encountered two transient startup gaps,
  recovered in-process, completed the remaining queued direct-owner work, and
  is active with no pending direct UI request.
- PASSED: full Python pytest; full strict mypy (141 source files); full Ruff
  lint; SENTRY worker tests (48); frontend source tests (11), TypeScript, Vite
  production build; Docker image build; `git diff --check`.
- The aggregate `anima-validate` wrapper is FAILED only at its first formatting
  gate because three unrelated pre-existing dirty owner-worktree files are not
  Ruff-formatted. This slice's seven changed Python files pass format-check;
  later wrapper stages were run separately and passed. The unrelated files were
  preserved rather than mechanically rewriting concurrent owner work.
- NOT RUN: hosted CI, authenticated browser submission from the owner's existing
  session, and a physical door-unlock announcement. No unrestricted raw host or
  credential access is claimed or added.

## 2026-09-08 — live alert-setting failure and bounded classification fix

- The first authenticated owner request failed at `TOOL_INVOKE` with HTTP 409
  `TRUSTED_ACTION_SPEC_UNAVAILABLE`. Request
  `1903ebff-d2de-5c97-b8bc-9dc948be8486` is durably `UNKNOWN_RESULT` because the
  SENTRY provider turn had begun, but the failure occurred before
  `PluginManager` invoked the settings tool. No alert-setting write or physical
  side effect occurred.
- Root cause: the new non-read-only operation was absent from Core's exact
  trusted internal-source allowlist and therefore defaulted to
  `COORDINATED_CONSEQUENTIAL`; Phase 9 correctly refused it without an action
  safety specification.
- Corrected only the exact pair
  `anima.household-learning.set_device_notification` plus
  `builtin:anima_ha.household_learning` to `POLICY_GATED_INTERNAL`. A forged or
  external same-name operation remains consequential and fails closed.
- The terminal failed request was not replayed. Ten unrelated historical
  `AUTONOMOUS_ATTENTION` requests remain pending; no direct-owner request is
  pending. A new authenticated owner request is required to establish the rule.
- PASSED: focused household-learning/plugin/SENTRY boundary suite; strict mypy
  on the corrected surface; `git diff --check`; Docker image build; live
  `/healthz`; container health; and active worker after Core restart.
- Deployed image:
  `sha256:afe653c8ee1032c650876030eff35a95fac79c48457c342040287086aa6d1c6a`.
  NOT RUN: hosted CI, successful authenticated retry, door-lock event, and TTS
  announcement.
