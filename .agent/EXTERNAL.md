# External Discovery Ledger

Record material prior-art investigations when Authority triggers external discovery. Do not log every trivial web search.

---

## AUTHORITY-BOOTSTRAP-001 — Authority 3.0 governance package

- Date checked: 2026-08-28
- Trigger: Governance installation for a new project.
- Source: Connected Notion page `Authority 3.0 — Complete Installation Package`.
- Freshness: Retrieved 2026-08-28; package page states Authority 3.0.
- Disposition: ADOPT

### Problem addressed

Provide a durable governance and evidence workflow for a project operated through an Architect → Codex → evidence → Architect loop.

### Relevant overlap

The package defines the root agent router, project state/history files, reusable Codex and external-discovery workflows, directive/result contracts, evidence ladder, state update rules, safety boundary, and new-project checklist.

### Fit / limitations

It is governance and process infrastructure, not ANIMA HA implementation. It does not establish runtime dependencies, architecture completion, or prototype acceptance evidence.

### Decision rationale

Adopted because it is the requested Authority 3.0 package and directly supplies the required new-project file set.

### Recheck trigger

Only when the canonical Authority package changes or the project is explicitly migrated to a newer authorized governance version.

---

## ANIMA-HA-P0-RUNTIME-BASELINE-002 — Python packaging, tooling, and runtime

