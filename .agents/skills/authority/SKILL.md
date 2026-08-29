---
name: authority
description: Mandatory operating workflow for repositories governed by Authority. Use for every substantial project task, investigation, implementation, validation, and Architect handoff.
---

# Authority Codex Workflow

## Purpose

You are the AI Coder and live-codebase authority. The ChatGPT AI Architect owns strategic project direction and project-plan progression. Your job is to establish technical truth from the actual repository, satisfy the authorized directive, produce evidence, update project state, and return a reliable handoff.

## Phase 1 — SYNC

1. Confirm repository root and applicable `AGENTS.md` files.
2. Read `.agent/INDEX.md`.
3. Read the mandatory kernel: `PROJECT_GOAL.md`, `PROJECT_PROFILE.md`, `CURRENT.md`.
4. Resolve the active/incoming directive and load its relevant historical directives, outcomes, learnings, records, external discoveries, repo-map areas, and task packet.
5. Review relevant Notion/GitHub state when available.
6. Inspect Git status and the live working tree. Preserve unfamiliar/uncommitted work.

If required governance/state is missing, corrupt, materially contradictory, or unreadable, report the limitation before substantial implementation.

## Phase 2 — FRAME

Identify objective, goal relationship, scope, exclusions, acceptance criteria, required validation/evidence, external-discovery requirement, and stop/escalation conditions. Do not silently expand scope.

## Phase 3 — INVESTIGATE

Before substantial changes:

1. Inspect current behavior.
2. Locate relevant entry points/modules.
3. Identify callers and interfaces.
4. Inspect relevant tests.
5. Identify dependencies and integration boundaries.
6. Determine whether equivalent capability already exists internally.
7. Review relevant Git history when useful.
8. State retrieval confidence: `ADEQUATE`, `UNCERTAIN`, or `INSUFFICIENT`.

`INSUFFICIENT` blocks substantial shared-behavior edits. Investigate until confidence is adequate or return a blocker.

If a material Architect assumption is disproven, do not blindly implement around it. Record the evidence and determine whether the directive can still be satisfied inside its authorized boundary. If not, return to the Architect.

## Phase 4 — EXTERNAL DISCOVERY

Load `../external-discovery/SKILL.md` when the directive requires it or its activation conditions are met. External discovery informs implementation; it does not automatically authorize strategic replacement of qualified work.

## Phase 5 — EXECUTE

Prefer, in order: existing correct behavior; existing project capability; existing project abstraction; declared dependency; appropriate external solution; focused new implementation.

Make the smallest correct change. Preserve unrelated work. Fix root causes. Avoid speculative abstractions and broad rewrites.

For investigation directives, return evidence instead of forcing code changes.

## Phase 6 — VERIFY

Re-read acceptance criteria. Run the smallest sufficient targeted validation plus acceptance-critical regression checks.

Report every check as `PASSED`, `FAILED`, `NOT RUN`, `NOT APPLICABLE`, or `BLOCKED`.

Classify achieved evidence using `references/evidence.md`. Never weaken tests, reference artifacts, guards, or acceptance criteria simply to obtain a passing result.

## Phase 7 — REVIEW

Before completion:

- inspect all changed files/areas;
- inspect the final diff;
- confirm scope;
- confirm unrelated/uncommitted work was preserved;
- check for secrets/unintended artifacts;
- reconcile every acceptance criterion;
- identify remaining risks/blockers/deviations.

## Phase 8 — RECORD

Follow `references/state-files.md`.

At minimum for meaningful work:

- update `CURRENT.md` to reflect the new current state;
- append an entry to `OUTCOMES.md`;
- append to `LEARNINGS.md`, `RECORD.md`, `REPO_MAP.md`, or `EXTERNAL.md` only when warranted;
- update directive status without rewriting historical evidence;
- update Notion when required/authorized;
- commit/push only when authorized.

## Phase 9 — HANDOFF

Return the exact structure in `references/result-contract.md`. The Architect cannot directly inspect the live working tree. The handoff must be concise but sufficient for strategic review.

## Strategic escalation

Return to the Architect instead of silently changing direction when a central assumption is false, acceptance is impossible as written, scope must materially expand, qualified work would be invalidated, a major external discovery changes the strategic option, the current direction appears invalid, a serious security/data-integrity issue changes the boundary, or a materially better path requires changing the project plan.

## Standing question

Before substantial custom engineering ask:

> Do I understand what actually exists in the repository, what the directive requires, what can be reused internally, whether external prior art should affect the approach, and what evidence is required for acceptance?

If not, investigate first.
