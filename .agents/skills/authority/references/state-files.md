# Project-State Update Rules

## INDEX.md

Update pointers when the current stage, active directive, active task packet, or last accepted outcome changes.

## PROJECT_GOAL.md

Do not change without explicit authorized strategic goal change.

## PROJECT_PROFILE.md

Update verified durable profile/configuration facts when they materially change.

## CURRENT.md

Mutable snapshot. Update after meaningful work so the next agent can understand current stage, objective, blockers, evidence, and decision point.

## DIRECTIVES.md

Append-only after adoption. Add new directives and status/supersession records without rewriting historical directive content.

## OUTCOMES.md

Append-only. Record what actually happened and the evidence achieved, including failures/partials.

## LEARNINGS.md

Append-only. Only durable verified or explicitly supported-hypothesis knowledge belongs here.

## RECORD.md

Append-only. Major decisions, milestones, reversals, failures, and governance events only.

## REPO_MAP.md

Update only when repository structure/understanding changes materially and is verified.

## EXTERNAL.md

Append-only. Record material prior-art investigations when external discovery was warranted.

## tasks/

Use only for genuinely complex/long-running/handoff-sensitive work. Preserve failed/completed packets for provenance.

Never rewrite or delete history merely to make the project appear cleaner or more linear.

## Native loop responsibilities and loading

INDEX lists exact responsibility and read/update triggers for every required
state file. Coder updates affected local files; Architect independently checks
accuracy and supplies acceptance/disposition. Keep detailed evidence in the
existing integration packet and reference it from both repositories; preserve
separate component goals. Do not create competing integration plans.

CURRENT checkpoints distinguish local/committed/pushed/deployed pairs, worker
role, gaps, blockers, synchronization and next action. OUTCOMES distinguishes
reported results from independent verification. Historical DIRECTIVES/RECORD/
OUTCOMES and task evidence retain prior bytes; append sourced supersessions.
Keep blocked/review-pending work in active; completed holds accepted, cancelled
or superseded work with distinct dispositions. This is the current lifecycle
rule over any older generic packet-close wording.

Read root AGENTS, Authority skill, INDEX, its .agent goal/profile/current kernel,
the active task and relevant history. Explicit file reread/fingerprints do not
prove client startup discovery or automatic reload in an existing session.
