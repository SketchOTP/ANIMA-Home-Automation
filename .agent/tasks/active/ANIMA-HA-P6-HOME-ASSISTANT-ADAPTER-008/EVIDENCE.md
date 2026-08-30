# Evidence — ANIMA-HA-P6-HOME-ASSISTANT-ADAPTER-008

Status: target implementation and local validation passed; GitHub checkpoint/CI pending.

## Starting state

- Starting SHA: `b426d66e7293a132dcdb4abaa96bc7594cdf7b73`
- Working tree: clean, `main...origin/main`
- Accepted prerequisite: Phase 5, CI `33277980009`
- Retrieval confidence: `ADEQUATE`

## Target evidence

- Real HA container: `2026.8.2`, pinned index digest `sha256:56690a89c79a0de98035e1719f8324a92d5859c1192ff45adb0230ea81cb42a5` — `E3_TARGET_TESTED` on x86-64.
- Discovery: 11 states, 60 service domains, 3 areas, 1 device, 11 entities in the deterministic fixture run.
- Real WebSocket state/registry events, KNOWN/UNKNOWN/UNAVAILABLE normalization, deterministic duplicate handling, snapshot buffer race, provider mapping/unmapped/many-to-one behavior: `PASSED`.
- OPA deny/confirmation/strong-auth short-circuit before HA: `PASSED`.
- Real low-risk `input_boolean.turn_on` service plus fresh observed state: `PASSED`.
- Deliberate acknowledged-but-unobserved outcome: `VERIFICATION_FAILED`, `PASSED`.
- Stop/restart, OFFLINE, bounded reconnect, resubscribe, full reconciliation, explicit history gap, invalid-auth `AUTH_FAILED`, disable/re-enable, and persisted restore: `PASSED`.
- Secret/token/password absence from persistence/status/output and bounded attribute filtering: `PASSED`.
- Resource sample: HA container `0.00% CPU`, `308.6 MiB`; full Python harness process `104320 kB` RSS on current x86 host. This is not Pi evidence.

## Regression/static evidence

- `ruff format --check src tests`: `PASSED`
- `ruff check src tests`: `PASSED`
- strict `mypy src tests`: `PASSED`, 27 source files
- `pytest`: `PASSED`, 43 tests
- migrations repeated with no pending change: `PASSED`
- Phase 1–5 PostgreSQL/OPA/MCP integration harnesses: `PASSED`
- Phase 6 synthetic simulator normalization: `PASSED`, no network used
- Package build, fresh-checkout reproduction, public safety, final GitHub CI: pending checkpoint.

## Evidence limits

- Native ARM64/Pi: `NOT RUN`; metadata/manifests only.
- Physical devices/household: `NOT RUN`; HA virtual/demo entities only.
- Customer OAuth, security access actions, Luna, Phase 7 Attention/Context Broker: `NOT APPLICABLE` to this directive.
