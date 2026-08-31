# Phase 11 external gate-closure evidence

## Publication

- Starting governed checkpoint: `0aaad4a287efaf26d02afac7f1d55d1edbbc0405`; hosted CI `33442786332` passed.
- Implementation checkpoint: `dde3e2bc42fc5004ddf06690ddbd9dc9941999f8`; hosted CI `33445636772` passed on the exact SHA.
- Evidence amendment checkpoint: `f069e5c0d1d42d0a74eba3267f8393f325509429`; hosted CI `33446725375` passed on the exact SHA.
- Final governed evidence checkpoint: `abc9bece8b4827828ca759993191a1f20338d442`; hosted CI `33446946952` passed on the exact SHA.

## Calendar OAuth

- `GoogleCalendarCredentialProvider` is an ANIMA-owned adapter over the pinned `google-auth==2.57.0` stack.
- Cached valid-token, expired-token refresh, newly constructed restart refresh, revoked/invalid refresh failure, and same-request HTTP 401 refresh retry pass in `tests/test_external.py`.
- Calendar uses the exact owned-calendar scope `https://www.googleapis.com/auth/calendar.events.owned` and deterministic provider event identity. Auth refresh retries preserve the same request/event identity.
- No commissioning helper was needed: the existing operator-controlled SecretBroker environment is the approved secret source. No token is printed or persisted by this change.

## AgentRuntime and durable follow-up

- `tests/test_phase11_integration.py` drives the actual `AgentRuntime` and `PluginManager` through one broad catalogue for weather, recipe, web research, and place selection.
- The same test proves hostile provider text remains `EXTERNAL_UNTRUSTED` into the next scripted cognition turn and cannot add a tool or capability.
- The same actual AgentRuntime schedules a declarative durable task through `TaskNativePlugin`; a fresh worker instance dispatches the guaranteed `scheduled_reasoning_due` event; a new AgentRuntime episode receives a distinct ContextPacket ID and performs a fresh external read.
- The PostgreSQL Phase 10 harness now extends that path: the initial AgentRuntime episode reads synthetic weather value `17`, persists the task through PostgreSQL, restart-mode scheduled cognition reads fresh value `23`, and the future consequential action still traverses Phase 9. The provider remains a deterministic MockTransport fixture, not a live external provider or live Luna behavior.

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
- PostgreSQL durable-task harness: PASS, including lifecycle parity, stale-worker rejection, cancellation cleanup, idempotency/replay, lease recovery, fresh ContextPacket, fresh external value, and future Phase 9 action.
- Repository-wide Ruff format/check remains non-clean only because the pre-existing Phase 5 evidence script `scripts/verify_phase5_plugins.py` has unrelated formatting/import/line-length violations; no unrelated file was changed.
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
