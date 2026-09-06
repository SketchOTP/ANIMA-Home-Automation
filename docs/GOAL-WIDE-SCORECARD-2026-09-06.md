# Goal-wide usability scorecard — 2026-09-06

This scorecard is a product-planning snapshot, not an acceptance claim. It
compares the permanent completion goal with the current ANIMA repository and
the accepted Phase 0–14 evidence.

| Objective | Current disposition | Evidence boundary / remaining gap |
| --- | --- | --- |
| MO-01 resilience and recovery | ACCEPTED | Phase 14 is accepted; native Pi 5 remains an external hardware gate. |
| MO-02 management plane | PARTIAL — RECOVERY WORKFLOW IMPLEMENTED | Bounded device, integration, alert, notification, scene, automation, task, calendar, preference, backup/restore, and room workflows exist. Unsupported advanced HA administration remains outside the prototype surface. |
| MO-03 versioned API | PARTIAL | Current UI workflows have authenticated API routes; a formal 100% support-matrix audit remains open. |
| MO-04 local UI | PARTIAL — RECOVERY CONTROL ADDED | Current bounded lifecycle is owner-usable, including explicit backup restore with a physical-state reobservation warning; final integrated SENTRY operation is not yet the owner-facing completion marker. |
| MO-05 SENTRY MCP | ACCEPTED | Phase 13 runtime-compatible household boundary is accepted; no raw authority bypass exists. |
| MO-06 SENTRY integration | PARTIAL — OWNER TEXT DELIVERY IMPLEMENTED | The ANIMA UI can queue a bounded SENTRY request and receive/display a live result through the credential-isolated delivery channel. An actual external SENTRY host turn is not claimed by this increment; voice remains later work. |
| MO-07 onboarding without HA frontend | IMPLEMENTED (BOUNDED) | ZHA onboarding, device discovery, commissioning, lifecycle, and recovery are available through ANIMA; unsupported integration classes fail explicitly. |
| MO-08 settings ownership | IMPLEMENTED (BOUNDED) | Presentation, preferences, alert policy, notification route, integration, scene, automation, task, calendar, and room settings are ANIMA-owned where supported. |
| MO-09 external-by-intent | IMPLEMENTED (BOUNDED) | Weather, web, places, recipes, shopping, calendar/reminders, and notification paths are present with explicit trust/degradation limits; cart/checkout is not claimed. |
| MO-10 authority and exact results | ACCEPTED | Identity, policy, credentials, confirmation, verification, provenance, and unknown-result boundaries are retained. |
| MO-11 engineering and deployment | IMPLEMENTED (SUPPORTED PATH) | CI covers x86-64/ARM64 software, containers, migrations, health, and backup evidence; native Pi execution remains gated. |
| MO-12 final integrated scenarios | BUILD LATER | The complete A–O SENTRY-operated scenario deck is intentionally not started. |
| MO-13 SENTRY voice and text | PARTIAL — BOUNDED TEXT DELIVERY | SENTRY is the displayed intelligence identity and ANIMA delivers bounded live results without durable response-text storage or embedded-agent fallback. A live SENTRY host/provider turn and voice operation remain unproven. |
| MO-14 zero HA frontend dependency | PARTIAL | Supported bounded workflows are exposed through ANIMA; a final published support-matrix audit remains to be completed. |
| MO-15 project complete | OPEN | Requires MO-02–MO-14 simultaneously plus final exact-head evidence and owner acceptance. |

## Current product decision

The bounded SENTRY text-delivery increment and the owner-facing backup-restore
increment are implemented and hosted-qualified as separate goal slices. The
next largest owner-facing capability remains the complete text operation:

```text
owner → SENTRY text turn → anima-household MCP/Core → fresh Truth read or safe
semantic action → ANIMA policy/verification → exact result → SENTRY response
```

The actual shadow Codex attempt reached the real provider boundary but stopped
at HTTP 401 authentication. That is an external operator resource gate, not a
reason to add a second cognition seam or embedded fallback. Until it is
available, the repository can continue bounded ANIMA management work; voice,
physical whole-home scenarios, and the complete A–O deck remain later work.
This is not an automatic start of the historical Phase 15 roadmap.

## Latest product increment — bounded backup restore

ANIMA now lets an authenticated owner restore a validated server-owned
PostgreSQL snapshot through Core after explicit browser confirmation. Core
keeps the archive path and database credentials private, applies current
migrations, and invalidates restored physical Truth until Home Assistant is
reobserved. This closes the owner initiation gap without adding a new service
or exposing raw database administration. Phase 14 remains accepted; Phase 15
remains unauthorized.
