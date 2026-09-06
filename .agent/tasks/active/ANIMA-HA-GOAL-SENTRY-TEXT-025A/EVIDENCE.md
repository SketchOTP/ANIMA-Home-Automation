# Evidence — Goal SENTRY text operation 025A

Status: `COMPLETE — PENDING ARCHITECT ACCEPTANCE`.

Starting checkpoint: `851187c8ca7e28d7823c76bcdaa604ed9d061173`.

The bounded live-result implementation is present in
`src/anima_ha/live_results.py`, `src/anima_ha/sentry_service.py`, and
`src/anima_ha/ui_api.py`. The React conversation view polls the authenticated
request route and labels the responding intelligence SENTRY.

Local checks completed so far:

- Python bytecode compilation: pass.
- `git diff --check`: pass.
- TypeScript check: pass.
- frontend tests: 4 pass.
- production Vite build: pass.

The mounted-checkout Python environment could not be recreated because the
host disk quota was exhausted while installing the locked mypy wheel. This is
a validation limitation, not a product claim.

Hosted exact-head validation passed on implementation head
`97be56fac54a848982d5767fe792ea66083412e9` in CI `34055080097`. The published
artifact is `9995888935` with digest
`sha256:9c077a0ed861bee7378ba8e79178248eab16243f1dfa80a2a0448ced29630833`.
The run passed the existing deterministic, SENTRY/MCP, Phase 14,
ARM64/container, frontend, and H5 browser stages.

The durable/content boundary remains explicit: result text is delivered only
through the bounded PostgreSQL notification channel and short-lived UI memory;
the durable request record retains status and metadata, not response text.
The actual external SENTRY host is not claimed as live evidence by this
increment and remains a later runtime/resource gate.
