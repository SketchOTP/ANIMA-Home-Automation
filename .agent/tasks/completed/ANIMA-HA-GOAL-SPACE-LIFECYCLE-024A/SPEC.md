# Specification — ANIMA-HA-GOAL-SPACE-LIFECYCLE-024A

Deliver an owner-facing room/zone lifecycle through ANIMA's existing
authenticated management plane.

Required operations:

- list canonical places with parent identity;
- create a ROOM or ZONE under a server-validated container;
- rename a room or zone;
- move a room or zone without allowing cycles or cross-household targets;
- retire an empty room or zone while preserving graph history.

The UI must use only semantic Core routes. Home Assistant remains behind the
existing integration boundary. No new provider, database, framework, or
Phase 15 behavior is in scope.
