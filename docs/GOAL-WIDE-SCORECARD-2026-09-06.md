# Goal-wide usability scorecard — 2026-09-06

This scorecard is a product-planning snapshot, not an acceptance claim. It
compares the permanent completion goal with the current ANIMA repository and
the accepted Phase 0–14 evidence.

| Objective | Current disposition | Evidence boundary / remaining gap |
| --- | --- | --- |
| MO-01 resilience and recovery | ACCEPTED | Phase 14 is accepted; native Pi 5 remains an external hardware gate. |
| MO-02 management plane | PARTIAL | Bounded device, integration, alert, notification, scene, automation, task, calendar, preference, backup, and room workflows exist. Active restore and unsupported advanced HA administration remain outside the prototype surface. |
| MO-03 versioned API | PARTIAL | Current UI workflows have authenticated API routes; a formal 100% support-matrix audit remains open. |
| MO-04 local UI | PARTIAL | Current bounded lifecycle is owner-usable; restore remains maintenance-only and final integrated SENTRY operation is not yet the owner-facing completion marker. |
| MO-05 SENTRY MCP | ACCEPTED | Phase 13 runtime-compatible household boundary is accepted; no raw authority bypass exists. |
| MO-06 SENTRY integration | PLATFORM ACCEPTED | ANIMA is SENTRY-ready, but final owner-facing text/voice operation remains later integrated-product work. |
| MO-07 onboarding without HA frontend | IMPLEMENTED (BOUNDED) | ZHA onboarding, device discovery, commissioning, lifecycle, and recovery are available through ANIMA; unsupported integration classes fail explicitly. |
| MO-08 settings ownership | IMPLEMENTED (BOUNDED) | Presentation, preferences, alert policy, notification route, integration, scene, automation, task, calendar, and room settings are ANIMA-owned where supported. |
| MO-09 external-by-intent | IMPLEMENTED (BOUNDED) | Weather, web, places, recipes, shopping, calendar/reminders, and notification paths are present with explicit trust/degradation limits; cart/checkout is not claimed. |
| MO-10 authority and exact results | ACCEPTED | Identity, policy, credentials, confirmation, verification, provenance, and unknown-result boundaries are retained. |
| MO-11 engineering and deployment | IMPLEMENTED (SUPPORTED PATH) | CI covers x86-64/ARM64 software, containers, migrations, health, and backup evidence; native Pi execution remains gated. |
| MO-12 final integrated scenarios | BUILD LATER | The complete A–O SENTRY-operated scenario deck is intentionally not started. |
| MO-13 SENTRY voice and text | BUILD LATER | A bounded text-operation increment is the next product candidate; ANIMA will not add a competing voice stack. |
| MO-14 zero HA frontend dependency | PARTIAL | Supported bounded workflows are exposed through ANIMA; a final published support-matrix audit remains to be completed. |
| MO-15 project complete | OPEN | Requires MO-02–MO-14 simultaneously plus final exact-head evidence and owner acceptance. |

## Next product decision

The room/zone lifecycle increment closes the most immediate household-map
management gap. The largest remaining owner-facing value gap is a bounded
SENTRY text household-operation slice: a user asks SENTRY for a fresh ANIMA
read or a safe semantic action, ANIMA authorizes/executes/verifies it, and
SENTRY communicates the exact result. This is a goal-directed product
increment, not an automatic start of the historical Phase 15 scenario deck.

The next slice must preserve the accepted Phase 13 client-only MCP boundary,
keep ANIMA authoritative for Truth/policy/execution, and remain text-only and
bounded. Voice, physical whole-home scenarios, and the complete A–O deck remain
later work requiring explicit scope and evidence.
