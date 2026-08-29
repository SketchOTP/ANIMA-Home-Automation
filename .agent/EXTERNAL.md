# External Discovery Ledger

Record material prior-art investigations when Authority triggers external discovery. Do not log every trivial web search.

---

## AUTHORITY-BOOTSTRAP-001 — Authority 3.0 governance package

- Date checked: 2026-08-28
- Trigger: Governance installation for a new project.
- Source: Connected Notion page `Authority 3.0 — Complete Installation Package`.
- Freshness: Retrieved 2026-08-28; package page states Authority 3.0.
- Disposition: ADOPT

### Problem addressed

Provide a durable governance and evidence workflow for a project operated through an Architect → Codex → evidence → Architect loop.

### Relevant overlap

The package defines the root agent router, project state/history files, reusable Codex and external-discovery workflows, directive/result contracts, evidence ladder, state update rules, safety boundary, and new-project checklist.

### Fit / limitations

It is governance and process infrastructure, not ANIMA HA implementation. It does not establish runtime dependencies, architecture completion, or prototype acceptance evidence.

### Decision rationale

Adopted because it is the requested Authority 3.0 package and directly supplies the required new-project file set.

### Recheck trigger

Only when the canonical Authority package changes or the project is explicitly migrated to a newer authorized governance version.

---

## ANIMA-HA-P0-RUNTIME-BASELINE-002 — Python packaging, tooling, and runtime

