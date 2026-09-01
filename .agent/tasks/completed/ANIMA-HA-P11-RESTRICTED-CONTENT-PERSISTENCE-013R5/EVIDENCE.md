# Evidence — restricted external-content persistence

Date: 2026-09-01

## Scope and starting state

- Directive: `ANIMA-HA-P11-RESTRICTED-CONTENT-PERSISTENCE-013R5`.
- Starting repository: `/srv/ATLAS/100_ACTIVE/Projects/ANIMA Home Automation`.
- Starting branch/state: `main`, clean, `67b72bf52e1f45e33b9c35a1c0c89e87cf47f7ee == origin/main`.
- Prior hosted CI: `33509333301` passed on that exact starting SHA.
- No secrets, private keys, `.env` files, or runtime credentials were inspected, copied, hashed, committed, or logged.

## Publication checkpoints

- Implementation checkpoint: `b810c853b47470c4395dd1a5731e59da98ae41a5`.
- Hosted implementation CI: `33525400264` passed on that exact SHA.
- Governance closure checkpoint and final hosted CI are recorded below after
  the closure commit and push.

## Architecture correction

- `ContentPersistence` is Core-owned. Best Buy's normalized tool IDs are
  `EPHEMERAL_RESTRICTED`; raw plugin metadata cannot select `FULL_DURABLE`.
- `BestBuyProductProvider` is fixed-host, HTTPS-only, bounded read-only REST
  access to `api.bestbuy.com`, with only model-visible `query` and `count`.
  The API key is runtime-secret input only.
- Full restricted provider results remain in the active process for the current
  answer. Durable episode/tool/turn fields receive structural projections,
  content digests, provenance, trust, policy, and result counts only.
- Once a restricted result succeeds, the episode is tainted. The current caller
  receives `EpisodeRunResult.live_response_text`; the durable response is a
  `[CONTENT_NOT_DURABLY_RETAINED]` marker. Later tool requests are blocked with
  `RESTRICTED_EXTERNAL_CONTENT_SIDE_EFFECT_BLOCKED`, including reads.
- No 72-hour cleanup daemon, unrestricted provider cache, or Phase 12 behavior
  was added.

## Fresh evidence

- Locked environment: `uv sync --locked --dev` passed.
- Changed-scope Ruff format/check passed for six changed files.
- Strict mypy passed: 42 source files.
- Full pytest passed: 145 tests. A separate `anima-validate` run reproduced a
  known intermittent Phase 5 MCP stdio startup failure; the isolated test and
  the complete rerun passed, and no Phase 5 source was changed.
- OPA passed: `4/4` using the pinned OPA 1.20.1 container.
- Package build passed for sdist and wheel.
- `git diff --check` passed.
- Real PostgreSQL verifier passed. Synthetic product/price sentinels appeared
  in the live response, while database-wide text/JSON/JSONB scan and in-process
  JSON export scan returned zero occurrences. Durable rows retained only
  structural examples and a response marker. Duplicate trigger replay returned
  no reconstructable live response.
- Phase 10 PostgreSQL harness passed lifecycle parity, stale-worker rejection,
  cancellation, AgentRuntime task scheduling, fresh scheduled cognition, future
  Phase 9 routing, provenance separation, and fresh external value evidence.

## Provider/resource status

- Best Buy deterministic normalization and manifest tests passed, including
  fixed host/path, bounded fields, attribution, external price provenance,
  secret-free audit representation, and explicit missing-key behavior.
- `BEST_BUY_API_KEY` is absent. No live Best Buy query is claimed; the honest
  status is `EXTERNAL_RESOURCE_GATE_BEST_BUY_KEY`.
- Walmart remains preserved but deferred as
  `DEFER — ENTITLEMENT_CLARIFICATION`. There is no Walmart fallback.

## Limitations

- The host has no `pg_dump`; the required export scan used an in-process JSON
  export of every public `anima_*` table instead.
- The SFTP/GVFS workspace cannot reliably launch Python; validation used the
  allowlisted local filesystem reproduction above.
- Native ARM64/Pi, physical-home, production-scale, and credentialed Best Buy
  live evidence remain unclaimed.
