# Evidence — ANIMA-HA-P4-IDENTITY-POLICY-006

## State

- Starting checkpoint: `66a6f94f999e9e5d1b0134945b3e6aae3a00d60d`, clean `main` tracking `origin/main`.
- Retrieval confidence: `ADEQUATE`.
- Implementation checkpoint and final governed checkpoint are recorded in the final GitHub and Notion readback after commit/push.

## Dependency decision

- OPA/Rego `1.20.1`: `ADOPT / WRAP`, Apache-2.0, pinned multi-architecture image index digest `sha256:39daf255ae7f25d81103f03a0c18308a50b7b5bb67907bed6166f70e24a970ff`.
- Cedar: `REFERENCE`; its native authorization result is allow/deny.
- Casbin: `REFERENCE / REJECT as core`; no material reduction for ANIMA's contextual four-way result.
- OpenFGA: `DEFER / REJECT for Phase 4`; ReBAC tuples are not required at this household policy scale.
- Direct Python: `BUILD` for ANIMA contracts, input/output wrapper, risk classification, identity aggregation, audit, and fail-closed behavior; not a replacement for policy-as-code evaluation.

## Implemented boundary

- Immutable identity evidence with expiry, issuer, provenance, assurance, and generic metadata.
- Deterministic assurance aggregation with explicit conflict handling; voice and local proximity cannot produce strong authentication.
- Semantic `ActionIntent` and risk classes including `UNKNOWN`; provider IDs and memory are not authorization inputs.
- Local OPA REST adapter with policy bundle version/digest and structured four-way decisions.
- Explicit, immutable-in-runtime autonomy configuration for low-risk and secure actions.
- Exact, expiring, single-use confirmation challenges.
- PostgreSQL persistence for evidence, policy bundles, confirmations, and decisions; existing Event Journal records guaranteed policy-decision audit events.
- Fail-closed denial on OPA timeout, outage, malformed response, or invalid result.
- Simulator policy scenario and Rego policy test matrix.

## Validation

- OPA `check`: `PASSED`.
- OPA `test --fail-on-empty`: `PASSED`, 4/4.
- PostgreSQL migration initial/repeat: `PASSED`.
- OPA health/startup/restart and controlled policy reload: `PASSED`.
- x86-64 PostgreSQL + OPA integration: `PASSED`; all required decision classes, stale Truth, conflicting identity, confirmation replay, role/memory boundary, and audit persistence covered.
- PostgreSQL restart persistence: `PASSED`; evidence counts remained `12|33|2` before/after restart.
- Phase 1 regression: `PASSED`; journal, projection retry, rebuild, and uncertainty statuses remain green.
- Phase 2 regression: `PASSED`; semantic graph, Truth binding, provider mapping, rename, and commissioning remain green.
- Phase 3 regression: `PASSED`; memory lifecycle, precedence, isolation, index rebuild/fallback, routines, and Truth separation remain green.
- Simulator: `PASSED`; policy scenario returned recognized-voice unlock `REQUIRE_STRONGER_AUTH` and admin install `DENY`.
- Ruff: `PASSED`.
- Strict mypy: `PASSED`, 23 source files.
- Pytest: `PASSED`, 24 tests.
- Package validation: `PASSED` from local-disk reproduction checkout; direct SFTP `uv build` remains blocked by the mount's `.venv` symlink limitation.
- Public-safety scan and clean-tree verification: performed before final push.

## Evidence limits

- PostgreSQL and OPA runtime evidence is synthetic and x86-64.
- Official OPA amd64/arm64 manifests establish portability metadata only; no native Raspberry Pi execution or resource measurement was performed.
- No physical identity, Home Assistant, Luna, real-door, real-house, plugin, action-execution, or Phase 5 claim is made.
