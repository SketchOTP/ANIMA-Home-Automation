# Family routines

Open ANIMA on the Linux PC at `http://localhost:18090/`, refresh the page once,
then choose **Routines**. No Home Assistant configuration screen is needed.

## Add a routine

1. If the person is missing, choose **Manage household users**, add or update
   them on **Users**, then return to **Routines**. Identity, SENTRY access,
   Wi-Fi hints and face profiles belong on Users rather than being duplicated
   in the routine editor.
2. Select the member and enter a short routine label.
3. Choose individual days or Weekdays, Weekends, or Every day. Days identify the
   local start day. Set start/end times and check the time zone.
4. Optionally choose a room/zone and enter a description. Choose **Save routine**.

An end time earlier than the start crosses midnight. Equal start/end times are
not accepted. No family schedules or names are prefilled by the application.

## Manage saved routines

- Filter by member; **Load more routines** uses the existing bounded cursor.
- **Edit** changes a saved expectation. Previous versions remain in history.
- **Disable** keeps an expectation saved but inactive; **Enable** reactivates it.
- **Remove** asks for confirmation and retracts the expectation from the active
  list. It does not permanently delete its history.
- If a change fails or has an uncertain result, the list refreshes and the draft
  remains for review. There is no automatic mutation retry. Edit the current
  version or check the list before discarding a draft and trying again.

## What these records mean

A routine is an **owner-declared expectation**, not a device observation, proof
of presence, authentication, scheduled action or automation. Existing Core tools
and SENTRY context can read these records alongside current presence,
preferences, memory and events; current evidence remains authoritative. SENTRY
remains the intelligence and voice interface, while these graphical forms
configure durable household context.

## Completion evidence — 026A routines, 2026-09-07 UTC

**COMPLETE for the bounded owner Routines workflow; full product remains
incomplete.** Retrieval confidence: ADEQUATE. Tapo/Wansview development is paused
by the owner; their partial code and stopped Android installation are preserved.

Reused Graph/Memory, native Tool Gateway, current policy and FastAPI/React. Added
the exact native `anima.family-routines.add_member` tool (manifest 1.1.0), routed
through the existing owner/CSRF/Core path. It accepts only a name and cannot
assign roles, authentication, or presence. Changed the synchronous database API
handlers to FastAPI threadpool handlers so routine reads do not occupy the ASGI
event loop. No new database, migration, provider, policy rule, or dependency.

Changed areas: `family_routines.py`, `family_routines_api.py`, native registration
in `plugins.py`, routing in `ui_runtime.py`, `FamilyRoutines.tsx`/CSS, backend/API
tests, the isolated browser server and routine browser scenarios.

### Validation

- Full Python: **784 passed, 8 opt-in environment tests skipped**, zero failures
  (792 collected). Routine opt-ins were separately run rather than treated as
  evidence through their default skips.
- Focused routine/API suite with actual isolated PostgreSQL and unchanged OPA:
  **67 passed**. Includes persistence/versioning, household/CSRF boundaries, plain
  member creation, real OPA denial/zero mutation with audit, and threadpool check.
- Browser: **126 passed** across desktop/tablet/phone. Of these, **42** cover
  routines: six real PostgreSQL/OPA browser executions (two workflows at three
  viewports), plus 36 explicitly labeled UI fixture/error/session checks. The
  other 84 are adjacent existing graphical-console regressions. Real workflows:
  create/reload/edit/disable/enable/retract; add member/reload member options.
- TypeScript, five frontend checks, Vite build, Ruff check/format, strict mypy
  (104 files), unchanged OPA9/9, catalogue/prebound tests62, diff checks and existing
  tracked/new-source credential-pattern scans: **PASSED**.
- Docker UI build and Python wheel construction/install: **PASSED**. No separate
  sdist build or new hosted CI is claimed. Local bundled runtime lacks npm; direct
  Node TypeScript/Vite/test entrypoints passed, and Docker's npm build also passed.
- Synthetic desktop/phone screenshots visually inspected. Browser helper CLI
  was unavailable; the existing Playwright suite supplied actual rendered checks.
  Its isolated fixture does not connect HA; setup-unavailable in those screenshots
  is not the production HA state.

### Deployed state

Linux-PC `anima-pc-ui-1` image:
`sha256:574e89f795ee75b49ba162fae77504fa094e1a49ac1600ff0105a07404f34908`.
Health HTTP200/healthy, HA setup ONLINE, routine endpoint unauthenticated401.
Served UI `index-BC_rzd1p.js`, SHA256
`cabf59bcb1e7c5369aba86ded35c683b2fadd257c546d00872535e5d2da34476`.
Installed routine/API/Core/plugin module digests match tested local source.
No claimed/delivered/running provider request existed before the bounded UI/Core
restart. PostgreSQL, HA, OPA and SENTRY were not restarted. No owner member or
routine was added by tests; only isolated synthetic households were mutated.

Local JUnit evidence (not hosted artifacts):

- `/tmp/anima-routines-finish-full.xml`, SHA256
  `7be189f1d5f5b7af68bc55e8d23e0410c9e103f2193bb4aaf9c8f51882d02104`.
- `/tmp/anima-routines-finish-backend.xml`, SHA256
  `c4b4508451217e697a3c99782b17dc8c0cf3184f41761aaf06fcb002d837def0`.
- `/tmp/anima-routines-finish-browser/`: synthetic screenshot evidence.

Evidence level: E3/E4 for isolated owner workflows and regressions; E5 only for
observed deployed health/asset/source compatibility. Actual owner-authenticated
routine creation and live SENTRY voice authoring are not claimed by these tests.

Authority skill preserved existing work and drove separated live/fixture
evidence. External discovery: NONE required for reuse of qualified architecture.
The initial assumption that member options alone were sufficient was disproved:
the owner household had only one person, so the simple member-creation workflow
was necessary. Async route declarations also hid synchronous database work.

Git base remains `435815855ffda8ff917406daeb063ca498b7b9c7`; dirty local work is
preserved. No new commit, push, hosted CI, artifact, phase acceptance, or
whole-goal completion is claimed. Recommend owner use/review of Routines next;
do not resume paused vendors automatically.

ANIMA, ANIMA–SENTRY integration and SENTRY Notion authority pages were updated
and read back after deployment with the vendor pause, owner workflow, exact
image and qualified local counts. Local CURRENT/OUTCOMES/REPO_MAP/LEARNINGS and
026A evidence/handoff agree. No strategic phase or full-product acceptance.
