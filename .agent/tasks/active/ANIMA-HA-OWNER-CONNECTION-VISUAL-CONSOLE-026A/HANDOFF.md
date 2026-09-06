# 026A — owner connection and visual console handoff

Disposition: **CONTINUE — bounded owner deployment retained; full Goal incomplete**.

The owner can now open the graphical ANIMA console against their actual HA
household, discover inventory, create rooms and commission the two existing
SenseGuards into matching spaces. The separate scoped Codex worker has returned
a real read response to the browser. Fifteen management sections are connected
to existing bounded APIs; unsupported operations are not generic HA/code tools.

The latest bundle fixes the queued-response identifier, trusted HA invocation
context, room-tool execution classification, stable multi-tab CSRF, and
all-or-nothing dashboard refresh. Policy, identity and physical verification
remain Core-owned. Worker ambiguity is retained without automatic retries.

## Validation at the implementation checkpoint

- Full backend validation: 278 pytest tests, strict mypy on 79 source files,
  Ruff format/check: PASS.
- Client/worker suite: 47 tests and 43 subtests: PASS.
- OPA: 9/9 PASS. Python sdist/wheel and Docker UI build/start/health: PASS.
- Frontend final focused suite: 23 desktop browser scenarios, TypeScript,
  static tests (5/5) and Vite: PASS. The recurring device-count failure was
  reproduced on the old bundle before the partial-refresh correction.
- Earlier same-increment responsive matrix: 36/36; PostgreSQL/OPA/Core browser
  suite and approval/rejection target passed in isolated environments.
- Hosted CI runs the repository-wide integration/ARM64/browser/container/safety
  suite on the published SHA and uploads the owner JUnit metadata with its
  existing evidence artifact. Exact run/SHA/artifact results belong to the
  publication handoff and Notion, not a self-referential source-file hash.

## Runtime and limits

The owner build serves `index-Cnn9LIRc.js`, SHA-256
`a0e84d4740bbdff67cd0c4a37de93661047661c072c62b09516a49344e5c1eb1`.
Its private connection and client files remain outside Git. The workstation
worker/tunnel services are separate from protected SENTRY and retain its tree.

Two failed room requests are negative evidence, not successful setup. Their
source-level routing defect is corrected and tested; a new live request must
check current state rather than replay either ambiguous turn. Upstream HA has
zero entities for the SenseGuards, so physical monitoring/alert delivery remains
unqualified despite correct room assignments. Several management mutations are
UI-only until their SENTRY execution profiles are qualified. See the complete
bounded matrix and evidence in `docs/OWNER-VISUAL-CONSOLE-026A.md` and this packet.

No resident SENTRY voice/persona completion, arbitrary code-editing agent,
unrestricted HA administration or `ANIMA_HA_PROTOTYPE_GOAL_COMPLETE` is claimed.
Phases 0–14 acceptance is unchanged. No historical Phase 15 scenario phase was
started, and no new resilience scope was introduced.
