# Codex → Architect Result Contract

Return this for every substantial directive.

# CODEX RESULT — <DIRECTIVE ID>

## Verdict

`COMPLETE` | `PARTIAL` | `BLOCKED` | `DISPROVEN` | `NEEDS_ARCHITECT_DECISION`

## Retrieval confidence

`ADEQUATE` | `UNCERTAIN` | `INSUFFICIENT`

## Technical state discovered

Concise live-repository truth established during the task.

## Work performed

What was implemented or investigated.

## Files / areas changed

List important changed areas, or `NONE` for investigation-only work.

## Validation

- `<check>`: `PASSED` | `FAILED` | `NOT RUN` | `NOT APPLICABLE` | `BLOCKED`

## Evidence level

`E0_CLAIMED` | `E1_OBSERVED` | `E2_REPRODUCED` | `E3_TARGET_TESTED` | `E4_REGRESSION_PROTECTED` | `E5_OPERATIONALLY_OBSERVED`

## Acceptance results

- `<criterion>`: `PASSED` | `FAILED` | `NOT RUN` | `NOT APPLICABLE` | `BLOCKED`

## External discovery

What was checked, disposition, and whether it affects strategic direction. Use `NONE` if not triggered.

## Assumptions confirmed

- `<...>`

## Assumptions disproven

- `<...>`

## New durable learnings

- `<...>`

## Risks / blockers

- `<...>`

## Deviations from directive

- `<...>`

## Project records updated

- `.agent`: `<files/entries>`
- Notion: `<page/update or NOT UPDATED>`

## GitHub state

- Commit: `<SHA or NONE>`
- Branch: `<branch>`
- Push/PR state: `<state>`

## Recommendation to Architect

State the technical recommendation, but do not self-authorize a strategic next step.
