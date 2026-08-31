# Phase 11 external gate-closure evidence

## Publication

- Starting governed checkpoint: `0aaad4a287efaf26d02afac7f1d55d1edbbc0405`; hosted CI `33442786332` passed.
- Implementation checkpoint: `dde3e2bc42fc5004ddf06690ddbd9dc9941999f8`; hosted CI `33445636772` passed on the exact SHA.
- Final governed checkpoint and final hosted CI are recorded after the governance closure push.

## Calendar OAuth

- `GoogleCalendarCredentialProvider` is an ANIMA-owned adapter over the pinned `google-auth==2.57.0` stack.
- Cached valid-token, expired-token refresh, newly constructed restart refresh, revoked/invalid refresh failure, and same-request HTTP 401 refresh retry pass in `tests/test_external.py`.
- Calendar uses the exact owned-calendar scope `https://www.googleapis.com/auth/calendar.events.owned` and deterministic provider event identity. Auth refresh retries preserve the same request/event identity.
- No commissioning helper was needed: the existing operator-controlled SecretBroker environment is the approved secret source. No token is printed or persisted by this change.

## AgentRuntime and durable follow-up

- `tests/test_phase11_integration.py` drives the actual `AgentRuntime` and `PluginManager` through one broad catalogue for weather, recipe, web research, and place selection.
- The same test proves hostile provider text remains `EXTERNAL_UNTRUSTED` into the next scripted cognition turn and cannot add a tool or capability.
- The same actual AgentRuntime schedules a declarative durable task through `TaskNativePlugin`; a fresh worker instance dispatches the guaranteed `scheduled_reasoning_due` event; a new AgentRuntime episode receives a distinct ContextPacket ID and performs a fresh external read.
- Existing Phase 10 PostgreSQL harness remains the authoritative PostgreSQL durable-task/lease/restart evidence. The new external-value comparison fixture is deterministic and in-memory; it does not claim a live external provider or live Luna behavior.

## Live-resource harness

`scripts/verify_phase11_external.py` now reports independently:

- Open-Meteo: `PASS`, class `LIVE_PUBLIC_SYNTHETIC`.
- TheMealDB: `PASS`, class `LIVE_PUBLIC_SYNTHETIC`.
- ntfy: `PASS`, class `LIVE_PUBLIC_SYNTHETIC` with no-cache/no-Firebase synthetic headers.
- Brave web, Place Search, and product-oriented search: each `EXTERNAL_RESOURCE_GATE_BRAVE_SEARCH`, class `EXTERNAL_RESOURCE_GATE` because `BRAVE_SEARCH_API_KEY` is absent.
- Google Calendar list and create/readback: each `EXTERNAL_RESOURCE_GATE_GOOGLE_CALENDAR`, class `EXTERNAL_RESOURCE_GATE` because the three OAuth references are absent.

No credentialed live claim is made. If credentials are injected later, the
harness performs the listed calls and preserves the same evidence classes.

## Fresh validation

- `uv build --sdist --wheel`: PASS.
- Full pytest: PASS, including the new Phase 11 integration tests.
- Changed-file Ruff format/check: PASS.
- Strict mypy: `Success: no issues found in 41 source files`.
- `git diff --check`: PASS.
- Public safety scan: PASS; only deliberate placeholder test strings contain token-like words, and no secret value/runtime artifact was added.
- Prior Phase 1–10 harnesses and isolated HA evidence remain accepted baseline evidence; no Phase 12 behavior was added.

## Limitations

The live Brave and Google gates remain blocked by missing operator credentials.
Evidence is local x86-64/Python 3.12 with deterministic provider fixtures and
public synthetic traffic; it is not native ARM64/Pi, physical-home,
production-provider, production-scale, or human-notification evidence. The
GVFS/SFTP path cannot reliably launch processes, so local `/srv/ATLAS` is the
reproduction path.
