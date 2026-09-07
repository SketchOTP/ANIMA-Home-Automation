# CODEX RESULT — 026A vendor and SENTRY continuation

## Verdict

**PARTIAL — PC-side implementation/preparation; live vendor and automatic voice
delivery incomplete.** No prototype-complete or unrestricted-control claim.

## Retrieval confidence and discovered state

ADEQUATE for current local code/runtime and supported boundaries; UNCERTAIN for
the owner's unprovisioned vendor apps and device event formats. Active native
PC repositories are `/home/sketch/Projects/ANIMA Home Automation` and
`/home/sketch/Projects/SENTRY`. Existing dirty work was retained. The prior shared
laptop deployment is not active. Current HA inspection finds no lock entity or
Tapo/Wansview notification source; this does not inspect the owner's phone apps.

## Work performed / changed areas

- `tapo_events.py`: bounded SmartThings/HA lock-state normalization, canonical
  binding and timestamp/attribution honesty. No lock/unlock execution or raw API.
- `android_notifications.py`: distinct ANIMA-owned typed report validation and
  labeled test-fixture entry point. Neither is a raw Wansview notification parser.
- `vendor_event_ingress.py`, `ui_api.py`: optional Core-owned relay receiver,
  separate private relay authentication, household/Graph checks, bounded/minimized
  Journal data and exact-event Attention handoff. Disabled without qualified
  source registration. Browser sessions are not relay credentials.
- `VendorConnectionsPanel.tsx/.css`, `main.tsx`: actual readiness cards under
  Integrations, bounded safe diagnostics, refresh and responsive controls.
- SENTRY `tools/sentry_anima_events.py`: inert one-attempt event lease primitive.
  It does not claim events, invoke Codex, consume the voice queue or speak.
- PC packages/runtime: official Waydroid/Weston/ADB, verified Android GAPPS images,
  headless boot, privacy correction and stopped-by-default preparation.

## Owner-usable result and acceptance boundary

The owner can inspect vendor setup gaps in ANIMA rather than seeing a fabricated
connected state. Existing local household management remains available. The new
receiver is implementation, not a producer connection. No actual lock or camera
alert was received in this increment; no synthetic alert was injected into the
owner household and no new model or TTS call was made for these vendors.

| Item | Disposition |
| --- | --- |
| Canonical typed lock observation | Target-tested; actual HA source absent |
| ANIMA-owned relay report protocol | Target-tested; producer not commissioned |
| Wansview raw notification capture/parser | Not implemented/qualified |
| Android PC boot | Observed; now stopped pending app setup |
| Official apps/accounts | Not installed or signed in on PC |
| Actual vendor event / fingerprint identity | Not observed |
| Automatic Attention → resident SENTRY → TTS | Not connected |
| Existing SENTRY direct household read | Prior separately recorded live evidence |
| Full SENTRY household write authority | Not claimed |

## Final local validation and deployment

- Full Python: **759 passed, 7 optional environment tests skipped**, zero failures
  (766 collected). The isolated vendor PostgreSQL target was separately executed,
  not represented by its opt-in skip in the default suite.
- Real isolated PostgreSQL/HTTP vendor target: **45 passed**; combined targeted
  set **257 passed, 2 other optional PostgreSQL seams skipped**. Real typed report
  append, duplicate replay, conflict rejection, unqualified rejection and original
  persisted non-wake ceiling pass. Truth observation/state and intelligence record
  counts remain 0/0/0 for the non-waking target. This uses structured test reports,
  not real vendor notifications. Disposable PostgreSQL containers were removed.
- Strict mypy: **104 source/test files passed**; Ruff check/format passed.
- OPA: **9/9 passed**. Initial `/policy` diagnostic path was incorrect; the actual
  mounted `/policies` path passed unchanged policy. No policy edit occurred.
- Frontend: TypeScript, five unit/static tests, Vite build and **36/36** focused
  browser checks passed across desktop/tablet/phone using labeled fixtures.
  The final protocol split changed the default setup gate to PRODUCER_UNQUALIFIED;
  the old contract assertion failed, was updated to this actual distinction, and
  the complete backend/browser suites passed again. No live receipt was inferred.
- SENTRY: worker's **178 focused tests** passed, including the inert primitive's
  11 tests; lead independently reran those 11 successfully. Runtime wake/TTS was
  not executed. No new SENTRY runtime configuration or service restart occurred.
- Python wheel construction/install in Docker and final UI image build passed.
  A separate local `python -m build` command was unavailable (module not installed);
  no standalone sdist or hosted package-build claim is made.
