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
