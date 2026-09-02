# Phase 12 H3 evidence

## Publication

- Starting governed checkpoint: `7524cd67daee305e8e4bc4446623fa022fee0cd2`; hosted CI `33655737686` passed.
- Implementation checkpoint: `37116b03c65bfac54a5261f30160e9030aa6011c`; hosted CI `33671817841` passed on that exact SHA.
- Final governed checkpoint: the governance commit containing this packet and the synchronized Authority/docs closure. Its exact SHA and hosted CI are recorded in the final handoff and Notion readback after push; the packet does not make a self-referential hash claim.

## Architecture and target evidence

- `create_app()` composes the real PostgreSQL graph, Truth, Event Journal,
  Attention, Context Broker, AgentRuntime, PluginManager/Tool Gateway, OPA,
  durable-task, local-calendar, and Phase 9 action dependencies when configured.
- `CoreUICommandGateway` routes task, calendar, and home-control mutations
  through the existing policy/tool boundaries. No API handler calls a domain
  service directly.
- `CoreConversationPipeline` routes the direct-user event through Journal →
  Attention → ContextPacket → AgentRuntime. The deterministic target reports
  linked event, trigger, context-packet, correlation, causation, and episode
  IDs with `fallback_enabled=false`; only the model response is scripted.
- Policy role is resolved from commissioned graph PERSON metadata for every
  governed operation. Missing roles fail closed; browser payloads cannot set a
  role or provenance.
- HA OAuth state uses server-side expiry/single use plus an initiating-browser
  nonce cookie. Mismatch, expiry, and replay are rejected.
- Active external providers receive `ExternalAuditJournalSink(journal)` and
  capability projections distinguish available, degraded, and unavailable.
- Migration `0014_ui_preferences.sql` stores only allowlisted presentation
  preferences. Calendar projections include event `version` for conflict-safe
  update/cancel operations.

## Validation

- `uv sync --locked --dev`: PASS.
- `scripts/validate.sh`: PASS — 166 Python tests, Ruff, strict mypy, OPA 7/7.
- `uv build --sdist --wheel`: PASS.
- Frontend `pnpm test`: PASS — 2 tests.
- Frontend TypeScript/Vite production build: PASS.
- Playwright: PASS — 9 tests across desktop, tablet, and phone.
- PostgreSQL migration initial/repeat: PASS — no pending migrations on repeat.
- `verify_phase12_commissioned_runtime.py`: PASS — real PostgreSQL/OPA/Core
  composition, graph identity, policy-gated task/calendar mutation, and
  Journal → Attention → ContextPacket → AgentRuntime trace.
- `verify_phase12_final_ux.py`: PASS — configured `create_app()` composition,
  real task mutation, conversation trace, settings persistence, and explicit
  HA commissioning gate.
- `git diff --check`: PASS.
- Public-safety scan: PASS — no credentials, private keys, runtime state, or
  secret material added.

## Browser evidence

Screenshots were captured from the running application with synthetic data and
the explicit test-auth flag, then MIME-verified as PNG:

- `docs/assets/anima-home-desktop.png`
- `docs/assets/anima-home-tablet.png`
- `docs/assets/anima-home-phone.png`

The Playwright matrix also passed same-origin API/network posture, dashboard,
conversation, navigation, and responsive viewport checks. Browser persistent
storage remains unused; restricted product content is not persisted by the UI.

## Evidence limits

No live Home Assistant OAuth consent, physical-home behavior, production TLS,
live Luna credential turn, native ARM64/Pi execution, or real household-data
claim is made. HA remains an explicit commissioning gate on this host. Phase
13 Voice Software Path was not implemented.
