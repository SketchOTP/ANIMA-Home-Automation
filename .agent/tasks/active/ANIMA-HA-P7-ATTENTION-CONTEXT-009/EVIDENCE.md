# Evidence — ANIMA-HA-P7-ATTENTION-CONTEXT-009

## Starting state

- Starting governed SHA: `e1488d9a2d6280945cc2fd8bdba435733f0ba287`.
- Accepted Phase 6 CI: `33284537147`.
- Branch/remotes: clean `main`, exact with `origin/main` at task start.
- Retrieval confidence: `ADEQUATE` after Authority kernel, accepted Phase 1–6 boundaries, implementations, migrations, callers, tests, and external-primary-source review.

## Dependency decision

- BUILD: typed attention profiles/predicates, cursor/decisions/cooldown/rate/aggregation, ReasoningTrigger, ContextBroker/ContextPacket, trust/egress, replay/profile comparison.
- ADOPT / REUSE / WRAP: PostgreSQL, Psycopg, Phase 1 journal/truth, Phase 2 graph, Phase 3 memory/routines, Phase 4 identity contracts, Phase 5 registry.
- REFERENCE: CloudEvents SQL v1.0.0, CEL, OpenTelemetry Context/Baggage.
- DEFER: CEL runtimes, NATS/JetStream, provider tokenizer, embedding search.
- PROHIBIT: arbitrary executable attention scripts, LLM attention, behavioral automations.
- New runtime/service dependencies: NONE.

## Target evidence

- Migration `0008_attention_context.sql`: PASSED clean/repeat application on PostgreSQL 16.
- Focused/unit tests: PASSED. Guaranteed bypass, cooldown, rate, duplicate/no-change, unclassified critical fail-toward-trigger, exact 10,020-event replay, sparse exterior-door/user-request context, nighttime-motion uncertainty/routine context, budget pruning, secret redaction, untrusted content, degraded source, and profile comparison are covered.
- PostgreSQL high-volume harness: PASSED.
  - Canonical source events: 10,020 = 10,000 ordinary + 20 guaranteed.
  - Midstream restart point: 5,000; durable resume processed remaining 5,020.
  - Expected/actual aggregates: 4/4.
  - Expected/actual guaranteed triggers: 20/20.
  - Expected/actual total triggers: 24/24.
  - Aggregate source references: all 10,000 ordinary event IDs retained.
  - Pure replay/live trigger UUID equivalence: PASSED.
  - Context relevance, bedroom exclusion, Truth/memory/routine/identity/tool context, secret/egress boundary: PASSED.
  - Persisted digest and PostgreSQL restart: PASSED.
  - Profile comparison: A 24 triggers versus B 28; guaranteed loss zero; actual packet bytes reported.
- Replay CLI over 10,020 journal rows: PASSED; 10,024 decisions, 24 triggers/packets, `side_effects: NONE`.
- Simulator attention scenario: PASSED; 101 sources, guaranteed event preserved, `authority_surface: attention-only`, no side effects.
- Measured full Phase 7 PostgreSQL harness on current x86-64 host: 31.00 seconds wall, 114,468 kB max process RSS. This includes journal insertion, processing, context comparison, and database restart; it is not steady-state latency or Pi evidence.
- Existing infrastructure idle sample after validation: PostgreSQL 0.01% CPU / 21 MiB; OPA 0.00% / 12.54 MiB. Phase 7 adds no continuously running service, so no infrastructure resource delta was introduced.

## Regression evidence

- Locked fresh local-filesystem sync: PASSED (`uv sync --locked --dev`). This avoids the known SFTP/GVFS virtual-environment canonicalization limitation.
- Ruff format/check: PASSED.
- Strict mypy: PASSED, 32 source/test/Phase 7 harness files.
- Pytest: PASSED, 50 tests.
- OPA tests: PASSED, 4/4.
- Package sdist/wheel build: PASSED.
- Phase 1 PostgreSQL: PASSED.
- Phase 2 PostgreSQL graph: PASSED.
- Phase 3 PostgreSQL memory/routines: PASSED.
- Phase 4 PostgreSQL/OPA policy: PASSED.
- Phase 5 PostgreSQL/OPA/native/MCP: PASSED.
- Phase 6 real Home Assistant Core 2026.8.2 container: PASSED; real WebSocket discovery/events, provider mapping, policy-gated virtual action verification, reconnect/gap, invalid auth, disable/re-enable, PostgreSQL persistence.
- Public-safety review: PASSED; candidate file review, secret/private-key pattern scan, large-file scan, and Git diff check found no publishable credential/private runtime artifact. Synthetic placeholders contain no live secret.
- Hosted CI: pending implementation checkpoint push.

## Evidence ladder and limits

- E4_REGRESSION_PROTECTED: unit/static/build plus Phase 1–6 regression coverage.
- E3_TARGET_TESTED: x86-64 PostgreSQL high-volume/restart/replay and isolated real-HA regression.
- E2_REPRODUCED: simulator and replay CLI.
- E1_OBSERVED: ARM64 package/image metadata inherited from accepted dependencies; no native Phase 7 ARM64/Pi execution.
- No Luna, cloud model, agent reasoning, tool invocation by cognition, autonomous household action, new physical-home behavior, or Phase 8 evidence exists.
