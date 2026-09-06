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

Focused backend tests: PASS (27 tests).

Ruff format/check: PASS.

Strict mypy: PASS.

TypeScript check: PASS.

Frontend tests: PASS (4 tests).

Vite production build: PASS.

`git diff --check`: PASS.

Full-suite, hosted exact-head, and independent Architect acceptance remain
publication gates and must not be inferred from this focused evidence.

## Boundary

The implementation uses the existing authenticated UI → Core gateway →
PluginManager → PolicyService → PostgreSQL graph path. It does not call Home
Assistant directly, expose provider credentials, alter policy, or begin
Phase 15.
