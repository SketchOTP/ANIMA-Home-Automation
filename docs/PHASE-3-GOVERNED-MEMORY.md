# Phase 3 — Governed Memory and Routine Model

Phase 3 adds an ANIMA-owned, locally persisted memory contract and a small
deterministic routine model. It does not add Luna, Mem0, Home Assistant,
policy/identity, plugins, actions, durable tasks, UI, or voice behavior.

## Architecture decision

`anima_memory_records` in PostgreSQL is the only canonical memory store.
`MemoryRecord` owns identity, taxonomy, content, provenance, confidence,
validity, lifecycle, correction links, and graph references. The service has
no permission or authority mutation API; authority-like metadata is rejected.
An explicit preference can affect future context ranking but cannot authorize a
tool or change policy.

`anima_memory_search_index` is a derived PostgreSQL full-text index. It can be
truncated and rebuilt from canonical records. Active retrieval excludes
superseded, expired, and retracted records, including records outside their
validity window. If the derived index is unavailable or empty, the service
falls back to bounded lexical matching over canonical records and identifies
the degraded mode.

## Taxonomy, provenance, and precedence

The canonical types are `EXPLICIT_PREFERENCE`, `EXPLICIT_FACT`,
`OBSERVED_CONTEXT`, `INFERRED_PATTERN`, `INTERACTION_MEMORY`,
`AGENT_LESSON`, and `TEMPORARY_EPISODIC`. Provenance is explicit and may
point to an interaction, journal event, Truth observation, graph identity,
prior memory, history-derived routine, or bounded agent lesson.

Retrieval uses deterministic precedence before lexical score:

1. explicit fact;
2. explicit preference;
3. active temporary episodic context;
4. interaction memory;
5. observed context;
6. bounded agent lesson;
7. inferred pattern.

This is a context ordering rule, not an authorization rule. Current Truth is
not written by MemoryService and remains the authority for current state.
Explicit temporary context is filtered by its validity window, so a statement
such as “we are staying up late tonight” can outrank an inferred low-activity
routine while it is active without modifying the routine or Truth.

## Lifecycle and audit

Memory records are append-oriented. `correct()` creates a new canonical record
linked with `supersedes_memory_id`, marks the old record `SUPERSEDED`, and
removes the old derived index entry. `expire()` and `retract()` preserve the
record and its history while removing it from active retrieval and the index.
Meaningful mutations emit `memory.mutation` events through the existing Phase
1 Event Journal in the same transaction as the canonical change.

Agent lessons are storage-only in this phase, require confidence no greater
than 0.5, and cannot create capabilities, alter prompts, modify software, or
grant authority. No autonomous extraction or Luna lesson loop exists.

## Routine model

`RoutineService` rebuilds `household_activity_by_bucket` from canonical
`routine.activity_observation` journal events. It stores bucket probabilities,
low-activity buckets, confidence, sample count, source time interval, source
event IDs, and a model version. Rebuilding is deterministic and idempotent;
new observations are incorporated by replaying the journal history. The output
is explicitly `INFERRED` and states that low activity is not proof of sleep or
absence. It cannot mutate memory, Truth, policy, or automation.

## Dependency qualification and dispositions

| Candidate | License / current qualification | Decision | Boundary and replacement path |
| --- | --- | --- | --- |
| Existing PostgreSQL 16 + Psycopg | PostgreSQL License / Psycopg 3.3.4; already qualified | ADOPT / WRAP | Canonical memory, routine persistence, and derived lexical index; callers use ANIMA interfaces. |
| Direct ANIMA memory and routine implementation | Repository-owned | BUILD | Preserves taxonomy, provenance, precedence, lifecycle, and authority boundary. |
| PostgreSQL full-text search | PostgreSQL License; core feature | ADOPT / WRAP | Small local lexical index; truncate/rebuild from canonical records. Replace with another derived index without changing MemoryService. |
| Mem0 OSS 2.0.19 | Apache-2.0; Python >=3.10; current source supports PostgreSQL/pgvector, metadata, expiration, and `infer=False`; telemetry exists and is opt-out | DEFER / WRAP candidate | Useful future secondary index only. Not installed or used; canonical records remain outside it and its LLM extraction/conflict behavior is not accepted as ANIMA semantics. |
| FastEmbed 0.8.0 | Apache-2.0; ONNX Runtime-based lightweight embeddings; Python >=3.10 | DEFER | No model was downloaded and no embedding corpus was introduced. Requalify with native ARM64/Pi latency/RAM and offline cache evidence before adoption. |
| Direct pgvector embeddings | PostgreSQL/pgvector; extension already available | DEFER | The database path is retained, but no unqualified model or vector dimension is locked in Phase 3. |
| LangGraph | MIT; stateful graph/agent orchestration | DEFER / REJECT as foundation | Overlaps future agent runtime and persistence; does not own ANIMA memory semantics. |
| Letta / MemFS | Apache-2.0 project; agent runtime with persisted memory filesystem | DEFER / REJECT as foundation | Agent-owned runtime/memory model and optional external/cloud paths exceed this phase; ANIMA canonical store is the replacement boundary. |
| Graphiti | Apache-2.0 code; temporal LLM/embedding knowledge graph | DEFER | Later learned/temporal enrichment candidate; unnecessary graph infrastructure and inference for deterministic Phase 3 memory. |
| River 0.24.2 | BSD-3-Clause; maintained online-ML library | DEFER | Direct journal aggregation is smaller and sufficient for the prototype routine. Add only if measured drift/online-learning needs justify it. |
| Lightweight Python statistics | Python standard library | ADOPT | Routine confidence and bucket aggregation are deterministic and have no new runtime dependency. |

### External qualification sources

- [Mem0 source package metadata](https://raw.githubusercontent.com/mem0ai/mem0/main/pyproject.toml), [Mem0 memory implementation](https://github.com/mem0ai/mem0/blob/main/mem0/memory/main.py), and [Mem0 self-hosted telemetry configuration](https://github.com/mem0ai/mem0/blob/main/server/README.md)
- [FastEmbed repository](https://github.com/qdrant/fastembed), [FastEmbed PyPI metadata](https://pypi.org/project/fastembed/), and [FastEmbed release](https://github.com/qdrant/fastembed/releases/latest)
- [River repository and license](https://github.com/online-ml/river) and [River release](https://pypi.org/project/river/)
- [LangGraph repository](https://github.com/langchain-ai/langgraph)
- [Letta memory documentation](https://github.com/letta-ai/letta-docs-md/blob/main/concepts/memfs/index.md)
- [Graphiti repository](https://github.com/getzep/graphiti)
- [PostgreSQL full-text search documentation](https://www.postgresql.org/docs/16/textsearch.html)

## Evidence boundary

Unit evidence covers contract validation, precedence ordering, agent-lesson
limits, temporary validity, and the no-authority metadata guard. PostgreSQL
integration evidence covers canonical persistence, lifecycle, filters,
household isolation, index deletion/rebuild/fallback, journal audit, and
routine recomputation on x86-64. Simulator evidence is synthetic only. No
Mem0, external embedding, Home Assistant, Luna, real-house, physical-device,
or native Raspberry Pi evidence is claimed. ARM64 remains the accepted
manifest/package metadata level from earlier phases.
