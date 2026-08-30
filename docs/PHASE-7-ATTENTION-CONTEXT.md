# Phase 7 — Attention Layer and Context Broker

Status: implementation complete, pending Architect review. This boundary selects durable cognition opportunities and assembles sparse local context. It does not call Luna, choose household actions, invoke tools, contact Home Assistant, or implement Phase 8 agent behavior.

## Architecture and ownership

Phase 7 reads only canonical Phase 1 journal rows. `PostgresAttentionService` processes them in monotonic journal-position order and stores immutable decisions, durable aggregation state, durable `ReasoningTrigger` records, metrics, failures, and a consumer cursor in PostgreSQL. The source event is committed before attention sees it; an attention transaction failure therefore cannot erase source reality.

The normal transaction is:

```text
lock consumer cursor
→ read canonical journal rows after the cursor
→ close due aggregates
→ classify each event with a pinned profile
→ persist decision / trigger / suppression state
→ advance cursor
→ commit
```

An exception rolls back the batch, records the failed journal position separately, and leaves the cursor before the unreconciled event. A PostgreSQL advisory transaction lock prevents two live workers from racing the same consumer.

## Attention profiles and decisions

`AttentionProfile` is an ANIMA-owned, versioned typed configuration. Rules may match bounded fields such as canonical event type, source, subject prefix, delivery/importance class, and explicit Truth-state metadata. Rule outcomes are `TRIGGER`, `AGGREGATE`, or `IGNORE`; no rule carries a tool, command, service call, notification, or household action.

Every registered profile has a canonical JSON digest. Reusing a profile version with different content fails closed. A live cursor cannot silently switch profiles. Decisions preserve the profile version/digest, source event and journal position, decision class, reason code, correlation/aggregation keys, resulting trigger, and bounded metadata. Database triggers reject normal updates/deletes of decisions and ContextPackets.

Decision classes are `TRIGGER`, `SUPPRESS`, `AGGREGATE_PENDING`, and `AGGREGATE_TRIGGER`. Suppression reasons distinguish `DUPLICATE`, `COOLDOWN`, `RATE_LIMIT`, `LOW_SIGNIFICANCE`, `AGGREGATED`, and `CONFIGURED_IGNORE`.

## Guaranteed reasoning

A distinct canonical event bypasses ordinary cooldown, rate limiting, and aggregation when its delivery class is `GUARANTEED`, its type is in the profile's guaranteed set, or its ANIMA-owned metadata explicitly marks guaranteed reasoning. The prototype profile includes user requests, security alarms, leaks, and critical system health. Canonical-event deduplication remains upstream in Phase 1, so replaying the same logical event cannot create another trigger.

Unclassified critical/high-importance input fails toward a trigger. Unclassifiable ordinary input fails explicitly without cursor advance; it is not silently discarded.

## Cooldown, rate limiting, correlation, and aggregation

Cooldown keys are profile/rule/household/subject scoped. Rate windows are profile/rule/household scoped. Both are persisted, deterministic, and apply only to ordinary traffic.

Correlation prefers the canonical event correlation ID and otherwise uses bounded canonical subject/event semantics. It groups context; it never prescribes an outcome.

Aggregation state stores the aligned window, source IDs, journal-position range, subjects, count, and representative metadata. Due windows close deterministically before later events or at an explicit flush boundary. A deterministic trigger UUID plus uniqueness constraints prevents duplicate flushes after restart. The durable trigger retains every source event ID; a ContextPacket may summarize a very large source-ID list with count/digest and a durable trigger reference to stay within its packet budget.

## ReasoningTrigger

`ReasoningTrigger` is the durable Phase 7 output. It preserves trigger type, all source event IDs, journal-position range, subject references, correlation ID, reason, priority, profile version, and status. Current statuses are `PENDING`, `CONTEXT_READY`, and `FAILED_CONTEXT`. Phase 8 can consume these rows without an in-memory queue.

## Context Broker

`ContextBroker` performs read-only selection against existing ANIMA services. Its default hard caps are:

| Section | Maximum |
| --- | ---: |
| Source events | 8 |
| Graph objects/relationships | 16 |
| Truth facts | 12 |
| Recent related events | 12 |
| Memories | 6 |
| Routine records | 3 |
| Identity items | 3 |
| Tools | 8 |
| Serialized packet | 65,536 bytes |

Selection starts with the trigger and direct source events, expands through canonical graph subjects and relationships, retrieves current Truth without flattening `STALE`, `UNKNOWN`, `UNAVAILABLE`, or `CONFLICTING`, and then requests bounded recent events, active memory, routines, identity context, and healthy relevant tools. It does not load all entities, graph nodes, history, memories, tools, or policy data.

Graph/tool relevance uses canonical node kinds, capability semantics, and ANIMA-owned tool hints. Tool inclusion records `policy_status: NOT_EVALUATED`; it never implies authorization. The executable Rego/policy corpus is absent. Actual invocation remains behind the Phase 5 gateway and Phase 4 policy.

Explicit memory and temporary context retain their memory type, lifecycle, confidence, and provenance. Inferred memory and routines remain `INFERRED`; routines are also explicitly `probabilistic`. Memory carries `authority: NONE`.

## Ranking, pruning, and explanation

