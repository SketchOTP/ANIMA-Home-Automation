# Specification — ANIMA-HA-P6-HOME-ASSISTANT-ADAPTER-008

## Objective

Connect ANIMA to a real isolated Home Assistant Core 2026.8.2 instance through a replaceable adapter while preserving Phase 1 truth/event semantics, Phase 2 canonical identity, and mandatory Phase 4/5 policy/tool gating.

## Required boundary

- HA area/device/entity IDs remain provider references scoped by a stable ANIMA-side instance ID.
- Unknown HA objects remain unmapped; names never create canonical identity.
- State and events normalize into provider-independent EventEnvelope and TruthObservation contracts.
- Reconnect uses subscribe/buffer, snapshot, replay, reconciliation, and explicit gap evidence.
- Agent-facing tools are bounded semantic operations; no generic HA service tool exists.
- Low-risk action success requires observed post-call state, not API acknowledgement.
- Token material is secret-brokered and absent from persistence, logs, audit, descriptors, and Git.

## Stop conditions

Stop for any need to weaken truth/identity/policy boundaries, persist credentials, bypass the Phase 5 gateway, add a foundational service, claim acknowledgement as physical success, or enter Phase 7 behavior.
