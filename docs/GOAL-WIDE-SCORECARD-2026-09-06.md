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

The bounded SENTRY text-delivery increment is complete pending Architect
acceptance. It closes the UI-to-live-result handoff but does not claim that a
real external SENTRY host has yet consumed the request. The largest remaining
owner-facing gap is therefore the next coherent text operation:

```text
owner → SENTRY text turn → anima-household MCP/Core → fresh Truth read or safe
semantic action → ANIMA policy/verification → exact result → SENTRY response
```

The next increment must use the accepted client-only MCP boundary and preserve
ANIMA authority for Truth, policy, execution, and verification. If the protected
SENTRY runtime cannot be exercised without source-tree changes or credential
exposure, record that resource boundary explicitly and pivot to the next
owner-usable ANIMA management workflow rather than adding another delivery seam.
Voice, physical whole-home scenarios, and the complete A–O deck remain later
work; this is not an automatic start of the historical Phase 15 roadmap.
