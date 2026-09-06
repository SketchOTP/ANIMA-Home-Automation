# ANIMA HA — Goal Alert Policy Management 017A

## Objective

Deliver the smallest owner-facing management-plane slice that lets the owner
configure typed SenseGuard alert policies through ANIMA, without opening the
Home Assistant frontend or exposing a raw automation editor.

## Scope

- expose existing SenseGuard policy semantics through the Core/plugin boundary;
- list, create, update, enable, and disable policies for the authenticated
  household;
- preserve optimistic versioning, provenance, timezone/window semantics, and
  existing policy evaluation;
- add an ANIMA Alerts view with bounded resource selection and clear outcomes;
- prove persistence, policy routing compatibility, and restart behavior;
- update goal-facing documentation and evidence.

## Explicit non-goals

- no new provider, database, broker, or framework;
- no raw Home Assistant automation editor or arbitrary YAML/service payloads;
- no changes to OPA semantics, Attention semantics, or Phase 15 behavior;
- no Phase 15 household demonstration.

## Sequence

1. Map current SenseGuard store, plugin, Core runtime, UI gateway, read model,
   API, and test composition.
2. Add the typed Core adapter and bounded read/write routes using the existing
   policy store and PluginManager boundary.
3. Add the Alerts UI and normalized semantic mutation feedback.
4. Add deterministic, PostgreSQL-backed tests for ownership, version conflict,
   enable/disable, and event-router compatibility.
5. Run static/tests/build checks, publish evidence, and reconcile governance.

