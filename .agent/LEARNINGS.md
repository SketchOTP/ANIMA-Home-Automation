# Durable Learnings

Temporary observations do not belong here. Add only findings likely to remain useful across future tasks.

---

## ANIMA-HA-P0-RUNTIME-BASELINE-002

- A pinned uv lockfile plus a narrow Python 3.12 support line gives Phase 0 reproducible package resolution without prematurely selecting future agent/event frameworks.
- The SFTP-mounted workspace cannot reliably host Python virtual-environment symlinks or mypy traversal; validation must distinguish this host filesystem limitation from application failures and can use a clean local-filesystem reproduction.
- The pgvector PostgreSQL image provides both amd64 and arm64 manifests and can be used as an extension-ready persistence substrate while vector/product schemas remain deferred.

---

## AUTHORITY-BOOTSTRAP-LEARNING-001 — Governance and implementation state are separate

- Date: 2026-08-28
- Evidence source: AUTHORITY-BOOTSTRAP-001 / Authority 3.0 Notion package
- Confidence: VERIFIED

### Learning

ANIMA HA starts with the Authority 3.0 governance package installed but with no implementation, dependencies, Git history, or runtime evidence.

### Why it matters

Future agents must treat governance bootstrap evidence as evidence of installed controls only, not evidence that any ANIMA HA capability or prototype acceptance criterion has been implemented.

### Recheck trigger

When the first implementation directive establishes repository, dependency, runtime, or test facts.

---

## ANIMA-HA-P0-LEARNING-001 — Existing GitHub baseline must remain the history parent

- Date: 2026-08-28
- Evidence source: ANIMA-HA-P0-GOVERNANCE-BASELINE-001 / remote inspection
- Confidence: VERIFIED

### Learning

The public `SketchOTP/ANIMA-Home-Automation` repository existed before local Git initialization at commit `088b267467fff93bfd225b9a94a6f4999759fb9f`, with `.gitignore` and `LICENSE` as its complete tree.

### Why it matters

Future checkpoints must preserve that history and must not replace or force-update `main` to discard the existing baseline.

### Recheck trigger

Any future history rewrite proposal, remote migration, or change to the repository's default branch.

## ANIMA-HA-P1-REALITY-SUBSTRATE-003 — PostgreSQL is sufficient for Phase 1 authority

- PostgreSQL unique constraints/`ON CONFLICT`, generated identity positions, JSONB payloads, and transactional projections are sufficient for the prototype's canonical journal and derived truth substrate without a second broker.
- A journal-first transaction boundary preserves malformed/projector-failing events for retry and rebuild; projection checkpoints must advance only after projection commit.
- Source sequence is a per-source ordering signal, not physical arrival order. Latest ties must remain visible so contradictory values are not silently selected.
- The maintained Python `eventsourcing` library is a valid BSD-3-Clause PostgreSQL-capable candidate, but its aggregate/application abstractions are not the ANIMA observation/truth contract; keep it deferred behind a replaceable boundary.
- NATS JetStream remains a later event-bus candidate because its durable consumers and at-least-once redelivery would add a second duplicate-handling/persistence layer before independent consumers justify it.
- KurrentDB/EventStoreDB is not the prototype baseline because its current Kurrent License is not OSI-approved and its separate service is unnecessary for this Pi-oriented Phase 1.

## ANIMA-HA-P2-HOUSEHOLD-GRAPH-004 — Canonical graph ownership

- PostgreSQL recursive CTEs are sufficient for the expected commissioned household topology; AGE would add a graph extension/query model without measured need.
- Canonical household identity must be ANIMA-owned and UUID-based. Home Assistant/provider IDs remain external references and may map many-to-one to resources or separately to capabilities.
- Brick and Haystack are useful semantic vocabulary prior art but are not runtime dependencies; Graphiti belongs to later learned/temporal context, not deterministic commissioning.
- Graph mutations can share the Phase 1 journal transactionally through a caller-owned Psycopg connection, preserving one audit boundary without a second audit store.
- Security sensitivity and household roles are graph facts only. They must not grant authority or become policy before the authorized policy phase.

## ANIMA-HA-P3-GOVERNED-MEMORY-005 — Canonical memory must own semantics

- PostgreSQL canonical memory plus a disposable PostgreSQL full-text index is sufficient for the Phase 3 prototype without adding a service or embedding model.
- Memory taxonomy, provenance, precedence, correction, expiry, and retraction belong to ANIMA; Mem0's extraction/conflict behavior cannot be the authority boundary even when `infer=False` is available.
- Derived search indexes must be disposable: deleting the index must leave canonical records readable and rebuild must restore indexed retrieval.
- Explicit context can outrank inferred routine context by deterministic precedence while remaining separate from Truth and policy. Routine output must state what it does not prove.
- The current Mem0 source package is Apache-2.0/Python >=3.10 and includes telemetry paths; FastEmbed 0.8.0 is a lightweight ONNX candidate; neither is adopted until offline/privacy/native-ARM64/resource qualification is complete.
- Direct journal aggregation is smaller than adding River for the current routine requirements; upgrade only when measured drift or online-learning requirements justify it.

## ANIMA-HA-P4-IDENTITY-POLICY-006 — Deterministic authority boundary

- OPA/Rego 1.20.1 is a suitable local replaceable evaluator for ANIMA's structured policy contract; pin both the multi-architecture image digest and the ANIMA policy bundle digest.
- Identity evidence is not authority: voice and local proximity remain recognized evidence, while strong authentication requires an evidence type and assurance rule that explicitly supports it.
- Conflicting principal evidence must not strengthen identity; resolving to anonymous/conflicted context is safer than selecting one claim.
- Explicit Anima autonomy is policy configuration, not memory or routine inference. Household roles are descriptive inputs and do not grant authority without policy.
- Confirmation and stronger authentication are separate: an exact, expiring, single-use confirmation can authorize a confirmation-gated external/financial operation but does not silently upgrade identity assurance.
- Policy evaluator failure, malformed output, and unavailable service must produce a durable `DENY` rather than fallback to model or remembered judgment.
