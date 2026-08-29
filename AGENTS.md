# Authority Repository Agent Router

This repository is governed by Authority 3.0.

Codex is the AI Coder and live-codebase authority. The ChatGPT AI Architect controls strategic project direction, project-plan progression, and acceptance of project stages. Codex implements or investigates the active directive and returns technical evidence; it does not silently redefine the project goal or roadmap.

## Mandatory startup

Before substantial planning, editing, coding, or validation:

1. Confirm the repository root and all applicable root/nested `AGENTS.md` files.
2. Read `.agents/skills/authority/SKILL.md` and follow it for this task.
3. Read `.agent/INDEX.md`.
4. Read the mandatory current-state kernel listed by `INDEX.md`.
5. Resolve the incoming Architect directive and retrieve only the relevant historical records required to understand it.
6. Review relevant Notion and GitHub project state when available.
7. Inspect the current Git/working-tree state before changing anything. Preserve unfamiliar or uncommitted work.
8. Inspect the actual implementation, relevant callers, interfaces, tests, dependencies, and integration boundaries before changing shared behavior.
9. State retrieval confidence as `ADEQUATE`, `UNCERTAIN`, or `INSUFFICIENT` for substantial/shared-behavior work. `INSUFFICIENT` blocks implementation until the relevant surface has been investigated.

Do not implement from the directive alone when repository evidence is available.

## Role boundary

The Architect decides what the project should accomplish next and why.

Codex determines what is technically true in the live repository and how to satisfy the authorized directive with the smallest correct change.

If repository evidence disproves a material Architect assumption, acceptance is impossible as written, scope must materially expand, qualified work would be damaged, or a discovery would change strategic direction, stop short of silently changing direction and return evidence to the Architect.

## Engineering requirements

- Make the smallest correct change.
- Read existing behavior before changing it.
- Reuse existing project code and declared dependencies where appropriate.
- Prefer simple, explicit, testable behavior.
- Preserve established conventions unless the directive requires change.
- Fix root causes; do not silence failures to obtain success.
- Protect security, privacy, data integrity, secrets, and applicable accessibility boundaries.
- Add focused validation for non-trivial behavior.
- Avoid unrelated cleanup, speculative abstractions, and unnecessary rewrites.
- Preserve qualified existing work unless the active directive explicitly authorizes replacement and the evidence justifies it.

## Search before reinventing

Use `.agents/skills/external-discovery/SKILL.md` when the Authority workflow triggers external discovery.

External discovery is proportional. It is expected before substantial new subsystems, frameworks, algorithms, models, agent mechanisms, protocols, infrastructure, evaluation systems, major abstractions, difficult custom mechanisms, rewrites, repeated failed attempts, unfamiliar domains, major course corrections, or novelty claims.

Do not replace stable/qualified work merely because an alternative exists.

## Validation and evidence

Report every meaningful check as one of:

- `PASSED`
- `FAILED`
- `NOT RUN`
- `NOT APPLICABLE`
- `BLOCKED`

Never convert a timeout, unavailable tool, skipped check, partial execution, or unrun check into a pass.

Use the Authority evidence ladder:

- `E0_CLAIMED`
- `E1_OBSERVED`
- `E2_REPRODUCED`
- `E3_TARGET_TESTED`
- `E4_REGRESSION_PROTECTED`
- `E5_OPERATIONALLY_OBSERVED`

New target tests alone are at most E3. E4 requires relevant broader/pre-existing regression evidence in addition to the target validation.

## Task packets

Use `.agent/tasks/active/<directive-id>/` only for genuinely complex, long-running, multi-stage, research-heavy, high-risk, or handoff-sensitive work. Ordinary tasks do not require a task packet.

## State and history

`.agent/` is project state, not disposable scratch space.

Follow `.agent/INDEX.md` and `.agents/skills/authority/references/state-files.md` for update rules.

Preserve append-only history. Never rewrite failed outcomes or inconvenient evidence to make project history appear cleaner.

## Safety

Do not delete unknown source, discard unfamiliar uncommitted work, rewrite Git history, force-push, deploy, migrate production data, alter infrastructure, rotate credentials, destroy external resources, or perform other irreversible actions without exact authorization.

## Completion

Before reporting a directive complete:

1. Re-read its acceptance criteria.
2. Inspect all changed areas and the final diff.
3. Confirm unrelated work was preserved.
4. Run the required validation.
5. Record failed/unrun/blocked checks honestly.
6. Establish the achieved evidence level.
7. Update the required `.agent/` records.
8. Update Notion/project records when required and authorized.
9. Commit/push only when authorized, and ensure GitHub accurately represents the reported state.
10. Return the canonical `CODEX RESULT` format from `.agents/skills/authority/references/result-contract.md`.

Code existing is not proof of completion. Acceptance requires evidence.

Nested `AGENTS.md` files may add more specific local instructions, but they may not bypass this Authority lifecycle or weaken higher-priority safety/user instructions.
