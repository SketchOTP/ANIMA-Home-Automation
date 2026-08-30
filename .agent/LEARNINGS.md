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

## ANIMA-HA-P5-PLUGIN-CAPABILITY-RUNTIME-007 — Capability boundary learnings

- Official MCP Python SDK `2.1.1` is the current stable v2 line observed on 2026-08-29, with a pure-Python wheel and documented stdio/Streamable HTTP client boundary; wrapping it keeps MCP replaceable.
- Standard PyPA entry-point discovery is useful for trusted native plugins, but discovery must remain separate from enablement so installed code is not automatically available.
- A canonical tool descriptor must treat plugin/MCP metadata as untrusted hints: ANIMA manifest risk, identity, and Phase 4 policy remain authoritative; unknown consequential classification fails closed.
- Short-lived MCP subprocess connections give bounded crash/timeout containment and easy reconnect evidence, but they do not constitute a malicious-code sandbox. Stronger container isolation requires a separate measured decision.
- Secret minimization is enforceable at the runtime boundary by constructing a child environment from only base execution variables plus manifest-declared references; raw values remain absent from descriptors, persistence, and audit.
## ANIMA-HA-P6-HOME-ASSISTANT-ADAPTER-008 — Provider truth and action honesty

- Subscribe-and-buffer before snapshot prevents the startup interval from losing observable transitions; Phase 1 source ordering/deduplication remains authoritative when buffered events replay.
- HA areas/devices/entities are scoped provider references. Names and registry IDs cannot safely create or merge canonical household identity.
- HA disconnect permits current-state reconciliation after return but not reconstruction of missed transition history; journal the gap and preserve uncertainty.
- Service acknowledgement is not resulting state. Low-risk success requires a fresh observed HA state matching the request; otherwise return verification failure/unknown result.
- `hass-client` supplies useful protocol coverage but not ANIMA lifecycle semantics. Reconnect, resubscription, reconciliation, bounded retry, status, and policy/tool boundaries remain ANIMA-owned.
- `ha-testcontainer` 2.7.0 is useful prior art but its observed undeclared Playwright import cost made direct pinned-container orchestration the smaller Phase 6 harness.

## ANIMA-HA-P7-ATTENTION-CONTEXT-009 — Attention and context boundaries

- PostgreSQL journal position, advisory transaction locking, deterministic IDs, and unique constraints are sufficient for one restart-safe attention consumer; JetStream remains unnecessary until independent consumers justify duplicate durable delivery.
- Guaranteed reasoning is an event-class invariant, not a high numeric priority: distinct guaranteed canonical events bypass ordinary cooldown, rate limiting, and aggregation.
- A durable aggregate trigger may retain thousands of source IDs while its bounded ContextPacket carries a sample, total count, digest, and trigger reference. Durability and model-input sparsity are separate concerns.
- Context relevance must terminate in canonical graph/Truth/memory/tool contracts. Tool inclusion records relevance and health only; policy authorization remains unevaluated until invocation.
- Trust and cloud egress are separate ANIMA-owned classifications. External content remains untrusted even when relevant, and `LOCAL_ONLY` data is absent from the future cloud projection.
- Typed predicates are currently smaller and safer than CEL; CloudEvents SQL/CEL remain replacement prior art if rule complexity later demonstrates need.

## ANIMA-HA-P8-CODEX-OAUTH-RUNTIME-010R — Constrained Codex cognition learnings

- Codex CLI ChatGPT OAuth can support a bounded application cognition adapter without token extraction when Codex owns login and ANIMA only checks status/invokes the CLI.
- `codex exec` structured output on the tested CLI/model rejects a root `oneOf` and open variable objects; a flat all-required decision schema plus canonical JSON text for tool arguments preserves strict output while allowing ANIMA to perform exact Phase 5 schema validation.
- Stateless one-turn processes keep episode continuity ANIMA-owned. A structured transcript is sufficient for model-selected sequential tools without Codex session resume/history.
- Disabling direct capabilities requires both proactive strict config and reactive JSONL rejection. `agents.enabled=false` and `features.multi_agent=false` are both supported; the installed CLI requires `features.view_image=false` rather than `tools.view_image=false`.
- Model structured output is not perfectly deterministic. Invalid output must remain an explicit model failure and must never reach tool execution; live evidence included one such safe rejection before a complete passing matrix.
- ChatGPT OAuth usage provides token/latency evidence but not an API-dollar calculation or API retention control. Privacy depends on deterministic payload minimization plus the account/workspace server-side policy.

## ANIMA-HA-P9-ACTION-EXECUTION-CONCURRENCY-011 — Action safety learnings

- A durable `EXECUTING` marker must be committed before an external side effect; after restart it is evidence of possible side effect, not permission to retry.
- PostgreSQL session-level advisory locks can serialize canonical resources without a long transaction, but `pg_try_advisory_lock` is required when stale conflicting requests must fail immediately rather than queue.
- Latest-state preconditions must be checked after lock acquisition, and consequential verification must use a post-call refresh. Service acknowledgement alone is not success.
- Idempotency must bind a key to canonical request parameters. Reusing the key with different parameters is a conflict; repeating the same request returns the stored outcome without another connector call.
- Partial multi-effect outcomes require durable per-effect evidence and explicit non-compensation semantics. Ambiguous timeout/error after dispatch must remain `UNKNOWN_RESULT`.
