# Evidence — ANIMA-HA-P6-HOME-ASSISTANT-ADAPTER-008

- Starting SHA: `b426d66e7293a132dcdb4abaa96bc7594cdf7b73`; Phase 5 CI `33277980009`.
- Implementation SHA: `ecae55af1894889e0948d11a9ae01288c217c646`; exact-SHA CI `33284454470` PASSED.
- Real HA target: Core `2026.8.2`, image index `sha256:56690a89c79a0de98035e1719f8324a92d5859c1192ff45adb0230ea81cb42a5`.
- Discovery: 11 states, 60 service domains, 3 areas, 1 device, 11 entities in the deterministic fixture.
- Real WebSocket state/registry events; KNOWN/UNKNOWN/UNAVAILABLE; duplicate/race; mapping/unmapped/many-to-one; policy deny/confirm/strong-auth; verified low-risk power; deliberate verification failure; disconnect/reconnect/gap; invalid auth; disable/re-enable; HA/PostgreSQL restart: PASSED.
- Ruff format/check, strict mypy 27 source files, pytest 43 tests, migrations, Phase 1–5 integrations, simulator, locked fresh-copy validation/build, public-safety scan: PASSED.
- Resource sample on x86 host: HA container 0.00% CPU / 308.6 MiB; full harness process 104320 kB RSS.
- ARM64/Pi: metadata only. Physical household/device: NOT RUN. Phase 7/Luna: NOT IMPLEMENTED.
