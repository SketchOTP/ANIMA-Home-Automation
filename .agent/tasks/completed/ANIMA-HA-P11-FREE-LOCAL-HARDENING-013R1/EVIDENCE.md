# Evidence — ANIMA-HA-P11-FREE-LOCAL-HARDENING-013R1

## Starting state

- Repository: `SketchOTP/ANIMA-Home-Automation`, `main`.
- Starting HEAD: `179f36e98c5c31595231bee8bbbd17a1ed89dea7`.
- Initial status: clean, `main...origin/main`.
- Scope: Phase 11 hardening only; Phase 12 not implemented.

## Calendar policy and persistence

- `CALENDAR_MANIFEST` mutation tools declare `LOW_RISK_HOME_CONTROL` and remain
  Core-approved `POLICY_GATED_INTERNAL`; physical/provider tools remain
  Phase 9 coordinated.
- Real pinned OPA + gateway: authenticated resident `ALLOW`, reason
  `LOW_RISK_HOME_CONTROL_AUTHORIZED`; anonymous direct mutation `DENY`, reason
  `POLICY_DEFAULT_DENY`.
- PostgreSQL target harness `scripts/verify_phase11_local_hardening.py`: create,
  replay, creation-key misuse conflict, get, list, update, stale-update
  conflict, cancel, repeat cancel, reconnect persistence, household isolation,
  trusted audit provenance, and zero `anima_actions` rows all passed.
- Calendar audit records contain bounded principal, episode, origin,
  tool-request, system-idempotency, changed-field, event ID, and resulting
  version data. Full descriptions are not journaled.
- Migration `0012_local_calendar` was applied to the target validation DB;
  migration repeat behavior remains covered by the existing validation path.

## SearXNG qualification

- Image: `docker.io/searxng/searxng:2026.8.29-d226b78bc`.
- Digest:
  `sha256:b36af7984b87191b595bc5301418ed6432c047668a4547ab531a7439b816fac3`.
- Manifest platforms: `linux/amd64`, `linux/arm64`, `linux/arm/v7`.
- Configuration: private/loopback, JSON only, no public instance, no image
  proxy, `limiter=false`, Valkey disabled, engines `duckduckgo` and
  `wikipedia`.
- x86-64 temporary-container measurements: approximately 95 MiB idle, 0% CPU
  at sample, 2.4 seconds startup-to-query, 3.3 seconds restart-to-query;
  post-restart query completed and the service remained running.
- Web target: `PASS`, one source-linked Wikipedia result; DuckDuckGo reported
  `CAPTCHA` in `unresponsive_engines`.
- Product target: `EXTERNAL_RESOURCE_GATE`, no useful product candidate.
- Candidate tests: Startpage and Qwant both returned upstream `CAPTCHA` in the
  same pinned image and were not adopted. This is a target-time external
  limitation, not a claim that the engines are universally unavailable.
- Overpass target: `PASS`, bounded synthetic restaurant query.
- `!bang` engine/category modifiers are rejected before SearXNG invocation.
- Strict command:
  `python scripts/verify_phase11_external.py --require-phase11-targets`
  returned nonzero because the product target was unavailable; non-strict mode
  preserved explicit gate reporting.

## Regression and publication

- Focused tests: `PASSED`.
- Changed-file Ruff: `PASSED`.
- Strict mypy: `PASSED` for 42 source files.
- OPA policy tests, package build, migration checks, diff check, and public
  safety scan: `PASSED`.
- Full pytest: `PASSED` on the fresh rerun after `uv sync --locked --dev`
  (`136 passed`). The first run had one transient, pre-existing Phase 5 MCP
  stdio startup failure; no Phase 5 source was changed.
- Implementation checkpoint: `c24b8eab5abe9acc31b4f54a321b0270399f3549`.
- Hosted CI: run `33462705630` `success` on that exact implementation SHA.
- Governed evidence closure checkpoint: `bf62877bcddd4683e4e7c046c2cb0233ef84f0b5`.
- Hosted CI: run `33462809329` `success` on that exact governed SHA.
- The final Authority synchronization is metadata-only; Phase 11 remains
  `IMPLEMENTATION COMPLETE — EXTERNAL_RESOURCE_GATE` pending Architect
  acceptance.

## Evidence limits

No native ARM64/Pi run, physical-home run, production-scale capacity claim,
commercial-provider claim, or human-notification delivery claim is made.
