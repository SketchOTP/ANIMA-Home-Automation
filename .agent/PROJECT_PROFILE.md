# Project Profile

## Repository

- Name: ANIMA HA (Home Automation)
- Root: repository root
- GitHub: https://github.com/SketchOTP/ANIMA-Home-Automation
- Default branch: `main`
- Initial remote baseline: `088b267467fff93bfd225b9a94a6f4999759fb9f`
- Governance baseline commit: `6fbabc892f53876fd94614ccc531dc7478a80288`

## Strategic documentation

- Notion: https://app.notion.com/p/3c9833cb27ff81759597cdc69c59176c
- Governance: Authority 3.0 — Complete Installation Package

## Technical profile

- Languages: Python 3.12.x
- Frameworks: None adopted in Phase 0; modular monolith package boundary is established
- Major dependencies: `psycopg[binary]` 3.3.4; development tools are pinned in `pyproject.toml` and `uv.lock`
- Build/test commands: `uv sync --locked --dev`; `./scripts/validate.sh`; `uv build`
- Runtime environments: Target Raspberry Pi 5-class ARM64 controller; portable ARM64/x86-64 development/target environments
- Persistent substrate: PostgreSQL 16.15 through pinned pgvector 0.8.6 image digest; runtime-only migration metadata in Phase 0
- Local infrastructure: Docker Engine with Compose v2 and a named PostgreSQL volume

## Important integrations

- Home Assistant — household automation substrate and replaceable device/event adapter.
- Luna 5.6 with medium reasoning — primary cloud cognition model for the prototype.
- Modular plugins/connectors/MCP — customer-selectable external and household capabilities behind ANIMA-owned contracts.

## Compatibility commitments

- Event-driven cognition; no continuous raw household telemetry, camera streams, or ambient audio to the cloud LLM.
- Local-first / external-by-intent behavior with minimum necessary context.
- Deterministic policy outside the LLM; preference does not grant authority.
- No shell, unrestricted filesystem, package installation, source modification, self-update, policy mutation, raw-secret, or executable-tool capability for Anima.
- ARM64/x86-64 portability and Raspberry Pi 5-class target suitability.
- Prototype completion boundary: `ANIMA_HA_PROTOTYPE_GOAL_COMPLETE`.

## Safety / operational constraints

- Preserve evidence and append-only project history.
- Treat stale, unknown, conflicting, inferred, external, or acknowledged-but-unverified state according to explicit provenance/freshness semantics.
- Do not claim phase or goal completion from code presence, isolated tests, simulated evidence, or unavailable external/physical validation.
- No production deployment, public release, or post-prototype work under the current goal.

## Source-of-truth boundaries

- Notion: strategic/product understanding and normative SSOT.
- GitHub: committed implementation and governance evidence.
- Codex working tree/runtime: live technical state.
- `.agent/`: local project state and append-only evidence/history.
- `.agents/`: reusable Authority operating procedure.
