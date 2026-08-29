# Phase 2 — Household Graph

Phase 2 adds deterministic semantic household topology to the Phase 1
PostgreSQL reality substrate. It does not add Home Assistant integration,
memory, policy, agent cognition, action execution, or learned graph behavior.

## Architecture decision

ANIMA owns the canonical graph in PostgreSQL using ordinary relational tables
and recursive CTE queries. `PostgresHouseholdGraph` is the ANIMA-owned contract
and repository boundary; Psycopg remains the only database adapter. Canonical
UUIDs are commissioned by ANIMA and are independent of mutable names and all
provider identifiers. The graph stores nodes, directed typed relationships,
aliases, provider references, and Truth bindings.

The chosen topology is intentionally small: containment, membership, entrance
connectivity, installation, capability exposure, monitoring, control, coverage,
and association. Security sensitivity and household roles are descriptive data
only; they do not grant authority or implement policy.

## Canonical model

`NodeKind` covers household, property, building, floor, room, zone, outside,
entrance, resource, sensor, person, pet, vehicle, and capability. A physical
or logical resource is separate from its capability nodes. For example, a
front-door lock resource exposes `lock.state`, `lock.lock`, and `lock.unlock`.

Containment is parent-to-child `CONTAINS`; the commissioning validator rejects
dangling endpoints and cycles. PostgreSQL recursive CTEs provide descendants
and semantic resource queries. Entrances are nodes with exactly two `CONNECTS`
place endpoints, allowing exterior/interior entrance queries without encoding
provider topology.

Aliases are normalized, scoped optionally, and resolve to zero, one, or many
canonical nodes. Ambiguous results are returned as `AMBIGUOUS`, never guessed.
Renaming preserves the UUID and can preserve the old name as an alias.

Provider references contain provider, provider scope, external object kind,
external ID, target kind, and canonical target. Multiple references may target
one resource; a capability can be targeted separately. Collisions require an
explicit remap, which retires the previous reference and records both changes
in the Phase 1 event journal.

Truth bindings associate a node or capability with an ANIMA truth key and
semantic attribute. The graph asks the existing Truth Service for current
resolution, retaining its status, value, timestamps, observations, and event
provenance. The graph introduces no presence inference.

## Commissioning and audit

`CommissioningDocument(version=1)` is a provider-independent deterministic
bootstrap format. The sample fixture in `anima_ha.fixtures` includes multiple
floors and rooms, outside space, front and garage entrances, locks, contacts,
camera coverage, people/roles, pet, vehicle, aliases, provider references, and
Truth bindings. Validation completes before database mutation. Loading the same
document again is idempotent; conflicting canonical kinds or provider targets
fail explicitly.

Graph mutations and commissioning inserts are committed in one PostgreSQL
transaction with `graph.mutation` events in the existing canonical journal.
Retirement is a timestamped state transition; canonical UUIDs remain stored and
are never reused.

## Prior-art qualification

| Candidate | License / state | Decision | Phase 2 fit and replacement path |
| --- | --- | --- | --- |
| PostgreSQL recursive CTEs | PostgreSQL License; mature PostgreSQL 16 feature | ADOPT / WRAP | Sufficient for the expected household graph; durable, transactional, already qualified, and recursively traversable. Replace repository implementation without changing Core contracts if needed. |
| Apache AGE | Apache-2.0; active extension project | REJECT for this phase | Adds an extension and graph query abstraction to the existing database without measured need. PostgreSQL remains the replacement path. |
| NetworkX | BSD-3-Clause; mature Python library | REJECT as canonical persistence | Useful for in-process algorithms but not durable authoritative storage. It can be added behind a future analysis adapter if a measured algorithm requires it. |
| Brick Schema | BSD-3-Clause; maintained building metadata ontology | REFERENCE / ADAPT | Reuses semantic lessons for building/space vocabulary without forcing RDF/runtime dependencies. ANIMA contracts remain authoritative. |
| Project Haystack | Academic Free License 3.0; open semantic building/IoT project | REFERENCE / ADAPT | Useful tag and relationship prior art; not adopted as the canonical schema because ANIMA needs stronger identity, provenance, provider isolation, and lifecycle semantics. |
| Graphiti | Apache-2.0 code; agent temporal-context project | DEFER | LLM/embedding-assisted temporal enrichment fits later memory/context work, not deterministic commissioned topology. PostgreSQL graph contracts remain the replacement boundary. |

Primary sources: [PostgreSQL recursive queries](https://www.postgresql.org/docs/16/queries-with.html), [Apache AGE](https://github.com/apache/age), [NetworkX](https://github.com/networkx/networkx), [Brick](https://github.com/BrickSchema/Brick), [Project Haystack](https://project-haystack.org/), and [Graphiti](https://github.com/getzep/graphiti). The future Home Assistant identity adapter must treat provider IDs as external references because of the [device registry config-entry constraint](https://developers.home-assistant.io/blog/2026/07/21/device-registry-single-config-entry/).

## Query surface

The current Core repository provides semantic methods for household and place
listing, recursive and direct resource lookup, exterior entrances and endpoint
places, monitoring sensors, capabilities, capability-to-resource lookup,
security-sensitive objects, aliases, provider-reference mapping, Truth-backed
presence, rename, remap, and retirement. These are Core APIs, not Luna tools.

## Evidence boundary

Unit evidence covers contract validation, cycle/reference/entrance rejection,
and alias collision behavior. PostgreSQL integration evidence covers durable
commissioning, recursive queries, idempotency, provider mappings, Truth
provenance, audit, rename, and remap. Simulator evidence uses only the synthetic
fixture. No Home Assistant or physical-home claim is made; ARM64 evidence
remains the previously accepted image/package metadata level.
