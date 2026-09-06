# Goal increment — ANIMA scene management

ANIMA now provides a bounded owner-facing scene workflow. A scene is a
household-scoped, versioned preset containing up to 16 canonical power
resources and their requested `desired_on` states. The browser never submits a
Home Assistant entity ID, service name, or arbitrary automation payload.

Scenes are created and edited through the Core plugin boundary and are checked
against commissioned household power resources. Applying a scene is a
sequence of ordinary ANIMA controls. Each step reuses the existing
Phase 5 → OPA → Phase 9 action path, including resource locking, fresh state,
verification, and the authoritative terminal outcome. If a later step cannot
complete, ANIMA reports a bounded `PARTIAL` result and stops; it does not claim
an atomic batch success.

This is the first reusable scene/preset slice of the management plane. Raw Home
Assistant automation editing, triggers, schedules, scenes with non-power
domains, and advanced integration configuration remain explicitly outside
this increment and require their own typed capabilities.

## Core surface

- PostgreSQL migration `0024_scenes.sql` stores definitions and optimistic
  versions.
- `anima.scenes` exposes `list_scenes`, `create_scene`, and `update_scene`.
- `POST /api/v1/scenes` manages definitions; `POST
  /api/v1/scenes/{scene_id}/apply` applies one through Core controls.
- UI scene definitions are household-scoped durable state; provider
  credentials and Home Assistant details remain server-owned.

## Evidence boundary

The implementation is covered by deterministic validation for household
scope, commissioned-resource validation, duplicate-resource rejection, and
stale-version handling. Full PostgreSQL, OPA, Home Assistant, frontend, and
hosted CI qualification remains the authoritative next validation step.
