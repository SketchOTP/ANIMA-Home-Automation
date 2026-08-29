# Complex Task Packets

Task packets are optional and proportional.

Create `.agent/tasks/active/<directive-id>/` only when work is genuinely complex, long-running, multi-stage, research-heavy, high-risk, or handoff-sensitive.

Do not create task packets for ordinary fixes or small features.

A task packet contains:

- `SPEC.md` — objective, scope, exclusions, acceptance, risks, stop conditions.
- `PLAN.md` — current implementation/investigation plan and checkpoints.
- `EVIDENCE.md` — important validation/evidence produced during the work.
- `HANDOFF.md` — concise continuation state if another session/agent must resume.

When the directive closes, move/preserve the packet under `tasks/completed/<directive-id>/` according to repository policy. Do not delete failed task packets merely because the work did not succeed.
