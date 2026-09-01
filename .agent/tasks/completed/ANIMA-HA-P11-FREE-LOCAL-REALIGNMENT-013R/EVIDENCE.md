# Evidence packet

## Scope and architecture

- Private pinned SearXNG provides bounded web and product search over a fixed
  JSON API and fixed engine set (`duckduckgo`, `wikipedia`). It has no public
  instance, image proxy, or Valkey requirement; local qualification uses a
  loopback-only host port.
- OpenStreetMap Overpass provides read-only POI discovery. ANIMA maps a
  bounded category enum to tags; raw Overpass query text is not model input.
- `src/anima_ha/calendar.py` and migration `0012_local_calendar.sql` provide
  household-scoped PostgreSQL calendar CRUD, deterministic trusted
  idempotency, creator provenance, optimistic versions, and terminal cancel.
- Only exact Core-approved calendar mutation IDs receive
  `POLICY_GATED_INTERNAL`; arbitrary plugins remain coordinated consequential.
  Physical/provider actions remain Phase 9-coordinated.

## Fresh validation

- `uv sync --locked --dev`: PASS in local-filesystem reproduction.
- Ruff format/check: PASS.
- strict mypy: PASS.
- pytest: PASS, 134 tests.
- OPA: PASS, 4/4.
- package sdist/wheel: PASS.
- ordered migration initial/repeat: PASS; `0012_local_calendar` applied once
  and skipped on repeat.
- SearXNG pinned container: PASS/healthy with no Valkey; live synthetic web
  and product JSON queries pass.
- Overpass live synthetic restaurant query: PASS.
- actual AgentRuntime local calendar mutation: PASS; one event persisted,
  trusted invocation context supplied provenance/idempotency, and no Phase 9
  physical action record was created.
- `git diff --check`: PASS.
- public safety: PASS; no secrets, tokens, private runtime state, or generated
  artifacts included.

## Evidence limits

Evidence is local x86-64 and synthetic/public-provider traffic. It does not
claim native ARM64/Pi, production-scale capacity, physical-home behavior,
high-risk external writes, or human notification delivery. Phase 12 was not
implemented.

## Publication

- Implementation checkpoint: `558c689cac96f3bddbd636b4d1b9e20d055b221d`.
- Implementation hosted CI: `33458814906`, success on the exact SHA.
- Final governed checkpoint and hosted CI are recorded after Authority closure
  publication and final exact-SHA validation.
