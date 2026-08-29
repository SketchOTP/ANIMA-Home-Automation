# Phase 0 dependency qualification

Checked: 2026-08-28/29 UTC. This is a Phase 0 qualification record, not a claim that all future ANIMA dependencies are selected.

| Component | Version / source | Decision | License / provenance | Qualification result |
| --- | --- | --- | --- | --- |
| CPython | 3.12.x; host observed 3.12.3 | ADOPT | PSF; standard library | Matches the planned Python stack and near-term library constraints. `.python-version` and `requires-python` constrain the supported line. |
| uv | 0.12.7 | ADOPT | Apache-2.0 OR MIT; Astral | Provides the project environment and universal lockfile. The lockfile is committed. |
| uv-build | 0.10.11, locked transitively | ADOPT | Apache-2.0 OR MIT; Astral | Small PEP 517 build backend; wheel and source distribution build passed from a local filesystem copy. |
| psycopg[binary] | 3.3.4 | ADOPT + WRAP | LGPL-3.0-only; Psycopg | Current PostgreSQL adapter with CPython 3.12 ARM64 and x86-64 binary wheels. It is used only behind `anima_ha.db`. |
| Ruff | 0.16.5 | ADOPT | MIT; Astral | One tool supplies deterministic lint and formatting; both checks pass. Published wheels include Linux ARM64 and x86-64 variants. |
| pytest | 9.1.1 | ADOPT | MIT; pytest-dev | Mature unit-test harness; four baseline tests pass. |
| mypy | 1.17.1 | ADOPT | MIT; mypy | Strict static checking passes on the baseline. Current PyPI `2.3.1` was evaluated but rejected for this checkpoint after an internal error during validation; re-evaluate on a future controlled upgrade. |
| Docker Compose | host Compose v5.5.0 | ADOPT | Docker distribution | Isolates the database service and named persistence volume. The repository does not require an application container yet. |
| PostgreSQL | Official 16.15 Bookworm base | ADOPT + WRAP | PostgreSQL License; official Docker image | Health-checked local persistent substrate. The application accesses it through the ANIMA database boundary. |
| pgvector image | `pgvector/pgvector:pg16-bookworm@sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`; extension 0.8.6 | ADOPT conditionally | PostgreSQL License; pgvector project image | Multi-arch image was inspected for Linux ARM64 and amd64 and ran successfully on x86-64. It avoids a later image migration if memory work adopts vectors. Vector extension use and vector/product schema remain deferred. |
| GitHub Actions | `actions/checkout@v5`, `actions/setup-python@v6` | ADOPT | GitHub Actions marketplace actions | CI invokes the same deterministic validation wrapper on Python 3.12.3. A hosted CI run is pending this checkpoint's push. |

## Deferred candidates

NATS/JetStream, OPA, Mem0, Hatchet, Home Assistant runtime, Luna/OpenAI Agents SDK, MCP/plugin implementations, UI, voice, and external-service clients are `DEFER`. They are not needed to prove this runtime baseline and introducing them would cross the Phase 0 boundary. Their qualification belongs to the phase that needs each interface.

## Material rejected alternatives

- `mypy 2.3.1` was not adopted for this checkpoint because the live x86-64 run produced an internal error before a type result. The pinned `1.17.1` run passes; upgrading requires a fresh qualification.
- Plain `postgres:16-bookworm` was not selected as the Compose image because the current phase can preserve the later memory option at low integration cost with the pgvector image. The official PostgreSQL image remains the replacement path if pgvector is later rejected.
- A larger service stack was not introduced because no Phase 0 acceptance criterion requires message brokers, policy engines, agent runtimes, or external connectors yet.

## Evidence and recheck triggers

- The host is x86-64. ARM64 claims are manifest and wheel metadata evidence, not native Raspberry Pi execution evidence.
- Docker manifest inspection showed official PostgreSQL 16.15 `linux/amd64` and `linux/arm64/v8` variants and pgvector image `linux/amd64` and `linux/arm64` variants.
- The pulled pgvector image is approximately 621 MB locally; idle database use observed on this host was approximately 0.02% CPU and 71 MiB memory. These are x86-64 host measurements, not Pi budgets.
- The named volume preserved migration metadata across `docker compose restart db`. Volume backup/restore remains a later explicit validation item.
- Recheck dependency versions, image digests, licenses, and resource use before production-like deployment or when Phase 1 adds a dependency that changes the persistence, event, policy, or agent boundaries.

