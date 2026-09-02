# Phase 12 closure evidence

## Published checkpoints

- Starting accepted Phase 11 checkpoint: `918365ce7c6145780112a808411d750fb0e289eb` (CI `33562645002`).
- Phase 12 implementation checkpoint: `208b7e546d8485539d2ae06427d268af116f9ceb` (CI `33580734640`).
- The final governed checkpoint and CI are recorded in the post-publication Authority/Notion handoff; this file deliberately does not claim a self-referential hash before its enclosing commit exists.

## Integrated evidence

- `src/anima_ha/ui_runtime.py` composes the existing PostgreSQL journal, Attention, Context Broker, AgentRuntime, PluginManager/Tool Gateway, OPA policy service, durable task and local-calendar plugins, and Phase 9 action coordinator.
- Configured `create_app()` selects `PostgresHouseholdReadModel` plus `CoreUICommandGateway` and `JournalConversationIngress`; it does not select `UnavailableCommandGateway` or the echo fallback when `ANIMA_DATABASE_URL` is present.
- The real AgentRuntime integration test exercises journal-triggered Attention → ContextPacket → scripted model episode and records event, trigger, context-packet, correlation, causation, and episode identifiers.
- The task mutation test invokes `TaskNativePlugin` through `PluginManager` and the policy gateway, proving the UI adapter does not call `TaskService` directly.
- Real PostgreSQL composition smoke test produced `CoreUICommandGateway`, `JournalConversationIngress`, and `PostgresHouseholdReadModel`; the full PostgreSQL composition pipeline returned a scripted AgentRuntime response with the linked journal/attention/context/episode trace.

## Validation

- `uv sync --locked --dev`: PASS.
- `anima-validate`: PASS — 160 Python tests, format, Ruff, strict mypy.
- `scripts/validate.sh`: PASS — backend gate and OPA 4/4.
- `uv build --sdist --wheel`: PASS.
- TypeScript, frontend unit tests, and Vite production build: PASS.
- Playwright desktop/tablet/phone and same-origin/privacy scenarios: PASS — 9 tests.
- Docker Compose config and `Dockerfile.ui` image build: PASS.
- `git diff --check`: PASS.
- Public-safety scan of changed source/docs/assets: PASS; no credentials, private keys, runtime state, or secrets were added.

## Screenshots

Actual synthetic-data screenshots are committed at:

- `docs/assets/anima-home-desktop.png`
- `docs/assets/anima-home-tablet.png`
- `docs/assets/anima-home-phone.png`

## Evidence limits

- Real Home Assistant OAuth consent/token exchange, live household commissioning, production TLS, native Raspberry Pi execution, and physical-home behavior remain unclaimed.
- The deterministic integrated composition uses the real AgentRuntime and a scripted model adapter; it does not claim a live Luna turn.
- The UI test-auth fixture remains available only under explicit `ANIMA_UI_TEST_AUTH=1` and is not acceptance evidence for production cognition.
- Phase 13 voice behavior was not implemented.
