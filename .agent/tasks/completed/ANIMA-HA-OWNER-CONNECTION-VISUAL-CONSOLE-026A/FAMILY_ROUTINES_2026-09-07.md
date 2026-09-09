# CODEX RESULT — 026A family routines and voice-only dashboard

## Verdict / retrieval

COMPLETE for the bounded source implementation; NOT DEPLOYED. Retrieval ADEQUATE.
This does not accept a project phase or claim operational SENTRY voice completion.

## Technical state and work performed

The existing governed Memory service supports explicit facts and immutable corrections.
Family routines now use that service rather than the inferred routine-model table.
The owner-facing Routines section supports canonical member selection, a label,
description, IANA timezone, distinct weekdays (Monday 0 through Sunday 6), local
start/end times, optional canonical room/zone, save/reload/edit/disable, and version
and provenance inspection. Overnight windows are supported; equal endpoints are
invalid. These are expectations, not scheduled jobs, physical observations, or
automatic actions. No real schedule or member was seeded.

Mutations travel through session authentication, Origin/CSRF, the existing Core
policy/plugin gateway, and Memory. Household scope and provenance come from trusted
context. The native plugin additionally requires a direct-user request from an
active canonical household owner; model-inferred/autonomous authoring fails closed.
Updates/disable/retract require the current immutable Memory ID. Corrections keep
history; listing uses scoped metadata SQL and UUID keyset pagination after filtering,
not the existing generic 100-result/top-k cutoff. No new table, migration, or enum.

The dashboard Anima section now provides a SENTRY voice-only status/handoff panel.
Shortcuts only display suggestions to speak; they never submit text. The composer
and frontend conversational POST/poll code are removed. Backend conversation
ingress remains intact for internal integration; read-only household reports,
activity, and all configuration forms remain. No browser microphone or typed chat
interface was introduced. Reported voice status is displayed without claiming the
desktop is listening.

## Files / exact integration contract

- New `src/anima_ha/family_routines.py`: `FamilyRoutinesNativePlugin(memory_service,
  graph)`, `FAMILY_ROUTINES_MANIFEST`, `family_routines_page`,
  `family_routine_options`, `FamilyRoutineError`.
- New `src/anima_ha/family_routines_api.py`: `install_family_routines_api(app,
  service, current_identity=..., current_session=..., require_mutation=...)`.
- New `ui/src/FamilyRoutines.tsx`: `FamilyRoutines({mutate, onAuthFailure})`.
  Self-loading; no change to the initial shared App snapshot shape. Reuses existing
  card/dashboard/form/checkbox/button/list classes; no framework or CSS replacement.
- Shared narrow hooks: `ui_runtime.py` native registration and gateway method;
  `ui_api.py` import/installer; `plugins.py` four exact native mutation-source IDs;
  `main.tsx` Routines mount/navigation and voice-only replacement.
- Tesla's KnowledgePanel remains mounted in Preferences. His requested
  `KnowledgeConfig.from_environment()` hook is wired; unused Path import removed.
  Shared edits followed his release. Requested multi_agent_v1 send_input was not
  exposed in this session; coordination updates were supplied to the lead, and
  Tesla's incoming messages confirmed the hook in source.
- Tests: `test_family_routines.py`, `test_family_routines_api.py`,
  `serve_family_routines.py`, `family-routines.spec.ts`, dedicated
  `playwright.family-routines.config.ts`. Default Playwright config excludes the
  specialized family-routines/knowledge fixtures. Existing redesign/UI tests now
  assert voice-only behavior. H5V setup uses programmatic internal test ingress,
  not a removed typed product UI.
- Frozen HA adapter/alert/MCP work was not edited by this increment.

HTTP: GET `/api/v1/family-routines?limit=50&cursor=...&person_id=...` returns
`items,next_cursor,members,places,can_edit,status`. POST
`/api/v1/family-routines/{create|update|disable|retract}` takes `{payload: ...}`.
Tool IDs: `anima.family-routines.{list_routines,create_routine,update_routine,
disable_routine,retract_routine}`. Mutation result is `{status: SUCCEEDED,routine}`
inside the existing Core outcome envelope. Reads are paginated; mutations require
the current routine_id and complete replacement fields for update. Projection
includes immutable routine_id/version, person/place names and IDs, label, days,
start/end, timezone, notes, enabled, provenance, OWNER_DECLARED_EXPECTATION, and
authority NONE. SENTRY receives semantic tools through its existing request-bound
catalogue; authenticated direct voice requests remain required for mutations.

## Validation / acceptance

