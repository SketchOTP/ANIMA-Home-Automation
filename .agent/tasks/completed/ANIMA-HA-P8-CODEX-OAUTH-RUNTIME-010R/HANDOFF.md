# Handoff — ANIMA-HA-P8-CODEX-OAUTH-RUNTIME-010R

- Verdict: COMPLETE / PASS pending independent Architect review.
- Starting governed SHA: `44d4f59737aeed9aa55583eb49823a37535d607d`.
- Phase 8 implementation SHA: `8486cd10b7962df11898bc8b61b1ec46d0809dd5`.
- Exact-SHA CI: GitHub Actions `33293828743`, PASSED without OAuth credentials.
- Runtime: `codex-cli 0.150.0-alpha.8`; ChatGPT OAuth status only; `gpt-5.6-luna`; medium reasoning; no API-key fallback.
- Selected boundary: ANIMA-owned durable sequential loop around isolated ephemeral `codex exec`; Codex returns structured decisions and never receives direct ANIMA/Codex machine capabilities.
- Live matrix: A–I PASSED; 14 turns; tool sequences none / current-state / current-state→events / confirmation-gated message / stronger-auth-gated unlock / failed lookup / none under hostile text / weather / none.
- Usage/latency: 112,592 input, 4,864 cached input, 1,555 output, 508 reasoning-output tokens; median 4,468.88 ms, p95 6,347.26 ms; API dollar pricing not applied.
- Regression evidence: 84 tests, Ruff, strict mypy, package build, OPA, PostgreSQL episode restart, Phase 1–5 integrations, real isolated Phase 6 HA, Phase 7 10,020-event replay/restart, simulator, public-safety review, and CI passed.
- Evidence limits: x86-64 local OAuth and synthetic tools; no native ARM64/Pi, physical home, production external service, API ZDR, or model-determinism claim. Installed Codex CLI is alpha.
- Notion SSOT: to be updated with the final governed closure SHA after this append-only packet is committed.
- Architect action: independently review and accept/reject Phase 8 before authorizing Phase 9.
- Explicit boundary: Phase 9 Action Execution/Verification/Concurrency and later behavior were not implemented.
