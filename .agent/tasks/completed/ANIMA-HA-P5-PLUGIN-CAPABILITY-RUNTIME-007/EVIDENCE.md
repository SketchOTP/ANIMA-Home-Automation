# Evidence — ANIMA-HA-P5-PLUGIN-CAPABILITY-RUNTIME-007

## Checkpoint

- Starting accepted Phase 4 checkpoint: `50ea9c73e31b2037120da5d12e04555fa08b1da5`
- Phase 4 accepted CI: `33271197523`
- Phase 5 implementation checkpoint: `c186c34bcf93e9ff03d39c3e966fcb540583d478`
- Phase 5 CI: `33277823326`, passed on the exact implementation SHA
- Final closure metadata is recorded after the implementation checkpoint; it does not replace the accepted Phase 4 prerequisite or create a self-referential acceptance loop.

## Dependency decisions

| Candidate | Decision | Evidence |
| --- | --- | --- |
| Official MCP Python SDK v2 `2.1.1` | ADOPT / WRAP | PyPI release and official SDK inspected 2026-08-29; MIT, pure-Python wheel, stdio and Streamable HTTP client/server boundary; pinned in `pyproject.toml`/`uv.lock`. |
| `jsonschema 4.26.0` | ADOPT / WRAP | MIT, Python >=3.10, Draft 2020-12 and production/stable metadata; pinned and wrapped with ANIMA bounds/no-ref policy. |
| `importlib.metadata.entry_points()` | ADOPT | PyPA standard discovery; dedicated `anima_ha.plugins` group; discovery does not enable plugins. |
| Direct ANIMA manifest/registry | BUILD | Required for identity, lifecycle, risk, policy, secrets, configuration, audit, and replacement ownership. |
| FastMCP | REFERENCE / DEFER | Official `MCPServer` was sufficient for the reference server. |
| Pluggy | REFERENCE / DEFER | In-process hooks do not provide MCP transport or process/secret isolation. |
| Subprocess MCP | ADOPT | Bounded crash/timeout and reconnect containment for optional plugins. |
| Container-per-plugin | DEFER | No measured need for Phase 5 references; subprocess is explicitly not a malicious-code sandbox. |
| Runtime install/marketplace/update | PROHIBITED / DEFER | No package-manager or arbitrary executable installation API exists. |

## Validation

- `uv sync --locked --dev`: PASSED in a fresh local-disk checkout.
- Ruff format/check: PASSED.
- Strict mypy: PASSED, 25 source files.
- Pytest: PASSED, `31 passed`.
- OPA policy regression: PASSED through existing Phase 4 validation.
- Migration `0006_plugin_runtime`: PASSED; repeat migration was a no-op.
- Local x86-64 PostgreSQL + OPA + MCP integration: PASSED — native and MCP healthy states, failing/incompatible states, policy-gated invocation, disable/re-enable, persisted restore, and declared event ingress.
- PostgreSQL restart: PASSED — plugin/tool counts `4|2` before and after controlled restart.
- Simulator `anima-sim --once --scenario plugins`: PASSED — native `HEALTHY`, MCP `HEALTHY`, policy-gated synthetic invocation `SUCCESS`, disable removed one tool.
- Fresh checkout from `c186c34…`: PASSED — locked sync, validation, and package build.
- GitHub Actions `33277823326`: PASSED on `c186c34…`.
- Public safety: PASSED — no committed raw secrets or generated runtime state; only documented development placeholders/fake test values.

## Acceptance evidence

- Versioned/stable manifests, compatibility, duplicate/collision/schema bounds: unit evidence PASSED.
- Native entry-point discovery and separate enablement: unit evidence PASSED.
- Native and MCP tools normalize to namespaced canonical descriptors: unit/local MCP evidence PASSED.
- All invocation paths require Phase 4 policy; denial/confirmation/stronger-auth prevent runtime invocation: unit/integration boundary PASSED.
- MCP stdio discovery and structured normalized call: local subprocess evidence PASSED.
- Streamable HTTP uses the same adapter boundary but was not run against a permanent remote endpoint: NOT RUN as external runtime evidence; explicitly deferred with no remote service added.
- Startup failure, crash, timeout, bounded retry configuration, and healthy-plugin independence: unit/integration PASSED.
- Declared-only fake secret and sanitized child environment: unit evidence PASSED; raw values absent from persisted plugin/tool rows and journal payloads.
- Configuration is schema validated and persisted per plugin; global household state is not passed automatically: unit/code-boundary evidence PASSED.
- Declared plugin event became a Phase 1 envelope with plugin provenance; undeclared ingress is rejected: unit/integration PASSED.
- Phase 1–4 regressions: PASSED through existing harnesses and CI.

## Evidence limits

Evidence levels: `E4_REGRESSION_PROTECTED` for unit/static/build and Phase 1–4 regressions; `E3_TARGET_TESTED` for synthetic x86-64 PostgreSQL/OPA/MCP integration; `E2_REPRODUCED` for simulator/fresh-checkout reproduction; `E1_OBSERVED` for ARM64 package metadata. No Home Assistant, Luna, physical action, real external service, or malicious-code sandbox claim is made. Native Raspberry Pi execution and resource qualification remain future work. Direct SFTP-path builds remain blocked by the known `.venv` symlink limitation; local-disk reproduction passes.