Each item has a deterministic rank and inclusion reason. Direct trigger/current Truth/canonical subject context outranks peripheral data; explicit memory outranks inferred memory; healthy semantically relevant tools outrank unrelated or unavailable tools. Per-section caps are applied before the byte budget. Byte overflow removes whole lower-priority records in a fixed order and records `BUDGET_PRUNED`; JSON is never cut mid-record. Required trigger context remains present. Very large aggregate source sets are represented by a bounded ID sample, total count, digest, and durable `reasoning_trigger:<id>` reference.

Bounded reason codes include `DIRECT_TRIGGER`, `DIRECT_TRIGGER_SUBJECT`, `RELATED_ENTRANCE`, `CURRENT_TRUTH`, `RECENT_CORRELATED_EVENT`, `EXPLICIT_RELEVANT_MEMORY`, `INFERRED_RELEVANT_MEMORY`, `ROUTINE_TIME_MATCH`, `IDENTITY_REQUEST_CONTEXT`, `TOOL_CAPABILITY_MATCH`, `BUDGET_PRUNED`, and `SOURCE_UNAVAILABLE`.

If an optional source fails, its section is `DEGRADED` with a bounded error code; no data is fabricated and the trigger remains. `FAILED_CONTEXT` is reserved for failure to assemble required minimum context.

## Trust, privacy, and future cloud projection

Every item is marked `AUTHORITATIVE_LOCAL`, `OBSERVED_LOCAL`, `INFERRED_LOCAL`, `PLUGIN_TRUSTED`, or `EXTERNAL_UNTRUSTED`. External/plugin metadata cannot raise its own trust, grant authority, alter instructions, or widen the tool set.

ANIMA assigns `CLOUD_ALLOWED`, `CLOUD_REDACTED`, or `LOCAL_ONLY`. The deterministic cloud-safe projection removes `LOCAL_ONLY` items, recursively redacts secret/credential fields, and preserves trust/provenance. No cloud call occurs in Phase 7. Raw policy, credentials, biometric material, and whole-household state are not packet inputs.

The exact bounded packet, selection-profile version, source references, assembled time, digest, omissions, and serialized byte count are persisted. Identical fixed inputs and assembly time reproduce the digest.

## Replay and profile comparison

`anima-attention-replay` reads a journal range and profile, evaluates pure in-memory attention, and assembles non-persisted ContextPackets from local read-only state. It makes no HA calls, plugin invocations, tool calls, cloud calls, or agent decisions. A second profile can be compared over the same events; output reports trigger counts, guaranteed losses, suppression-reason differences, and actual ContextPacket byte differences. Comparison never promotes a profile.

## Dependency decisions

| Candidate | Decision | Rationale |
| --- | --- | --- |
| ANIMA typed predicates/configuration | BUILD | Small, explicit, auditable, non-executable rule set fits current attention semantics. |
| PostgreSQL cursor/decisions/triggers/aggregates | ADOPT / REUSE / WRAP | Existing canonical journal and transaction boundary provide restart safety without another durable system. |
| CloudEvents SQL v1.0.0 | REFERENCE | Apache-2.0 declarative filtering prior art; no runtime or event-contract dependency. |
| Official `cel-expr-python==0.1.3` | REFERENCE / DEFER | Apache-2.0, CPython 3.12 x86-64/ARM64 wheels, but young and materially larger than needed for this predicate set. |
| Community `cel-python==0.5.0` | DEFER / REJECT as foundation | Small pure-Python beta implementation, but the project does not need a second expression runtime. |
| NATS/JetStream | DEFER | Mature Apache-2.0 durable delivery, but adds at-least-once/redelivery and a second persistence/consumer subsystem without a measured Phase 7 need. |
| OpenTelemetry Context/Baggage | REFERENCE | Useful technical trace propagation; household context and sensitive data explicitly remain in ContextPacket, not baggage. |
| Arbitrary Python callbacks/scripts | PROHIBITED | Customer-authored executable attention logic violates the bounded deterministic configuration boundary. |

No new runtime dependency or infrastructure service was introduced.

## Validation and evidence limits

The PostgreSQL target harness journals 10,000 ordinary events across two subjects and two aligned minute windows plus 20 interspersed guaranteed events. It stops after 5,000 rows, reconstructs the service, resumes, and verifies exactly four aggregate triggers plus 20 guaranteed triggers. All 10,020 source events remain canonical; live and pure replay trigger IDs match; persisted context digest survives PostgreSQL restart. Profile A produced 24 triggers/234,616 aggregate packet bytes and Profile B produced 28/268,708 while preserving all guaranteed events.

The exterior-door scenario includes the entrance, contact/lock semantic neighborhood, current Truth, explicit preference, identity, routine provenance, and one relevant tool while excluding the bedroom. The nighttime-motion unit scenario includes its room, explicit `UNKNOWN` occupancy evidence, and an inferred/probabilistic routine. The user-request scenario bypasses suppression and includes bounded identity/tool context. Unit evidence also covers cooldown, rate limiting, duplicate/no-change behavior, critical fail-toward-trigger, budget pruning, secret redaction, untrusted content, cloud projection, and degraded memory lookup.

Evidence is synthetic x86-64 unit/PostgreSQL/replay evidence plus regression evidence from accepted lower phases. There is no Luna, cloud cognition, autonomous action, physical-home behavior, native ARM64/Pi run, or new real-HA behavior claim.
