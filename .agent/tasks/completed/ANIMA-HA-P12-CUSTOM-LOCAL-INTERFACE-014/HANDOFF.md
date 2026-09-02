# Handoff

Directive: `ANIMA-HA-P12-CORE-INTEGRATION-PORTFOLIO-CLOSURE-014H`.

Implementation checkpoint: `208b7e546d8485539d2ae06427d268af116f9ceb`; hosted CI `33580734640` passed on that exact SHA.

The production UI composition is now wired through `src/anima_ha/ui_runtime.py` to the existing Journal, Attention, Context Broker, AgentRuntime, Phase 5/4 gateway, durable tasks, local calendar, and Phase 9 coordinator. The deterministic integrated test uses the real AgentRuntime with a scripted model adapter and preserves event/trigger/context/episode trace IDs.

Governance closure includes the portfolio README, Mermaid architecture, actual responsive screenshots, current Authority state, and completion of this task packet. The final governed SHA and exact final hosted CI are recorded after the closure push in the Authority/Notion handoff.

Acceptance boundary: Phase 12 remains pending Architect acceptance. Real Home Assistant OAuth/commissioning, physical-home behavior, production TLS, native ARM64/Pi execution, and live Luna qualification remain explicit limitations. Phase 13 is unauthorized.