- Existing tracked repository safety scan plus new-source credential-pattern
  checks and `git diff --check` passed. Dirty source is preserved; this is not a
  clean-publication claim or a scan of private runtime credentials.

The final image `sha256:a334cdb892ea7691da6250a99f5249d23d6a2eb2df318c7e956ae010a10179ba`
is deployed as `anima-pc-ui-1` on localhost18090. Health is healthy/HTTP200,
HA setup reports ONLINE, served asset is `index-DyRGUZT7.js`. Status and relay
endpoints return401 without their required credentials. Production relay has
zero configured sources and enabled=false. Installed module digests match the
tested PC files. No active claimed/delivered/running provider turn existed before
restart; database/HA/SENTRY services were not restarted. Android remains stopped.

Local evidence (not hosted artifacts):

- `/tmp/anima-vendor-026a-final-tests.xml`, SHA256
  `2ff0b16cbd52418a4a8311d63a131b8603d42db1da896bb3cd4013effe3a3ba6`.
- `/tmp/anima-vendor-ingress-evidence-AlPU1p/protocol-target.xml`, SHA256
  `437cce48e60550ac3adc0a777a6365eeb7160f705c5565c7ead1e2a927f585ef`.
- `/tmp/anima-vendor-ingress-evidence-AlPU1p/protocol-combined.xml`, SHA256
  `0992f9bd771bd6721430dc8a6d7bbb1b352fe7d60627a4ac9e98e43aa770e2e2`.
- `/tmp/anima-vendor-panel-results/`: synthetic browser artifacts.

Evidence level: E3/E4 for deterministic and isolated-store contracts, E5 only
for observed PC boot and deployed default status. **Not E5 vendor delivery.**

## External discovery and assumptions

External-discovery skill led to reusing documented HA state fields and Waydroid's
installed notification forwarding rather than inventing private vendor APIs.
The latter lacks Android post time/channel/group metadata; receipt time must not
be relabeled as camera event time. The stock first Android startup broadened
device permissions; it was stopped and corrected before the successful bounded
boot. Exact negative evidence and controls are in
[the runtime runbook](ANDROID-NOTIFICATION-RUNTIME-026A.md).

[Tapo qualification](TAPO-DL110-INTEGRATION-QUALIFICATION.md) records the current
SmartThings cost/OAuth approval caveat and missing named-unlocker proof.
[Wansview qualification](WANSVIEW-MOTION-INTEGRATION-QUALIFICATION.md) distinguishes
typed protocol, missing private-bus collector, unknown real text format and
unqualified unattended delivery. No paid service or account agreement accepted.

## Remaining work / precise resource gate

The owner must confirm/add devices in the official apps and perform any necessary
vendor/Google sign-in directly. No password/setup-code transfer is requested.
After source access exists: qualify a real minimally redacted notification,
finish the private-bus package-filtered collector/parser, commission the relay,
then verify real alert ingestion and loss/reconnect behavior. Tapo source linking
needs explicit approval of the actual partner entitlement/OAuth scope if used.

SENTRY still needs the existing runtime's exact-event claim, concurrency lock,
qualified per-event context/tool restrictions, provider-start/lease/cancellation,
and separate response versus existing-TTS delivery hooks. Do not feed restricted
event data into the persistent owner conversation merely to produce a demo.
There is no second assistant daemon or fabricated voice delivery in this work.

## GitHub / authority state

ANIMA base HEAD `435815855ffda8ff917406daeb063ca498b7b9c7`; SENTRY base HEAD
`5441cf35f9a08aaa8f1d2926c17672b4f105d0f7`. This is an uncommitted local operational
increment. Prior CI `34067802116` applies only to the older ANIMA head. No new
commit, push, hosted CI, clean-tree claim or published artifact is implied.
Phase 14 acceptance remains unchanged; no historical Phase 15 cycle was started.

## Recommendation

Project records updated: `.agent/CURRENT.md`, `OUTCOMES.md`, `EXTERNAL.md`,
active026A evidence/handoff, and SENTRY's active-task event continuation note.
ANIMA, integration and SENTRY Notion authority pages received this partial
checkpoint and were read back successfully after deployment. Existing history
was preserved; no stale completion claim was promoted into current status.

Retain the bounded implementation and complete app/source setup before making
live vendor claims. Resume the existing SENTRY runtime connection as actual
product work, not another standalone lease framework. Authority-skill recording
keeps implementation, isolated tests, local deployment and live delivery separate.
