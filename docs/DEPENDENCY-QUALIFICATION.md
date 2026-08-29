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
