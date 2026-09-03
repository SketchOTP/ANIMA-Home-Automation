# CODEX DIRECTIVE — ANIMA-HA-P12-PRODUCT-SURFACE-ACCEPTANCE-CLOSURE-014H5R

## Disposition

`ACTIVE — REPLAN/SUPERSEDE H5 BEFORE FURTHER IMPLEMENTATION`.

## Parent directive/result

Supersedes `ANIMA-HA-P12-BROWSER-ACCEPTANCE-EVIDENCE-CLOSURE-014H5`, whose published H5 implementation/evidence remains preserved but partial. Parent status: `CONTINUE — IMPLEMENTATION/EVIDENCE PARTIAL; PENDING ARCHITECT ACCEPTANCE`.

## Exact baseline

- Repository: `SketchOTP/ANIMA-Home-Automation`
- Baseline SHA: `fe1833987aeaac60e680fca7035fa3e915ca1d70`
- Local `main` and `origin/main` matched at directive issuance.

## Verified current state

Phase 12 has a configured Core-composed UI and H5 deterministic Core/API, Docker, frontend, Playwright, restricted-content, external-health/audit, and isolated-HA API evidence. The decisive browser journeys remain unrun. The canonical Notion SSOT has now identified a higher-value product-surface gap: the prior H5 path over-centered browser evidence while omitting required rooms/devices, activity semantics, notifications/reports/recent actions, truthful health, and supported pending-approval state. The repository still points at the superseded H5 packet and must be reconciled without discarding its valid implementation or evidence.

## Relationship to canonical goal

This directive closes the actual Phase 12 product exit gate toward `ANIMA_HA_PROTOTYPE_GOAL_COMPLETE` by making the local interface represent the household intelligence and its governed evidence coherently. It is not project completion and does not authorize Phase 13.

## Primary closure objective

Close the Phase 12 product-surface acceptance gap with the shortest defensible implementation and evidence path, then stop Phase 12 for Architect acceptance.

## Bottleneck rationale

Additional browser tests around an incomplete product surface would be evidence drift. The current critical gap is not merely more browser coverage; it is that required household views and truthful operational state are incomplete or semantically mismapped. Approval behavior also must be grounded in the existing Phase 4/8 contracts before any UI affordance is added.

## Authorized scope

- Reconcile local Authority state with the canonical Notion H5R replan while preserving H5 implementation/evidence.
- Inspect and reuse the existing Phase 4 `ConfirmationChallenge` issue/consume contract, durable challenge store, Phase 5 confirmation input, and Phase 8 `WAITING_CONFIRMATION` behavior.
- Retain existing conversation, household/presence/security/weather, tasks/calendar, controls, capability, settings, and H5 evidence behavior.
- Make `display_mode` measurably alter bounded layout if still required by current implementation.
- Correct the configurable `activity` widget so it represents activity rather than a future voice card.
- Add a minimal Household Graph-derived rooms/devices view.
- Add sanitized notifications/reports/recent-actions views using existing journal, episode, action, and policy evidence.
- Make overall health reflect degraded and unavailable required capabilities honestly.
- Expose pending approval/user-action state only where existing Phase 4/8 contracts support an exact, single-use, audited continuation.
- Add focused tests and acceptance evidence for the changed surfaces.

## Prohibited scope

- No Phase 1–11 semantic weakening or replacement of accepted architecture.
- No new provider, framework, database, broker, or authority store.
- No browser-direct HA/provider/database access.
- No browser-supplied authority, action arguments, or confirmation bypass.
- No decorative Approve button; if safe continuation requires a material Phase 8 redesign, stop and return `NEEDS ARCHITECT_DECISION — CONFIRMATION_CONTINUATION_GAP`.
- No service worker/client durable content or raw restricted-content persistence.
- No production fault endpoint, arbitrary model/runtime injection, or self-programming capability.
- No Phase 13 voice behavior beyond accurately displaying future/unavailable state.
- Do not mark Phase 12 accepted or move the packet to completed under this directive alone.

## Required investigation

1. Inspect the current UI entry points, semantic view models, read models, API gateways, preference application, and existing tests.
2. Inspect the Phase 4 confirmation issue/consume contract and durable store, Phase 5 confirmation input, and Phase 8 `WAITING_CONFIRMATION` episode behavior.
3. Trace available journal, episode, action, policy, capability-health, Household Graph, and device/room data paths.
4. Determine which product surfaces can be composed from existing contracts without introducing a second authority or state owner.
5. State retrieval confidence before implementation as `ADEQUATE`, `UNCERTAIN`, or `INSUFFICIENT`. `INSUFFICIENT` blocks shared-behavior edits.

## Acceptance criteria

- The local Authority packet and current snapshot identify H5R as the active directive while preserving H5 as historical evidence.
- A commissioned sample household is operable through the desktop/tablet UI.
- Activity, Graph-derived rooms/devices, sanitized notifications/reports/recent actions, truthful health, and supported pending user action render from existing Core-owned data paths.
- `display_mode` produces measurable bounded layout behavior; configurable widget visibility/order remains real.
- Any supported confirmation path is exact, principal/intent/expiry bound, single-use, policy-gated, and audited; unsupported continuation is clearly unavailable.
- Existing task/calendar/control paths continue through normal Core gateways and preserve Phase 9 outcomes.
- Restricted content remains live-only and absent after reload from browser storage and PostgreSQL.
- Deterministic provider failure/recovery is reflected honestly and unrelated capabilities remain usable.
- Existing isolated-HA API evidence is rerun on the exact candidate head; browser evidence is added where it materially proves user-visible behavior.
- Phase 0–11 regression protection and repository/public-safety checks remain green.

## Required validation and evidence

Report every check as `PASSED`, `FAILED`, `NOT RUN`, `NOT APPLICABLE`, or `BLOCKED` and classify evidence with the Authority ladder. Run focused unit/API/UI tests, relevant full regression, type/lint/build checks, and acceptance-critical browser/runtime evidence. Do not promote deterministic or API evidence to browser evidence, or implementation existence to capability proof.

## Required durable updates

After execution and independent review, update `.agent/CURRENT.md`, append `.agent/DIRECTIVES.md` and `.agent/OUTCOMES.md` without rewriting history, update the task packet evidence/handoff, synchronize GitHub and the canonical ANIMA HA/Authority Notion records when authorized, refetch those records, verify exact SHA/CI/evidence alignment, and release or transition the project execution lock only after durable reconciliation.

## Stop conditions

Stop implementation and return to the Architect if the confirmation investigation requires a material Phase 8 redesign, a central assumption is false, a required capability cannot be composed within the authorized boundary, lock ownership/fencing cannot be validated, or Notion/GitHub/repository state cannot be reconciled without strategic direction. Phase 13 remains unauthorized.