- PASSED: 41 focused routine/API/native/SENTRY-boundary tests, including real
  PostgreSQL creation, fresh service reload, immutable edit/disable history,
  retraction, stale-version rejection, household/member isolation, strict fields,
  explicit provenance, scoped pagination beyond 100, and untouched inferred models.
- PASSED: 101 adjacent Memory/Graph/plugins/policy/preferences/UI/runtime/SENTRY
  regressions; one unrelated optional durable fixture skipped (NOT RUN).
- FAILED: full combined suite: 580 passed, 4 skipped, 1 failure. Existing
  `tests/test_household_spaces.py:120` expects five manifest tools while concurrent
  household-spaces source now also exports `list_resources`. Not changed here.
- PASSED: Ruff checks, focused formatting, mypy seven source/test files,
  TypeScript, Vite production build, `git diff --check`.
- PASSED: six real browser→API→Core→PostgreSQL routine checks across Chromium
  desktop/tablet/phone viewports: save/reload/edit/disable/version/provenance,
  no horizontal overflow, voice-only panel, session-expiry clearing, no page errors.
  Synthetic household only; policy evaluator is an explicit ALLOW fixture, while
  authentication, CSRF, native checks and durable Memory are real. Separate tests
  prove policy DENY prevents writes. This is not live owner or real desktop proof.
- Initial browser failures exposed an ambiguous test locator and textarea label;
  both corrected before the six passing checks. The first wider matrix had 83
  passes and one root-page 404 during shared asset rebuild; isolated recheck passed
  three times. Final wider matrix: PASSED, all 84 checks across desktop/tablet/phone
  on the completed bundle. Combined browser evidence: 90 passing checks.
- NOT RUN: production deployment, live owner routines, real SENTRY voice tool
  authoring, full H4/H5V integration fixtures, Safari/mobile-device hardware.

Evidence level: E4_REGRESSION_PROTECTED for this bounded implementation.
React/accessibility review and browser-verification skills informed stable labeling
and interaction checks. The unavailable agent-browser CLI was replaced with the
repository's Playwright browser runner. No external discovery was triggered: this
reuses existing internal mechanisms, not a new subsystem.

## Visible evidence

`ui/test-results-family-routines/family-routines-owner-crea-8dbe3-a-genuine-persisted-routine-{desktop,tablet,phone}/`
contains `routine-disabled-persisted.png` and `voice-only.png`. These are synthetic
test scenes, not owner schedules. Phone and desktop screenshots were visually
inspected, not just captured.

## Deployment steps — lead only, not executed

1. Resolve/reconcile the concurrent household-spaces manifest regression and
   finish Tesla's separate Memory matrix before accepting the combined build.
2. Include the new Python modules plus shared hooks and the new TSX component in
   the existing UI image. Preserve the lead's exact private Compose flags/env and
   mounts; use its existing `build ui` then `up -d --no-deps ui` workflow.
   Dockerfile.ui builds both backend source and frontend assets. No new migration,
   owner data seed, HA change, secret rotation, or vault access is required.
3. Recreating that ANIMA UI/Core process registers `anima.family-routines`.
   Existing SENTRY request catalogues are immutable: use a new properly bound
   request for the added tools; never rewrite an old catalogue or restart a helper.
4. Verify health/served assets and authenticated GET family-routines. As the
   owner, choose Routines, select a real canonical member, and save only an actual
   owner-provided schedule. Reload/edit/disable should return new versions. Verify
   Anima has no typed composer and Preferences still shows Tesla's Memory panel.

## Risks, assumptions, deviations, and records

No automatic scheduler or inferred-presence authority is implied by a routine.
Core may deny a mutation when policy/authentication requires it; the UI must not
manufacture success. New source is frozen for lead deployment. Shared dirty work
is preserved. No production data, account, device, configuration, or private vault
was mutated. Temporary test resources contained synthetic data only. The loopback
fixture server and `anima-family-routines-test-20260907` container were stopped
after verification; the ephemeral synthetic database was removed. No owner
database was used or changed. Screenshots remain in the test-result paths above.

Assumptions confirmed: existing Memory corrections and exact native policy boundary
support this workflow. Disproven: the dashboard typed composer satisfied voice-only
scope. Deviations: none to product scope; unavailable requested agent messaging and
browser CLI required the stated coordination/verification fallbacks.

GitHub: branch main; no commit, push, PR, or deployment by this worker. Notion NOT
UPDATED (lead publication). Current/outcome records point here; lead owns combined
deployment evidence and acceptance. Recommendation: reconcile the unrelated combined
test failure, deploy the cohesive image, then verify owner-visible behavior without
inventing family data or claiming desktop operational completion from fixtures.
