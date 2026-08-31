# Phase 11 evidence

## Publication

- Implementation checkpoint: `17252304a4f0642bb654ec612cfcb55a01411804`.
- Implementation hosted CI: `33442439042`, success on the exact SHA.
- Governed closure checkpoint and final hosted CI: recorded after closure push.

## Architecture evidence

- `ExternalResult` carries normalized bounded data, provider operation/time,
  freshness, attribution, source references, and explicit
  `EXTERNAL_UNTRUSTED` trust.
- `BoundedHttpClient` enforces HTTPS, exact allowlisted hosts, no redirects,
  GET/POST only, fixed relative paths, private/loopback IP rejection, timeout,
  response-size limits, and audit records that contain field names/digests and
  byte/status/latency metadata but no secret/header values.
- Core-owned Calendar and notification safety profiles enter Phase 9. Calendar
  success requires deterministic provider identity and matching provider
  readback; notification success is provider acceptance only, not human
  delivery/read. Connector claims cannot independently establish verified
  consequential success.
- Brave and Google Calendar credentials are independently gated and never part
  of model-visible schemas. Weather, recipes, and synthetic ntfy qualification
  remain independently usable.

## Validation

- `uv sync --locked --dev`: PASS; 67 locked packages resolved.
- Full pytest: `130 passed`.
- Focused external/action tests: `25 passed`.
- Ruff format/check on changed Phase 11 files: PASS.
- Strict mypy: `Success: no issues found in 40 source files`.
- Pinned OPA container: `PASS: 4/4`.
- Package sdist/wheel and `git diff --check`: PASS.
- PostgreSQL Phase 1–5 and 7–10 harnesses: PASS.
- Isolated real HA Phase 6 harness: PASS.
- Live synthetic: Open-Meteo PASS, TheMealDB PASS, ntfy no-cache/Firebase-disabled PASS.
- Brave and Google Calendar: `EXTERNAL_RESOURCE_GATE`; no credentialed live claim.
- Public safety: PASS; no secrets, private runtime state, or credentials added.

## Evidence limits

Evidence is x86-64 Python 3.12 local/CI execution and synthetic/public
provider traffic. It does not establish native ARM64/Pi qualification,
physical-home behavior, commercial production approval, production capacity,
Google OAuth commissioning, credentialed Brave behavior, or human notification
delivery/read. Phase 12 behavior was not implemented.
