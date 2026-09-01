# Handoff — ANIMA-HA-P11-RESTRICTED-CONTENT-PERSISTENCE-013R5

Verdict: `CONTINUE / HARDEN` — implementation/evidence complete for Architect
review; live Best Buy remains `EXTERNAL_RESOURCE_GATE_BEST_BUY_KEY`.

The bounded correction closes the accepted retention conflict without a purge
service: Core marks Best Buy content `EPHEMERAL_RESTRICTED`, keeps full content
only in the active live process, stores structural durable projections, and
blocks all later tool execution in the tainted episode. The active caller still
receives the full live answer. Unrestricted provider persistence remains
unchanged.

The real PostgreSQL sentinel and export scans passed with zero durable sentinel
occurrences. Best Buy deterministic provider tests passed, but no live provider
request was made because `BEST_BUY_API_KEY` is not configured. Walmart remains
deferred pending entitlement clarification. Phase 12 was not implemented.

Implementation checkpoint: `b810c853b47470c4395dd1a5731e59da98ae41a5`, hosted
CI `33525400264` passed on the exact SHA. The final governed SHA and CI are
recorded after the governance closure commit in this packet and
`.agent/CURRENT.md`.
