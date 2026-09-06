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
stale-version handling. Exact-head hosted qualification passed on
`c59504dcb9d85daecb16972fd1dfe925431821b7` in CI `34030239375`. The reviewable
artifact is `9988522653`, digest
`sha256:3c452d235a538c633840a6973f7111eae1d649df4e0abf6889f3199dd37f454d`.
The hosted workflow also passed the existing Phase 0–14/SENTRY validation,
ARM64/container checks, H5 targets, and public-safety scan. Local Python pytest
was unavailable in the SFTP checkout, so local execution is not claimed.

This increment remains pending independent Architect acceptance. Phase 15 is
not implemented or authorized.