- Date checked: 2026-08-28/29
- Trigger: Phase 0 requires reproducible dependencies, automated validation, and portable runtime support.
- Source: [uv project/lockfile documentation](https://docs.astral.sh/uv/guides/projects/); [Ruff linter](https://docs.astral.sh/ruff/linter/); [Ruff formatter](https://docs.astral.sh/ruff/formatter/); [Psycopg](https://www.psycopg.org/download/); [pytest](https://github.com/pytest-dev/pytest); [mypy](https://github.com/python/mypy); [uv license](https://github.com/astral-sh/uv/blob/main/README.md#license).
- Freshness: Sources checked against current published documentation/package metadata; exact adopted versions are in `pyproject.toml` and `uv.lock`.
- Disposition: ADOPT, with `psycopg` WRAPPED behind the ANIMA database boundary.

### Problem addressed

Provide a small, reproducible Python project environment and deterministic engineering checks on ARM64 and x86-64.

### Relevant overlap

uv supplies a checked-in cross-platform lockfile and managed environment; Ruff supplies lint and formatting; pytest supplies unit tests; mypy supplies strict static checking; Psycopg supplies the PostgreSQL DB-API adapter and binary wheels.

### Fit / limitations

All selected packages support Python 3.12. Psycopg 3.3.4 has Linux ARM64 and x86-64 binary wheels; Ruff and mypy publish ARM64-capable Linux distributions. The live host is x86-64. The latest mypy 2.3.1 produced an internal validation error and was not adopted; 1.17.1 passes and is pinned pending requalification.

### Decision rationale

The set is sufficient for Phase 0 and avoids adopting future-phase frameworks. Exact versions are locked; application code owns configuration/logging/database boundaries so providers can be replaced later.

### Recheck trigger

Upgrade request, Python-line change, ARM64 native execution, or introduction of a later-phase dependency that changes packaging or database requirements.

---

## ANIMA-HA-P0-RUNTIME-BASELINE-002 — PostgreSQL and pgvector deployment

- Date checked: 2026-08-28/29
- Trigger: Phase 0 requires a persistent substrate, migration mechanism, health check, restart persistence, and evaluation of the later vector-memory path.
- Source: [official PostgreSQL image](https://hub.docker.com/_/postgres); [pgvector project/Docker tags](https://github.com/pgvector/pgvector); [Docker multi-platform images](https://docs.docker.com/build/building/multi-platform/).
- Freshness: Image manifest and runtime inspection performed 2026-08-28/29; exact digest is recorded in `compose.yaml`.
- Disposition: ADOPT the pinned pgvector image conditionally for future vector use; ADOPT PostgreSQL; WRAP database access behind ANIMA-owned code; DEFER vector schema/use.

### Problem addressed

Provide isolated local persistence without pulling message brokers, policy engines, memory services, or agent infrastructure into Phase 0.

### Relevant overlap

PostgreSQL supplies the durable relational substrate. The pgvector image preserves a low-cost extension path for future memory work. Compose supplies health checking, named-volume persistence, and restart control.

### Fit / limitations

The observed pgvector image digest has Linux amd64 and arm64 manifests, includes vector extension 0.8.6, and ran successfully on this x86-64 host. The pulled image is approximately 621 MB and the idle container used approximately 0.02% CPU / 71 MiB memory on this host. These are not Raspberry Pi measurements. The named volume is the backup boundary; backup/restore implementation is deferred.

### Decision rationale

The image retains the later vector option without enabling product behavior or adding another service. Official `postgres:16-bookworm` remains the replacement path if pgvector maintenance or footprint becomes unacceptable.

### Recheck trigger

Native Pi run, image digest update, Phase 1 memory schema design, backup/restore qualification, or resource pressure on the target controller.

## ANIMA-HA-P1-REALITY-SUBSTRATE-003 — event journal and projection prior art

- Date checked: 2026-08-29
- Trigger: Phase 1 required a persistence/prior-art comparison before implementing the canonical event journal and Truth/State service.
- Sources: [Python eventsourcing project](https://github.com/pyeventsourcing/eventsourcing); [eventsourcing PostgreSQL documentation](https://eventsourcing.readthedocs.io/en/stable/topics/tutorial/part3.html); [NATS JetStream concepts](https://docs.nats.io/concepts/jetstream); [KurrentDB introduction](https://docs.kurrent.io/server/latest/); [KurrentDB repository](https://github.com/Kurrent-io/KurrentDB).

### Comparison and disposition

| Candidate | Disposition | Qualification | ANIMA decision |
| --- | --- | --- | --- |
| Existing PostgreSQL + Psycopg | ADOPT / WRAP | Already qualified in Phase 0; PostgreSQL 16/pgvector image has ARM64/x86-64 manifests; transactional SQL, unique constraints, JSONB, restart persistence | Canonical journal and derived truth projection behind ANIMA-owned interfaces |
| Direct ANIMA journal/reducer implementation | BUILD | Keeps event envelope, provenance, time semantics, truth quality, reconciliation, and replay owned by ANIMA | Selected for Phase 1 |
| Python `eventsourcing` 9.5.5 documentation/project | DEFER | BSD-3-Clause, maintained, typed, and PostgreSQL-capable through Psycopg; aggregate/application model does not directly fit external observations and ANIMA truth semantics | Reconsider only if a later bounded spike shows material code reduction without coupling |
| NATS JetStream (current server; version not pinned) | DEFER | NATS server is Apache-2.0; official JetStream docs describe persistent streams, durable consumers, replay, and at-least-once redelivery | Add only when independent asynchronous consumers justify a broker; do not replace canonical journal |
| KurrentDB/EventStoreDB v26.0 | REJECT for prototype baseline | Current KurrentDB docs identify Kurrent License v1 as not OSI-approved; separate event-native service adds operational/storage overhead and is unnecessary for Phase 1 | Keep as non-foundational alternative; replacement path is PostgreSQL |

### Boundary conclusion

The selected design preserves the event-sourcing benefits needed here—durable history plus rebuildable derived state—without delegating ANIMA's event/truth meanings to a framework or adding a second persistence service. The decision does not change the SSOT architecture or phase ordering.

## ANIMA-HA-P2-HOUSEHOLD-GRAPH-004 — canonical graph prior art

- Date checked: 2026-08-29
- Trigger: Phase 2 required prior-art comparison before selecting canonical graph persistence.
- Sources: [PostgreSQL recursive queries](https://www.postgresql.org/docs/16/queries-with.html); [Apache AGE](https://github.com/apache/age); [NetworkX](https://github.com/networkx/networkx); [Brick Schema](https://github.com/BrickSchema/Brick); [Project Haystack](https://project-haystack.org/); [Graphiti](https://github.com/getzep/graphiti).

### Comparison and disposition

| Candidate | License / maintenance | Fit, persistence, portability, and replacement path | Decision |
| --- | --- | --- | --- |
| PostgreSQL recursive CTE | PostgreSQL License; mature core feature in PostgreSQL 16 | Durable transactional relational persistence; recursive hierarchy traversal; already qualified for x86-64 and ARM64 image path; replace repository behind ANIMA contracts if needed | ADOPT / WRAP |
| Apache AGE | Apache-2.0; active PostgreSQL extension | Adds an extension and graph query abstraction without measured need for the expected household scale; PostgreSQL CTE repository is the replacement path | REJECT |
| NetworkX | BSD-3-Clause; mature Python project | In-process algorithms only; no authoritative durable persistence, restart, or transaction boundary; future analysis adapter could wrap it | REJECT as canonical persistence |
| Brick Schema | BSD-3-Clause; building semantic project | Broad RDF ontology and useful building vocabulary; runtime adoption would add semantic/dependency coupling; ANIMA graph contracts are the replacement boundary | REFERENCE / ADAPT |
| Project Haystack | Academic Free License 3.0; open building/IoT semantic project | Useful tags and relationships, but does not replace ANIMA-owned UUID, provenance, lifecycle, or provider-reference semantics | REFERENCE / ADAPT |
| Graphiti | Apache-2.0 code; active temporal agent-context project | LLM/embedding-assisted temporal graph construction fits later learned memory/context, not deterministic commissioned topology | DEFER |

### Boundary conclusion

No new graph database, extension, or service was introduced. The selected
PostgreSQL/Psycopg repository preserves ANIMA ownership of identity, semantics,
provider isolation, Truth bindings, mutation audit, and query behavior. The
Home Assistant registry remains future provider input only; its IDs are not
canonical household identity.

## ANIMA-HA-P3-GOVERNED-MEMORY-005 — memory, embedding, and routine prior art

- Date checked: 2026-08-29
- Trigger: Phase 3 required current qualification of canonical-memory engines, local embeddings, and routine-model options.
- Sources: [Mem0 package metadata](https://raw.githubusercontent.com/mem0ai/mem0/main/pyproject.toml); [Mem0 memory implementation](https://github.com/mem0ai/mem0/blob/main/mem0/memory/main.py); [Mem0 server telemetry](https://github.com/mem0ai/mem0/blob/main/server/README.md); [FastEmbed](https://github.com/qdrant/fastembed) and [FastEmbed PyPI](https://pypi.org/project/fastembed/); [River](https://github.com/online-ml/river) and [River PyPI](https://pypi.org/project/river/); [LangGraph](https://github.com/langchain-ai/langgraph); [Letta MemFS](https://github.com/letta-ai/letta-docs-md/blob/main/concepts/memfs/index.md); [Graphiti](https://github.com/getzep/graphiti); [PostgreSQL text search](https://www.postgresql.org/docs/16/textsearch.html).
- Freshness: primary sources checked 2026-08-29; exact source versions and limitations are recorded in `docs/PHASE-3-GOVERNED-MEMORY.md`.

### Comparison and disposition

| Candidate | License / maintenance / fit | Decision |
| --- | --- | --- |
| Existing PostgreSQL 16 + Psycopg | Already qualified; durable local persistence and transaction boundary | ADOPT / WRAP |
| Direct ANIMA memory/lifecycle/routine implementation | Preserves type, provenance, precedence, correction, expiry, isolation, and no-authority invariant | BUILD |
| PostgreSQL full-text search | Mature core local lexical index; no new service; disposable/rebuildable | ADOPT / WRAP |
| Mem0 OSS 2.0.19 | Apache-2.0, Python >=3.10, PostgreSQL/pgvector and `infer=False`; optional/default telemetry and provider/extraction semantics require a wrapper | DEFER / WRAP candidate |
| FastEmbed 0.8.0 | Apache-2.0, lightweight ONNX path, Python >=3.10; model download/cache and native Pi cost not qualified | DEFER |
| Direct pgvector embeddings | Extension already available, but no model/dimension/offline ARM64 qualification | DEFER |
| LangGraph | MIT; agent graph persistence/orchestration overlaps a later runtime | DEFER / REJECT as foundation |
| Letta / MemFS | Open-source stateful-agent memory with git-backed files; agent/runtime-owned semantics exceed this phase | DEFER / REJECT as foundation |
| Graphiti | Apache-2.0 code; LLM/embedding temporal graph enrichment fits later context, not canonical memory | DEFER |
| River 0.24.2 | BSD-3-Clause and maintained online ML/statistics; more footprint than current deterministic aggregation requires | DEFER |
| Python standard-library statistics | No new dependency; adequate deterministic bucket probabilities/confidence | ADOPT |

### Boundary conclusion

Canonical memory remains ANIMA-owned PostgreSQL data. No Mem0, embedding model,
external vector service, or River dependency was adopted. The implementation's
only retrieval index is local PostgreSQL full-text data that can be deleted and
rebuilt; fallback reads canonical records directly. This avoids household-data
egress and preserves a replacement path for future semantic retrieval.

### Recheck triggers

Requalify before adopting Mem0 or embeddings, enabling agent/Luna memory
extraction, deploying on native Raspberry Pi, changing the PostgreSQL image,
or introducing drift/online-learning requirements that exceed direct
aggregation.

## ANIMA-HA-P4-IDENTITY-POLICY-006 — policy-engine qualification

- Date checked: 2026-08-29
- Sources: [OPA v1.20.1 release](https://github.com/open-policy-agent/opa/releases/tag/v1.20.1), [OPA integration](https://www.openpolicyagent.org/docs/integration), [OPA Docker](https://www.openpolicyagent.org/docs/deploy/docker), [OPA bundles](https://www.openpolicyagent.org/docs/management-bundles), [OPA policy testing](https://www.openpolicyagent.org/docs/policy-testing), [Cedar authorization](https://docs.cedarpolicy.com/auth/authorization.html), [Cedar implementation](https://github.com/cedar-policy/cedar), [OpenFGA concepts](https://openfga.dev/docs/concepts), and [Casbin](https://casbin.org/).
- OPA v1.20.1 is Apache-2.0 and was the current stable upstream release observed on this date. The pinned image index is `sha256:39daf255ae7f25d81103f03a0c18308a50b7b5bb67907bed6166f70e24a970ff`; observed amd64 and arm64 manifests are recorded in `docs/PHASE-4-IDENTITY-POLICY.md`.
- OPA's local REST evaluation, structured JSON result, filesystem/bundle policy loading, and `opa test` fit the required replaceable evaluator boundary. Compose uses a loopback-only service and read-only policy mount with no remote bundle or decision-log destination.
- Cedar is reference-only because its native authorizer result is allow/deny; Casbin is reference/reject as core because it does not materially reduce the contextual four-way policy contract; OpenFGA is deferred/rejected for this phase because ReBAC tuples are not the primary household policy problem.
- Disposition: ADOPT / WRAP OPA; BUILD ANIMA contracts, risk classification, identity aggregation, confirmation, audit, and fail-closed wrapper; REFERENCE Cedar/Casbin; DEFER/REJECT OpenFGA.
- Recheck trigger: policy schema expansion, native Pi qualification, OPA image update, external bundle/decision logging, or Phase 5 capability integration.

## ANIMA-HA-P5-PLUGIN-CAPABILITY-RUNTIME-007 — plugin and MCP qualification

- Date checked: 2026-08-29
- Sources: [MCP Python SDK 2.1.1 on PyPI](https://pypi.org/project/mcp/2.1.1/), [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [PyPA entry points](https://packaging.python.org/en/latest/specifications/entry-points/), [PyPA plugin discovery](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/), [jsonschema](https://pypi.org/project/jsonschema/), and [Pluggy documentation](https://pluggy.readthedocs.io/en/stable/).
- MCP `2.1.1` is the current stable v2 release observed on this date. Its PyPI wheel is pure Python, MIT-licensed, and publishes the v2 line; the official SDK documents client support for local stdio and URL-based Streamable HTTP. The package's transitive async/HTTP stack is pinned by `uv.lock`; no native extension is required by the MCP package itself. Native ARM64 execution was not performed.
- `jsonschema 4.26.0` is MIT, Python >=3.10, production/stable, and supports Draft 2020-12. It is adopted only behind ANIMA's schema boundary; schemas are size/depth bounded and `$ref` is rejected to prevent automatic remote dereferencing.
- PyPA defines entry-point groups as the portable installed-plugin advertisement mechanism and documents `importlib.metadata.entry_points(group=...)`; ANIMA adopts the standard group but does not auto-enable discovered plugins.
- Pluggy is maintained MIT-licensed in-process hook/registry prior art; it does not provide MCP transport, process isolation, secret minimization, or ANIMA policy ownership, so it remains reference-only.
- FastMCP is reference/deferred because the official SDK `MCPServer` is sufficient for the synthetic server and adopting another server abstraction would add coupling without saving meaningful Phase 5 work.
- Subprocess MCP is adopted for optional plugin failure containment; it is explicitly not a malicious-code sandbox. Container-per-plugin isolation is deferred pending a later measured security/deployment requirement.
- Disposition: BUILD ANIMA manifest/registry/lifecycle/invocation/secrets/config/event/audit; ADOPT/WRAP official MCP and `jsonschema`; ADOPT standard entry-point discovery; REFERENCE/DEFER FastMCP and Pluggy; DEFER container sandbox and marketplace/install/update services.
- Recheck trigger: MCP SDK release/protocol change, Streamable HTTP deployment, native Pi qualification, malicious-code isolation requirement, or Phase 6/Home Assistant capability integration.
## ANIMA-HA-P6-HOME-ASSISTANT-ADAPTER-008 — HA client and test target

- Date checked: 2026-08-29
- Trigger: Phase 6 required a real HA target and current client/test-harness comparison.
- Sources: [Home Assistant WebSocket API](https://developers.home-assistant.io/docs/api/websocket/); [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/); [hass-client 1.2.3](https://pypi.org/project/hass-client/); [ha-testcontainer 2.7.0](https://pypi.org/project/ha-testcontainer/); [HA Core releases](https://github.com/home-assistant/core/releases).
- Freshness: official/current sources, package metadata, source inspection, OCI manifest, and x86-64 runtime checked 2026-08-29.

| Candidate | Disposition | Finding |
| --- | --- | --- |
| HA Core `2026.8.2` pinned GHCR image | ADOPT for target evidence | Real WebSocket/registry/service target; index digest has observed amd64 and arm64 children. |
| `hass-client==1.2.3` | ADOPT / WRAP | Apache-2.0, Python >=3.10, pure Python; required API surfaces present. ANIMA retains reconnect/reconcile semantics. |
| Direct `aiohttp` implementation | REJECT for runtime | Would duplicate the selected client's protocol surface; raw test helpers remain fixture-only. |
| `ha-testcontainer==2.7.0` | REFERENCE / DEFER | MIT/alpha; qualification found base import depended on separately installed Playwright, whose package was 45.5 MiB. |
| Direct pinned container fixture | ADOPT for tests | Smaller deterministic onboarding/token/demo evidence path and no runtime dependency. |

The selected image is `ghcr.io/home-assistant/home-assistant:2026.8.2@sha256:56690a89c79a0de98035e1719f8324a92d5859c1192ff45adb0230ea81cb42a5`. Container manifest support is not native Pi evidence. Recheck on HA/client upgrade, OAuth work, registry API change, or native ARM64 execution.

## ANIMA-HA-P7-ATTENTION-CONTEXT-009 — attention/filter/transport prior art

- Date checked: 2026-08-29
- Trigger: Phase 7 required a bounded local attention representation and restart-safe consumer before Luna.
- Sources: [CloudEvents SQL v1.0.0](https://github.com/cloudevents/spec/blob/main/cloudevents/sql/spec.md); [`cel-expr-python` 0.1.3](https://pypi.org/project/cel-expr-python/); [`cel-python` 0.5.0](https://pypi.org/project/cel-python/); [NATS JetStream](https://docs.nats.io/nats-concepts/jetstream); [OpenTelemetry Context](https://opentelemetry.io/docs/specs/otel/context/); [OpenTelemetry Baggage](https://opentelemetry.io/docs/concepts/signals/baggage/).
- Freshness: official specifications, repositories, and current package metadata checked 2026-08-29.

| Candidate | Disposition | Finding |
| --- | --- | --- |
| ANIMA-owned typed predicates | BUILD | Explicit terminating matches cover current event/source/subject/importance/Truth needs without executable customer logic. |
| PostgreSQL journal consumer state | ADOPT / REUSE / WRAP | Existing transaction, monotonic position, unique constraints, and persistence provide cursor/decision/aggregate/trigger restart safety. |
| CloudEvents SQL v1.0.0 | REFERENCE | Apache-2.0 declarative filtering prior art; adopting its runtime/contract would not reduce current implementation risk. |
| Official `cel-expr-python==0.1.3` | REFERENCE / DEFER | Apache/CEL Apache-2.0 wrapper; CPython 3.12 Linux x86-64 and ARM64 wheels observed, about 17.3/16.5 MB. Young and unnecessary for the bounded rule set. |
| Community `cel-python==0.5.0` | DEFER / REJECT as foundation | Beta pure-Python implementation with Python >=3.10 support, but no measured advantage over typed configuration. |
| NATS/JetStream | DEFER | Mature Apache-2.0 durable at-least-once delivery and credible ARM64 path; adds a second persistent consumer/redelivery system before independent consumers require it. |
| OpenTelemetry Context/Baggage | REFERENCE | Appropriate technical correlation mechanism; official guidance warns that baggage can propagate sensitive data, so household context remains in ANIMA ContextPackets. |
| Arbitrary Python attention callbacks | PROHIBITED | Executable customer rules would violate bounded, inspectable attention semantics. |

No new dependency or infrastructure was introduced. Recheck when rule complexity demonstrates a need for CEL, multiple independent consumers justify a broker, trace propagation is adopted, or native Pi resource evidence changes the tradeoff.

## ANIMA-HA-P8-CODEX-OAUTH-RUNTIME-010R — Codex OAuth cognition boundary

- Date checked: 2026-08-30
- Trigger: The operator superseded the API-key Agents SDK design and required the existing Codex CLI ChatGPT OAuth session for Phase 8 cognition.
- Sources: [Codex CLI reference](https://developers.openai.com/codex/cli/reference), [Codex configuration reference](https://developers.openai.com/codex/config-reference), [Codex non-interactive mode](https://learn.chatgpt.com/codex/non-interactive-mode), [Codex SDK](https://developers.openai.com/codex/sdk), [Codex App Server](https://developers.openai.com/codex/app-server), [Agents SDK](https://openai.github.io/openai-agents-python/), [Responses API](https://platform.openai.com/docs/api-reference/responses), and the Apache-2.0 Codex repository license.
- Freshness: Official pages and installed runtime inspected 2026-08-30. Exact installed CLI: `codex-cli 0.150.0-alpha.8`.

| Candidate | Disposition | Finding |
| --- | --- | --- |
| ANIMA durable episode/structured loop | BUILD | Required so ANIMA, not the provider, owns context, tools, policy, privacy, budgets, audit, and outcomes. |
| Codex CLI `codex exec` | ADOPT / WRAP | Installed status reports ChatGPT OAuth; model catalog exposes `gpt-5.6-luna` with medium reasoning; strict ephemeral JSONL/output-schema live probe passed with direct capability controls disabled. |
| Codex SDK | REFERENCE / DEFER | Programmatic replacement candidate, but unnecessary for the qualified Python subprocess boundary. |
| Codex App Server | REFERENCE / DEFER | Long-lived RPC surface is broader than the bounded one-turn runtime needs. |
| OpenAI Agents SDK | DEFER / REJECT for Phase 8 foundation | Valuable provider/API agent framework but does not consume the selected Codex CLI OAuth session. |
| Responses API | DEFER | Direct API credential and billing path is outside the operator ruling. |

### Boundary conclusion

The selected adapter launches a fresh empty working directory, ignores user
configuration/rules, uses strict config/read-only sandbox/ephemeral history,
disables shell, unified exec, multi-agent, apps, plugins, web, image, memories,
dependency installation, analytics, and feedback, and accepts only bounded
agent-message JSONL. The supported CLI uses `features.view_image=false` rather
than the rejected `tools.view_image=false` spelling. OAuth credential contents
were not inspected. No Python dependency or service was added.

### Recheck triggers

Codex CLI upgrade (especially because the installed build is alpha), model
catalog/config change, ChatGPT OAuth policy change, native ARM64/Pi deployment,
structured-output protocol change, or an Architect-authorized move to the SDK,
App Server, Agents SDK, or Responses API.

## ANIMA-HA-P9-ACTION-EXECUTION-CONCURRENCY-011 — locks and idempotency

- Date checked: 2026-08-30
- Trigger: Phase 9 introduced a new execution coordinator with resource serialization, ambiguous-side-effect handling, and idempotency semantics.
- Sources: [PostgreSQL 16 explicit locking](https://www.postgresql.org/docs/16/explicit-locking.html), [PostgreSQL advisory-lock functions](https://www.postgresql.org/docs/17/functions-admin.html), [PostgreSQL pg_locks](https://www.postgresql.org/docs/16/view-pg-locks.html), and [Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests?lang=curl).
- Freshness: official documentation checked 2026-08-30.
- Findings: PostgreSQL session locks persist until explicit unlock/session end, transaction locks release at transaction end, and `pg_try_advisory_lock` returns immediately on contention. Stripe's mature pattern stores the first result for a key and rejects parameter reuse; ANIMA applies the pattern to durable action claims but keeps stricter `UNKNOWN_RESULT` handling after possible external dispatch.
- Disposition: ADOPT / WRAP PostgreSQL session-level advisory locking; REFERENCE Stripe parameter-bound idempotency; BUILD ANIMA lifecycle, durable records, verification, and recovery semantics; REJECT Redis/Redlock as the foundational fencing mechanism; DEFER Temporal/Hatchet to Phase 10.
- Recheck trigger: PostgreSQL major-version change, measured lock contention/deadlock need, provider-native idempotency support, physical-home/HA execution qualification, or Phase 10 durable workflow authorization.

## ANIMA-HA-P11-EXTERNAL-CAPABILITIES-013 — External provider and dependency qualification

- Date checked: 2026-08-31
- Trigger: Phase 11 authorized bounded external-by-intent weather, discovery, recipes, Calendar, notification, trust, egress, and audit capabilities.
- Sources: [Open-Meteo API docs](https://open-meteo.com/en/docs), [Open-Meteo terms](https://open-meteo.com/en/terms), [Open-Meteo license](https://open-meteo.com/en/license), [Open-Meteo pricing](https://open-meteo.com/en/pricing); [Brave Web Search API](https://api-dashboard.search.brave.com/api-reference/web/search/get), [Brave Place Search](https://api-dashboard.search.brave.com/documentation/services/place-search); [TheMealDB API](https://www.themealdb.com/api.php), [TheMealDB terms](https://themealdb.com/terms_of_use.php); [ntfy publish](https://docs.ntfy.sh/publish/); [Google Calendar events.list](https://developers.google.com/calendar/api/v3/reference/events/list?hl=en), [events.insert](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert), [Calendar OAuth scopes](https://developers.google.com/workspace/calendar/api/auth), [Calendar MCP configuration](https://developers.google.com/workspace/calendar/api/guides/configure-mcp-server?authuser=0); [httpx PyPI](https://pypi.org/project/httpx/), [google-auth PyPI](https://pypi.org/project/google-auth/), [google-auth-oauthlib PyPI](https://pypi.org/project/google-auth-oauthlib/).
- Freshness: official documentation and package metadata checked 2026-08-31; exact adopted versions are in `pyproject.toml` and `uv.lock`.
- Disposition: ADOPT / WRAP bounded provider adapters and `httpx==0.28.1`; ADOPT Google auth packages for the runtime commissioning boundary; REFERENCE / DEFER Google Calendar MCP preview; DEFER retailer cart/checkout and browser/private endpoint automation.

### Findings and limits

- Open-Meteo provides the no-key prototype weather surface but its free endpoint is non-commercial, rate-limited, and attribution-bearing; commercial deployment requires a separately qualified plan.
- Brave provides bounded Web Search and Place Search endpoints, but `BRAVE_SEARCH_API_KEY` is a runtime credential gate and no credentialed live evidence is claimed here. Product discovery remains research data; no purchase or checkout authority is inferred.
- TheMealDB's official V1 surface and development key support prototype recipe normalization; public appstore/production use requires its supporter arrangement and terms review.
- ntfy's publish headers disable server cache and Firebase forwarding for synthetic qualification; provider acceptance is intentionally not human delivery/read evidence.
- Google Calendar direct REST is the bounded GA surface with runtime OAuth bearer credentials and deterministic event identity/readback; the official Calendar MCP is preview/reference and is not adopted.

## ANIMA-HA-P10-DURABLE-TASK-ENGINE-012 — durable task prior art

- Date checked: 2026-08-31
- Trigger: Phase 10 requires restart-safe declarative one-shot/recurring future work, and the directive requires current primary-source comparison before implementation.
- Sources: [Hatchet documentation](https://docs.hatchet.run/v1), [Hatchet embedded/self-hosting documentation](https://docs.hatchet.run/v1/embedded), [hatchet-sdk PyPI metadata](https://pypi.org/pypi/hatchet-sdk/json), [APScheduler PyPI metadata](https://pypi.org/pypi/APScheduler/json), [APScheduler repository](https://github.com/agronholm/apscheduler), [Temporal Python SDK PyPI](https://pypi.org/project/temporalio/1.32.0/), [Temporal Python SDK repository](https://github.com/temporalio/sdk-python), [croniter PyPI](https://pypi.org/project/croniter/), [PostgreSQL SELECT locking](https://www.postgresql.org/docs/18/sql-select.html).
- Freshness: primary upstream/package sources checked 2026-08-31. Current observed versions: `hatchet-sdk 1.38.1`, `APScheduler 3.11.3` with `4.0.0a6` prerelease history, `temporalio 1.32.0`, and `croniter 6.2.4`.

### Comparison and disposition

| Candidate | License / current evidence | Fit, cost, persistence, portability, replacement path | Decision |
| --- | --- | --- | --- |
| Existing PostgreSQL 16 + Psycopg | PostgreSQL License; already qualified in ANIMA | Durable local substrate, transactional uniqueness, JSONB, UTC database time, `FOR UPDATE SKIP LOCKED`; already supports ARM64 image path and existing migration boundary | ADOPT / WRAP |
| Direct ANIMA task/schedule/run implementation | No new dependency; preserves typed declarative payloads, provenance, policy boundary, and replacement path | Exact Phase 10 ownership; prevents executable payloads and stale-authority replay; small bounded surface | BUILD |
| `croniter 6.2.4` | MIT; PyPI publishes a `py3-none-any` wheel and Python 3.12 classifier; current release 2026-07-10 | Narrow next-occurrence calculation only; pure Python/ARM64-friendly package shape; cron strings remain data and ANIMA owns persistence/misfire/DST policy | ADOPT / WRAP conditionally |
| Hatchet `hatchet-sdk 1.38.1` | MIT; official docs describe a durable task/workflow platform, self-hosting, PostgreSQL, retries, queues, and event log | Strong capability and Python SDK, but adds an engine/API/gRPC/sidecar and a second durable state boundary; overlaps ANIMA task/run/event/policy ownership and increases Pi footprint | DEFER |
| Temporal Python SDK `1.32.0` | MIT; Python 3.10+; SDK uses Rust SDK Core and a separate Temporal server | Strong distributed workflow durability, timers, replay, and activities, but disproportionate service/worker/history architecture for bounded Phase 10 reminders and cognition opportunities | DEFER |
| APScheduler `3.11.3` | MIT; production/stable; Python 3.12; supports one-off, interval, cron, and persistent jobs | Useful misfire/coalescing/concurrency prior art and in-process integration, but callable/job-oriented persistence is not ANIMA declarative task ownership; 4.x is a prerelease redesign | REFERENCE / DEFER |
| Direct standard-library recurrence | No dependency | Suitable for ONCE and fixed-duration INTERVAL; implementing cron/DST correctly would duplicate mature parsing and recurrence logic without reducing ANIMA ownership | REFERENCE; use only for non-cron primitives |

### Boundary conclusion

Build the canonical `DurableTask`, `TaskSchedule`, and `DurableTaskRun` model and dispatcher over existing PostgreSQL/Psycopg. Use short `FOR UPDATE SKIP LOCKED` claim transactions and database timestamps; never hold a transaction through cognition or external execution. Wrap `croniter 6.2.4` only behind an ANIMA `RecurrenceCalculator`, with explicit five-field cron validation, persisted IANA timezone, deterministic DST handling, and a replacement path. Scheduled work emits a guaranteed `scheduled_reasoning_due` event and re-enters fresh Context/Policy/Agent boundaries; it never stores or replays future physical tool calls or old authorization.

### Recheck triggers

Reconsider a workflow service only after measured Phase 10 scale, long-running multi-step workflow, cross-process orchestration, or operational evidence shows PostgreSQL cannot provide the required delivery/recovery behavior. Requalify `croniter` on version, Python/ARM64 packaging, DST behavior, or recurrence semantics changes.

## ANIMA-HA-P11-EXTERNAL-GATE-CLOSURE-013H — OAuth and live-resource recheck

- Date checked: 2026-08-31
- Freshness: official Google and Brave documentation rechecked for this bounded continuation.
- Sources: [Google Calendar OAuth scopes](https://developers.google.com/workspace/calendar/api/auth), [Google installed-app OAuth](https://developers.google.com/identity/protocols/oauth2/native-app), [Google web-server OAuth and refresh](https://developers.google.com/identity/protocols/oauth2/web-server), [Calendar event creation](https://developers.google.com/workspace/calendar/api/guides/create-events), [Brave Web Search API](https://api-dashboard.search.brave.com/api-reference/web/search/get), [Brave Place Search](https://api-dashboard.search.brave.com/api-reference/web/place_search), [Brave API privacy notice](https://api-dashboard.search.brave.com/documentation/resources/privacy-notice), and [Brave API pricing](https://brave.com/search/api/).
- Decision: retain Google Calendar direct REST and Brave Search API. Google runtime uses refreshable `google-auth` credentials and the owned-calendar scope `https://www.googleapis.com/auth/calendar.events.owned`; no SearXNG or browser automation is introduced.
- Evidence: Brave web/place/product and Google Calendar list/create-readback are independently reported by the live harness. Both currently return `EXTERNAL_RESOURCE_GATE` because credentials are absent. Open-Meteo, TheMealDB, and ntfy synthetic evidence remains passing.

## Walmart product research qualification — 2026-09-01

- Existing implementation source: LedgerMind on the Atlas laptop at `/home/sketch/Projects/LedgerMind`, using the signed Walmart.io affiliate Product API v2 path. The repository was inspected read-only; its production smoke harness reported successful signature, catalogue, stores, keyword search, ZIP-scoped item pricing, and store-scoped item pricing probes. Cart push/checkout was explicitly unsupported.
- ANIMA disposition: `ADOPT/WRAP` the existing operator-entitled read-only contract behind `WalmartProductProvider`; do not copy `.env`, credential values, private-key material, or runtime data. ANIMA fixes the HTTPS host/path, request bounds, RSA-SHA256 signature boundary, secret names, result normalization, timestamps, and `EXTERNAL_UNTRUSTED` classification.
- Current official Walmart developer documentation primarily documents Marketplace OAuth APIs, including [item search](https://developer.walmart.com/global-marketplace/reference/getsearchresult), [catalog search](https://developer.walmart.com/global-marketplace/docs/item-search-for-the-walmart-catalog), and [API integration and usage](https://developer.walmart.com/us-marketplace/docs/api-integration-usage). Those public docs are not treated as proof of the LedgerMind affiliate path; the latter is supported here by inspected source plus status-only live smoke evidence.
- Live ANIMA evidence, with LedgerMind's operator environment mapped into ANIMA's trusted secret boundary, returned 9 distinct Walmart references for `wireless headphones` and 10 for `air fryer`. Each result carried provider reference/source URL and externally timestamped price/availability where supplied. Evidence class: `LIVE_CREDENTIALED` on Atlas x86-64.
- Provider constraints: no independent terms/cost requalification of the operator's existing Walmart entitlement was performed in this bounded continuation; the key/path remain an operator provisioning boundary. Missing or unreadable settings remain `EXTERNAL_RESOURCE_GATE_WALMART_PRODUCT_SEARCH`. No purchase, checkout, physical-home, production-scale, or Phase 12 claim is made.
- SearXNG remains the general web provider. eBay HTML extraction and other retailer scraping remain rejected; Open Products Facts and Best Buy were not added after the existing provisioned Walmart path met the live product usefulness target.
- Privacy/credential boundary: Brave API queries may be retained for up to 90 days according to its privacy notice; query minimization remains required. Google client secret, refresh token, and ephemeral access token remain outside model input, audits, Event Journal, Notion, and Git.
- Recheck triggers: operator credentials become available; Google scope/installed-app OAuth behavior changes; Brave API endpoint/auth/privacy terms change; or a provider defect requires current external behavior.

## ANIMA-HA-P11-FREE-LOCAL-REALIGNMENT-013R — Current provider decision

- Date checked: 2026-09-01.
- The prior Brave/Google qualification above is historical and superseded for
  the current prototype path by the Architect’s free/local realignment.
- Decision: `ADOPT / WRAP` private pinned SearXNG for bounded web/product JSON
  search; `ADOPT / WRAP` OpenStreetMap Overpass for bounded category-mapped POI
  reads; `BUILD` the first-party PostgreSQL calendar. Brave Search and Google
  Calendar are `SUPERSEDED / DEFERRED`.
- SearXNG is configured as a private local service with fixed engines,
  loopback-only qualification exposure, no public instance, no image proxy,
  and no Valkey. Overpass uses a fixed HTTPS host and no raw query tool.
- The local calendar uses migration `0012_local_calendar.sql`, trusted
  invocation provenance/idempotency, household isolation, optimistic version
  checks, and Core-approved policy-gated internal mutations. Future physical
  actions remain Phase 9-coordinated.
- Evidence: implementation `558c689cac96f3bddbd636b4d1b9e20d055b221d` / CI
  `33458814906`; final governed `6343b22e687fa5f2a031cb8c12ef5bf1301436a8` /
  CI `33458890546`; 134 tests, static/build/OPA/migration, healthy no-Valkey
  SearXNG, Overpass, PostgreSQL calendar, and AgentRuntime integration passed.

## Phase 11 bounded qualification — 2026-09-01

- SearXNG documentation for the adopted `2026.8.29+d226b78bc` release confirms
  JSON search API support, engine `!bang` syntax, and that the limiter requires
  Valkey. The private deployment keeps `limiter=false`, `public_instance=false`,
  JSON-only output, and no Valkey. The immutable image digest remains
  `sha256:b36af7984b87191b595bc5301418ed6432c047668a4547ab531a7439b816fac3`
  with amd64, arm64, and arm/v7 manifests.
- Candidate disposition: `REJECT` Startpage and Qwant as additional configured
  general engines for this qualification. Live tests against the same pinned
  image returned upstream CAPTCHA responses for both, as did DuckDuckGo at the
  target time. Preserve the bounded `duckduckgo` plus Wikipedia reference set;
  expose engine errors and let strict target validation report the product gate.
- Overpass remains `ADOPT / WRAP` for bounded synthetic POI lookup. The public
  OSM documentation says the main instance can be used below 10,000 queries/day
  and 1 GB/day; this prototype remains far below that and sends only bounded
  category-mapped queries.
- Trigger for recheck: a new SearXNG release, repeated upstream CAPTCHA/error
  behavior after target-network qualification, materially different Pi resource
  measurements, or an Architect-authorized provider decision.

## ANIMA-HA-P11-WALMART-ENTITLEMENT-QUALIFICATION-013R3 — Walmart entitlement

- Date checked: 2026-09-01. Disposition: `BLOCKED — WALMART_CLARIFICATION_REQUIRED`.
- Primary sources: [Walmart Affiliates FAQ](https://affiliates.walmart.com/faqs), [Walmart Affiliates Operating Agreement](https://affiliates.walmart.com/terms), and [Walmart developer API License Agreement](https://developer.walmart.com/global-marketplace/docs/terms-and-conditions). The FAQ establishes that joining is free but subject to acceptance. The Affiliate Agreement requires approved Affiliate Websites, Walmart/Platform Qualifying Links, clear/conspicuous disclosure, direct linking, restricted redistribution, Program-purpose licensing, and product price/availability updates within 24 hours of updates. The current developer API-license page is contextual only because it does not establish governance of the exact affiliate endpoint.
- Existing project evidence: LedgerMind at `/home/sketch/Projects/LedgerMind` was inspected read-only on Atlas. Its runbook/source identifies the signed Walmart.io affiliate Product API v2 path at `developer.api.walmart.com/api-proxy/service/affil/product/v2`, stage/production application keys, and optional Impact publisher ID. Prior sanitized smoke evidence proves technical operation, not entitlement scope.
- Exact endpoint status: `UNKNOWN` as active/legacy/deprecated from current authoritative public documentation. The endpoint's HTTP success and Walmart.io site availability do not prove current support, migration expectations, or license scope.
- Key unresolved questions: whether ANIMA is an approved application/surface; whether LedgerMind credentials may be reused cross-project; whether private local assistant consumption/display is covered; whether ordinary Walmart item URLs satisfy qualifying-link rules; whether publisher ID is mandatory; exact data retention/cache and AI/automation rules; exact rate limits; and account-specific fees.
- No dashboard was available through an already-authorized Codex session. No login, application registration, agreement acceptance, support contact, account mutation, credential inspection, or implementation change occurred.
- Required recheck trigger: operator supplies nonsecret dashboard metadata or Walmart provides written clarification covering ANIMA's application/surface, cross-project reuse, data display, link/disclosure, freshness/cache, cost, and endpoint support obligations.

## ANIMA-HA-P11-BEST-BUY-PRODUCT-PROVIDER-013R4 — qualification result

- Official Best Buy sources checked 2026-09-01: API catalog https://developer.bestbuy.com/apis, API documentation https://bestbuyapis.github.io/api-documentation/, and Terms and Conditions https://developer.bestbuy.com/legal.
- Products API is described as active; it covers current/historical products and fields including pricing, availability, specifications, descriptions, and images. Public documentation describes ordinary email API-key registration; Commerce API is invite-only and out of scope; published limits are 50,000 calls/day and 5 calls/second.
- Published obligations include clear attribution, preserved supplied links, Best Buy branding where API content appears in an Application, no third-party API access/key transfer, and no storage/cache of Content beyond 72 hours.
- ANIMA compatibility finding: full sanitized external tool results are persisted indefinitely by PostgresEpisodeStore in anima_agent_tool_requests.sanitized_result; no provider-content expiry or purge path exists. This conflicts with the 72-hour rule and triggers the directive's stop condition.
- Cost/key finding: UNKNOWN; no account/key was created or inspected and no BEST_BUY_API_KEY value was present in the process environment. Public registration instructions alone do not prove zero-cost issuance.
- Disposition: BLOCKED — BEST_BUY_RETENTION_COMPLIANCE. Do not integrate Best Buy until Architect authorizes a bounded retention/compliance design. Walmart remains DEFER — ENTITLEMENT_CLARIFICATION; no fallback is active. No secrets, account settings, or Phase 12 behavior were touched.

## ANIMA-HA-P11-UPCITEMDB-PRODUCT-PROVIDER-013R6 — Product-provider qualification

- Date checked: 2026-09-01
- Sources: [UPCitemdb API Explorer](https://upcitemdb.com/api/explorer), [API documentation](https://www.upcitemdb.com/api/), [plan comparison](https://www.upcitemdb.com/wp/docs/main/development/plan/), [rate-limit documentation](https://www.upcitemdb.com/wp/docs/main/development/api-rate-limits/), [terms](https://www.upcitemdb.com/terms), and [privacy policy](https://www.upcitemdb.com/privacy).
- Problem: replace the Best Buy key gate with a no-signup/no-key household product-search route without scraping or arbitrary network access.
- Qualification matrix:

  | Need | Evidence | Decision |
  | --- | --- | --- |
  | Product discovery | `/prod/trial/search`, live JSON results, product identity and offers | ADOPT / WRAP |
  | Cost/auth | Free Explorer, no signup, no API key, 100 combined requests/day | ADOPT / WRAP |
  | Search quota | Public docs disagree on 20 vs 40 free searches/day; plan comparison states 20 | Conservative 20/day |
  | Burst/pacing | Docs state burst limits; ANIMA adds 15-second minimum interval | ADOPT bounded limiter |
  | Terms | Limited/terminable service-use license; accuracy/availability disclaimer; customer responsible for third-party rights | ADOPT restricted/untrusted |
  | Affiliate data | API docs state Amazon/eBay sales data shown on site is not redistributed through API | Do not infer omitted offers |
  | Product quality | Five distinct EAN-identified products for each required live query; 13/19 offers | PASS target |
  | Privacy/retention | No ANIMA credential/account; full results are restricted live-only | EPHEMERAL_RESTRICTED |
  | Best Buy | New key onboarding operationally unavailable | DEFER |
  | Walmart | Cross-project entitlement unresolved | DEFER |
- Disposition: `ADOPT / WRAP` UPCitemdb for the active semantic `shopping.search_products` capability. Preserve Best Buy/Walmart source and history, but neither is an active fallback. Recheck provider docs/terms before production or material usage expansion.
