# Evidence — ANIMA-HA-GOAL-SPACE-LIFECYCLE-024A

Status: `COMPLETE — PENDING ARCHITECT ACCEPTANCE`

## Implementation

- `src/anima_ha/graph.py` adds household-scoped parent lookup, cycle-safe
  place movement, sibling-name conflict detection, and empty-place retirement.
- `src/anima_ha/household_spaces.py` exposes typed `move_space` and
  `remove_space` operations and parent-aware projections.
- `src/anima_ha/ui_runtime.py` routes the operations through the existing Core
  gateway.
- `src/anima_ha/ui_api.py` permits only the bounded place operation set.
- `ui/src/main.tsx` provides explicit rename, move, and confirmed remove
  controls and renders parent context.

## Validation

Focused backend tests: PASS (27 tests). Full Python suite: PASS (240 tests).

Ruff format/check: PASS.

Strict mypy: PASS.

TypeScript check: PASS.

Frontend tests: PASS (4 tests).

Vite production build: PASS. Python package build: PASS.

`git diff --check`: PASS.

Implementation head `60ac3e7958f39932f37f519789b6e66d4f2b8b48` passed exact-head
hosted CI `34051465103`. Governance head `7cdedb29f877087dbbec884f4e71a002cc53aa4e`
passed exact-head hosted CI `34051680528` and published artifact `9994893147`.
The downloaded artifact archive hash is
`sha256:b10b3529fd86a86c64319d0c6a247ddbb110d0e7f26d782d01d17cf81b2d5b79`.
Independent Architect acceptance remains pending.

## Boundary

The implementation uses the existing authenticated UI → Core gateway →
PluginManager → PolicyService → PostgreSQL graph path. It does not call Home
Assistant directly, expose provider credentials, alter policy, or begin
Phase 15.