- Date checked: 2026-08-28/29
- Trigger: Phase 0 requires reproducible dependencies, automated validation, and portable runtime support.
- Source: [uv project/lockfile documentation](https://docs.astral.sh/uv/guides/projects/); [Ruff linter](https://docs.astral.sh/ruff/linter/); [Ruff formatter](https://docs.astral.sh/ruff/formatter/); [Psycopg](https://www.psycopg.org/download/); [pytest](https://github.com/pytest-dev/pytest); [mypy](https://github.com/python/mypy); [uv license](https://github.com/astral-sh/uv/blob/main/README.md#license).
- Freshness: Sources checked against current published documentation/package metadata; exact adopted versions are in `pyproject.toml` and `uv.lock`.
- Disposition: ADOPT, with `psycopg` WRAPPED behind the ANIMA database boundary.

### Problem addressed

Provide a small, reproducible Python project environment and deterministic engineering checks on ARM64 and x86-64.

### Relevant overlap

uv supplies a checked-in cross-platform lockfile and managed environment; Ruff supplies lint and formatting; pytest supplies unit tests; mypy supplies strict static checking; Psycopg supplies the PostgreSQL DB-API adapter and binary wheels.

### Fit / limitations

All selected packages support Python 3.12. Psycopg 3.3.4 has Linux ARM64 and x86-64 binary wheels; Ruff and mypy publish ARM64-capable Linux distributions. The live host is x86-64. The latest mypy 2.3.1 produced an internal validation error and was not adopted; 1.17.1 passes and is pinned pending requalification.

### Decision rationale

The set is sufficient for Phase 0 and avoids adopting future-phase frameworks. Exact versions are locked; application code owns configuration/logging/database boundaries so providers can be replaced later.

### Recheck trigger

Upgrade request, Python-line change, ARM64 native execution, or introduction of a later-phase dependency that changes packaging or database requirements.

---

## ANIMA-HA-P0-RUNTIME-BASELINE-002 — PostgreSQL and pgvector deployment

- Date checked: 2026-08-28/29
- Trigger: Phase 0 requires a persistent substrate, migration mechanism, health check, restart persistence, and evaluation of the later vector-memory path.
- Source: [official PostgreSQL image](https://hub.docker.com/_/postgres); [pgvector project/Docker tags](https://github.com/pgvector/pgvector); [Docker multi-platform images](https://docs.docker.com/build/building/multi-platform/).
- Freshness: Image manifest and runtime inspection performed 2026-08-28/29; exact digest is recorded in `compose.yaml`.
- Disposition: ADOPT the pinned pgvector image conditionally for future vector use; ADOPT PostgreSQL; WRAP database access behind ANIMA-owned code; DEFER vector schema/use.

### Problem addressed

Provide isolated local persistence without pulling message brokers, policy engines, memory services, or agent infrastructure into Phase 0.

### Relevant overlap

PostgreSQL supplies the durable relational substrate. The pgvector image preserves a low-cost extension path for future memory work. Compose supplies health checking, named-volume persistence, and restart control.

### Fit / limitations

The observed pgvector image digest has Linux amd64 and arm64 manifests, includes vector extension 0.8.6, and ran successfully on this x86-64 host. The pulled image is approximately 621 MB and the idle container used approximately 0.02% CPU / 71 MiB memory on this host. These are not Raspberry Pi measurements. The named volume is the backup boundary; backup/restore implementation is deferred.

### Decision rationale

The image retains the later vector option without enabling product behavior or adding another service. Official `postgres:16-bookworm` remains the replacement path if pgvector maintenance or footprint becomes unacceptable.

### Recheck trigger

Native Pi run, image digest update, Phase 1 memory schema design, backup/restore qualification, or resource pressure on the target controller.

## ANIMA-HA-P1-REALITY-SUBSTRATE-003 — event journal and projection prior art

- Date checked: 2026-08-29
- Trigger: Phase 1 required a persistence/prior-art comparison before implementing the canonical event journal and Truth/State service.
- Sources: [Python eventsourcing project](https://github.com/pyeventsourcing/eventsourcing); [eventsourcing PostgreSQL documentation](https://eventsourcing.readthedocs.io/en/stable/topics/tutorial/part3.html); [NATS JetStream concepts](https://docs.nats.io/concepts/jetstream); [KurrentDB introduction](https://docs.kurrent.io/server/latest/); [KurrentDB repository](https://github.com/Kurrent-io/KurrentDB).

### Comparison and disposition

| Candidate | Disposition | Qualification | ANIMA decision |
| --- | --- | --- | --- |
| Existing PostgreSQL + Psycopg | ADOPT / WRAP | Already qualified in Phase 0; PostgreSQL 16/pgvector image has ARM64/x86-64 manifests; transactional SQL, unique constraints, JSONB, restart persistence | Canonical journal and derived truth projection behind ANIMA-owned interfaces |
| Direct ANIMA journal/reducer implementation | BUILD | Keeps event envelope, provenance, time semantics, truth quality, reconciliation, and replay owned by ANIMA | Selected for Phase 1 |
| Python `eventsourcing` 9.5.5 documentation/project | DEFER | BSD-3-Clause, maintained, typed, and PostgreSQL-capable through Psycopg; aggregate/application model does not directly fit external observations and ANIMA truth semantics | Reconsider only if a later bounded spike shows material code reduction without coupling |
| NATS JetStream (current server; version not pinned) | DEFER | NATS server is Apache-2.0; official JetStream docs describe persistent streams, durable consumers, replay, and at-least-once redelivery | Add only when independent asynchronous consumers justify a broker; do not replace canonical journal |
| KurrentDB/EventStoreDB v26.0 | REJECT for prototype baseline | Current KurrentDB docs identify Kurrent License v1 as not OSI-approved; separate event-native service adds operational/storage overhead and is unnecessary for Phase 1 | Keep as non-foundational alternative; replacement path is PostgreSQL |

### Boundary conclusion

The selected design preserves the event-sourcing benefits needed here—durable history plus rebuildable derived state—without delegating ANIMA's event/truth meanings to a framework or adding a second persistence service. The decision does not change the SSOT architecture or phase ordering.

## ANIMA-HA-P2-HOUSEHOLD-GRAPH-004 — canonical graph prior art

- Date checked: 2026-08-29
- Trigger: Phase 2 required prior-art comparison before selecting canonical graph persistence.
- Sources: [PostgreSQL recursive queries](https://www.postgresql.org/docs/16/queries-with.html); [Apache AGE](https://github.com/apache/age); [NetworkX](https://github.com/networkx/networkx); [Brick Schema](https://github.com/BrickSchema/Brick); [Project Haystack](https://project-haystack.org/); [Graphiti](https://github.com/getzep/graphiti).

### Comparison and disposition

| Candidate | License / maintenance | Fit, persistence, portability, and replacement path | Decision |
| --- | --- | --- | --- |
| PostgreSQL recursive CTE | PostgreSQL License; mature core feature in PostgreSQL 16 | Durable transactional relational persistence; recursive hierarchy traversal; already qualified for x86-64 and ARM64 image path; replace repository behind ANIMA contracts if needed | ADOPT / WRAP |
| Apache AGE | Apache-2.0; active PostgreSQL extension | Adds an extension and graph query abstraction without measured need for the expected household scale; PostgreSQL CTE repository is the replacement path | REJECT |
| NetworkX | BSD-3-Clause; mature Python project | In-process algorithms only; no authoritative durable persistence, restart, or transaction boundary; future analysis adapter could wrap it | REJECT as canonical persistence |
| Brick Schema | BSD-3-Clause; building semantic project | Broad RDF ontology and useful building vocabulary; runtime adoption would add semantic/dependency coupling; ANIMA graph contracts are the replacement boundary | REFERENCE / ADAPT |
| Project Haystack | Academic Free License 3.0; open building/IoT semantic project | Useful tags and relationships, but does not replace ANIMA-owned UUID, provenance, lifecycle, or provider-reference semantics | REFERENCE / ADAPT |
| Graphiti | Apache-2.0 code; active temporal agent-context project | LLM/embedding-assisted temporal graph construction fits later learned memory/context, not deterministic commissioned topology | DEFER |

### Boundary conclusion

No new graph database, extension, or service was introduced. The selected
PostgreSQL/Psycopg repository preserves ANIMA ownership of identity, semantics,
provider isolation, Truth bindings, mutation audit, and query behavior. The
Home Assistant registry remains future provider input only; its IDs are not
canonical household identity.