## Primary sources

- [uv projects and lockfiles](https://docs.astral.sh/uv/guides/projects/)
- [Ruff linter](https://docs.astral.sh/ruff/linter/) and [formatter](https://docs.astral.sh/ruff/formatter/)
- [Psycopg download and license](https://www.psycopg.org/download/)
- [pytest repository and license](https://github.com/pytest-dev/pytest)
- [mypy license](https://github.com/python/mypy/blob/master/LICENSE)
- [uv license](https://github.com/astral-sh/uv/blob/main/README.md#license)
- [official PostgreSQL image](https://hub.docker.com/_/postgres)
- [pgvector project and Docker tags](https://github.com/pgvector/pgvector)
- [Docker multi-platform images](https://docs.docker.com/build/building/multi-platform/)
- [GitHub Python Actions guidance](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)

## Phase 2 graph prior-art qualification

Checked: 2026-08-29. No new runtime dependency or infrastructure service was
introduced for the canonical household graph.

| Candidate | License / maintenance | Decision | Qualification and replacement path |
| --- | --- | --- | --- |
| PostgreSQL 16 recursive CTE | PostgreSQL License; mature core feature | ADOPT / WRAP | Supports hierarchical traversal and remains on the already-qualified PostgreSQL/Psycopg boundary. ANIMA owns contracts and can replace the repository implementation without changing callers. |
| Apache AGE | Apache-2.0; active PostgreSQL extension | REJECT | Requires an extra extension/query model and does not save enough work for this bounded household graph. Existing PostgreSQL tables/CTEs are the lower-risk replacement path. |
| NetworkX | BSD-3-Clause; mature Python library | REJECT as storage | In-process graph structures do not provide authoritative persistence, transactionality, or restart durability. A future algorithm adapter could wrap it if measured need appears. |
| Brick Schema | BSD-3-Clause; building ontology project | REFERENCE / ADAPT | Semantic vocabulary and relationship prior art only; no RDF dependency or runtime lock-in. |
| Project Haystack | Academic Free License 3.0; open building/IoT semantic project | REFERENCE / ADAPT | Tagging and semantic lessons only; ANIMA requires its own identity, provenance, lifecycle, and provider-reference semantics. |
| Graphiti | Apache-2.0 code; active agent temporal-context project | DEFER | LLM/embedding-assisted temporal enrichment belongs to later memory/context work, not commissioned deterministic topology. |

Primary sources: [PostgreSQL recursive queries](https://www.postgresql.org/docs/16/queries-with.html), [Apache AGE](https://github.com/apache/age), [NetworkX](https://github.com/networkx/networkx), [Brick](https://github.com/BrickSchema/Brick), [Project Haystack](https://project-haystack.org/), and [Graphiti](https://github.com/getzep/graphiti).

## Phase 3 governed memory and routine qualification

Checked: 2026-08-29. Phase 3 adds no new service or Python runtime dependency.
Canonical memory and routine persistence are built on the accepted PostgreSQL
16/Psycopg boundary; PostgreSQL full-text search is used only as a derived
local index.

| Candidate | Decision | Qualification result |
| --- | --- | --- |
| Existing PostgreSQL 16 + Psycopg | ADOPT / WRAP | Already qualified; retains durable local persistence and the replacement boundary. |
| ANIMA canonical memory/lifecycle/retrieval/routines | BUILD | Required to retain memory type, provenance, precedence, correction, expiry, retraction, isolation, and the no-authority invariant. |
| PostgreSQL full-text search | ADOPT / WRAP | Small local lexical index; canonical records survive index deletion and rebuild. |
| Mem0 OSS 2.0.19 | DEFER / WRAP candidate | Apache-2.0, Python >=3.10, PostgreSQL/pgvector and `infer=False` support are present. Default extraction/conflict behavior is not canonical ANIMA semantics, and current OSS/server sources document telemetry that must be explicitly disabled. Not installed in Phase 3. |
| FastEmbed 0.8.0 | DEFER | Lightweight ONNX approach and Python >=3.10 are promising, but model download/cache, CPU/RAM, and native ARM64/Pi execution were not qualified. No external embedding is introduced. |
| pgvector | DEFER | Existing extension remains available, but no model/dimension or vector index is adopted before local ARM64/privacy qualification. |
| LangGraph | DEFER / REJECT as foundation | Agent/runtime persistence overlap; cannot own ANIMA lifecycle or authority semantics. |
| Letta / MemFS | DEFER / REJECT as foundation | Agent-owned memory/runtime and broader persistence boundary exceed Phase 3. |
| Graphiti | DEFER | LLM/embedding temporal graph enrichment belongs to later learned context, not governed canonical memory. |
| River 0.24.2 | DEFER | BSD-3-Clause online ML is maintained, but direct deterministic aggregation is smaller and sufficient for current routines. |
| Python standard-library statistics | ADOPT | No extra dependency; deterministic routine aggregation and confidence calculation. |

Primary Phase 3 sources are linked in [`docs/PHASE-3-GOVERNED-MEMORY.md`](PHASE-3-GOVERNED-MEMORY.md). Recheck Mem0, FastEmbed, River, model files, and PostgreSQL/pgvector before adopting a semantic index, native Pi deployment, or agent/runtime integration.

## Phase 4 policy and identity boundary

- Date checked: 2026-08-29
- Selected policy image: `openpolicyagent/opa:1.20.1@sha256:39daf255ae7f25d81103f03a0c18308a50b7b5bb67907bed6166f70e24a970ff`
- Image manifests observed with `docker buildx imagetools inspect`: Linux amd64 `sha256:4ea5e3f5c5fa36f300448c701d48a5411ee3b7eafe399ec58cf5fb777853ad86`; Linux arm64 `sha256:909992a577c26e3cc5ce996e81760c0786cf55bb5c3dc3f31476f76a30827427`.
- License: Apache-2.0, verified from the upstream repository license.
- Maintenance: v1.20.1 was the current stable upstream release observed on 2026-08-29; the release fixed a v1.20.0 numeric-comparison regression.
- Fit: local HTTP evaluation, structured JSON result, Rego tests, filesystem policy loading, and bundle support match ANIMA's replaceable policy boundary.
- Runtime: the official image is small enough for a Pi-class local service; this checkpoint measures the host runtime, not native Pi runtime.
- Security boundary: Compose binds OPA to loopback, mounts policies read-only, configures no remote bundle or decision-log destination, and routes all evaluator errors to ANIMA fail-closed denial.
- Restart/replacement path: replace the image with another pinned OPA release or replace `OpaPolicyClient` with another evaluator implementing the ANIMA contract; policy version/digest remains attached to every decision.
- Sources: [OPA release](https://github.com/open-policy-agent/opa/releases/tag/v1.20.1), [OPA integration](https://www.openpolicyagent.org/docs/integration), [OPA Docker](https://www.openpolicyagent.org/docs/deploy/docker), [OPA bundles](https://www.openpolicyagent.org/docs/management-bundles), [OPA tests](https://www.openpolicyagent.org/docs/policy-testing), [Cedar](https://docs.cedarpolicy.com/auth/authorization.html), [OpenFGA](https://openfga.dev/docs/concepts), and [Casbin](https://casbin.org/).

| Candidate | Disposition | Result |
| --- | --- | --- |
| OPA/Rego 1.20.1 | ADOPT / WRAP | Local structured evaluator; ANIMA owns contracts, risk, identity, audit, and fail-closed behavior |
| Cedar | REFERENCE | Typed policy/schema lessons; native output is allow/deny |
| Casbin | REFERENCE / REJECT as core | Embedded RBAC/ABAC is useful but not a material fit improvement for the required four-way contextual result |
| OpenFGA | DEFER / REJECT for Phase 4 | ReBAC tuple service is unnecessary for current household policy scale |
| Direct Python | BUILD for wrapper/contracts only | Used for ANIMA-owned semantics, not as a replacement for policy-as-code evaluation |
