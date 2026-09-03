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

## ANIMA-HA-P10-TASK-POLICY-INTEGRATION-012H — Durable task authority boundary

- An AgentRuntime that routes every non-read-only tool through physical-action coordination makes trusted local task persistence fail closed. A Core-owned execution boundary is required: task mutations remain Phase 5/4 policy-gated internal state changes, while provider side effects remain Phase 9 coordinated.
- Provenance and creation idempotency are invocation facts, not task content. Deriving them from the current episode/tool-request identity prevents model-selected creator claims and preserves deterministic replay.
- PostgreSQL lifecycle guards must be expressed as atomic allowed-source predicates, and dispatch must require the same live claimant and lease at both begin and completion. Deterministic event IDs do not authorize stale workers.
- Cancellation around `CLAIMED -> DISPATCHING` requires an explicit rule: before event append, terminalize the dispatching run without emitting the event; after append, preserve the event and reconcile honestly.

## ANIMA-HA-P11-EXTERNAL-CAPABILITIES-013 — External capability boundaries

- External providers must return bounded normalized data with explicit `EXTERNAL_UNTRUSTED` trust, attribution/source references, freshness, and provider metadata; provider text never becomes instructions, policy, identity, or Household Graph authority.
- Fixed-host HTTPS, no redirects, explicit method/path allowlists, private-IP rejection, response-size limits, and secret-free request audit records provide a small replaceable egress boundary. Audit records can be adapted into the append-only Event Journal without storing authorization headers or secret values.
- Provider availability is an independent resource gate. Missing Brave or Google Calendar credentials must not disable no-credential weather/recipe capabilities or synthetic notification qualification, and a gate is not evidence of provider success.
- Consequential external writes require Core-owned Phase 9 profiles. Calendar acknowledgement is insufficient without provider readback; ntfy acknowledgement establishes provider acceptance only, not human delivery or read status. Retailer checkout/cart automation remains outside the bounded prototype.
- Direct Google Calendar REST is the current bounded integration surface; the official Calendar MCP is reference/deferred while it remains preview. OAuth credential commissioning and native ARM64/Pi qualification remain separate evidence work.

## ANIMA-HA-P11-WALMART-ENTITLEMENT-QUALIFICATION-013R3 — Entitlement evidence

- A successful signed request to a retailer API proves technical reachability, not that the account/application is authorized for a different project or surface.
- Affiliate terms written around approved websites and qualifying links cannot be silently generalized to a private local assistant. When the exact application scope, link format, data-use rights, or current legacy endpoint terms are unavailable, the correct state is `BLOCKED — WALMART_CLARIFICATION_REQUIRED`.
- Free program enrollment does not establish zero cost for a specific API entitlement; account-specific fees, rate limits, and support status must remain `UNKNOWN` until verified from the entitlement or a current governing pricing/support record.

## ANIMA-HA-P11-RESTRICTED-CONTENT-PERSISTENCE-013R5 — Retention boundary

- A provider retention restriction is best enforced at the Core persistence boundary: keep the full bounded result in the active process, persist structural evidence and digests, and avoid a cleanup daemon whose backup/export races could preserve stale content.
- Restricted content must taint the whole episode. Blocking every later tool, including reads, prevents model-echoed provider content from entering another durable or external sink while preserving the current caller's live answer.
- Provider identity and trust classification are not enough to enforce retention: the Core must derive `EPHEMERAL_RESTRICTED` from the canonical tool identity and ignore plugin-supplied durability claims.
- A successful CI/test result does not close a provider gate when credentials are absent. Best Buy deterministic normalization is implemented, but live product usefulness remains an explicit `EXTERNAL_RESOURCE_GATE_BEST_BUY_KEY`.

## ANIMA-HA-P11-UPCITEMDB-PRODUCT-PROVIDER-013R6 — No-key product research

- The UPCitemdb free Explorer is callable without signup or credentials through `/prod/trial/search`, but its public documentation currently disagrees on the free search quota. A conservative ANIMA limiter should assume 20 searches/day, pace searches at least 15 seconds apart, and obey live `X-RateLimit-*` and `Retry-After` headers.
- UPCitemdb returns useful real product identity for ordinary categories, but offer timestamps can be materially old and historical price fields are not current retail offers. Preserve timestamps and never promote them to household Truth.
- UPCitemdb offer links are provider-returned redirects and should be preserved rather than rewritten; product content remains `EXTERNAL_UNTRUSTED` and Core `EPHEMERAL_RESTRICTED` because the database aggregates third-party sources and its terms disclaim accuracy/availability.
- Best Buy developer onboarding is deferred as operationally unavailable for this prototype and Walmart remains entitlement-blocked. UPCitemdb is the active no-key product path; no automatic fallback is permitted.

## ANIMA-HA-P12-CUSTOM-LOCAL-INTERFACE-014

- Keep the UI as a semantic ANIMA boundary: read models return normalized household summaries and command gateways are the only mutation seam.
- OAuth access tokens are transient coroutine data; session records retain only hashed cookie/CSRF values and exact mapped household/principal identifiers.
- A browser UI can be validated independently with deterministic test auth, but that does not prove the host has composed the real journal, attention, context, AgentRuntime, policy, or Phase 9 command bridges.
- SSE should carry bounded invalidation names only; clients refetch semantic view models rather than receiving raw events or provider payloads.
- Phase 13 behavior remains unauthorized.

## ANIMA-HA-P12-CORE-INTEGRATION-PORTFOLIO-CLOSURE-014H

- The UI can synchronously drive the existing PostgreSQL Attention path for a newly appended event by priming an event-scoped consumer cursor; this avoids replaying unrelated historical backlog while retaining the canonical Attention implementation.
- The configured `create_app()` path must select the Core composition when `ANIMA_DATABASE_URL` is present; absent required configuration remains an explicit unavailable/development state and must not silently enable the test echo.
- UI mutation adapters should resolve canonical registered tool IDs (`anima.durable-tasks` and `anima.calendar`) and pass controls to the existing Phase 9 coordinator rather than calling domain services directly.
- Browser screenshots captured by the in-app exporter were JPEG bytes despite `.png` names; publication assets must be MIME-verified and converted to actual PNG files before commit.

## ANIMA-HA-P12-COMMISSIONED-RUNTIME-TRUTH-CLOSURE-014H2

- Production identity must resolve from commissioned provider references to a canonical person and graph membership, never from a UI fallback map or display name. Exact-zero and multi-target results are distinct fail-closed outcomes.
- The normal PostgreSQL composition can register no-key/qualified Phase 11 providers without activating Walmart or Best Buy; Home Assistant must remain unavailable until its instance, websocket, provider scope, and secret reference are complete.
- Production read models must consume the graph, Truth projection, and plugin registry. A missing provider is an explicit capability/state result, not a reason to reuse deterministic demo household content.

## ANIMA-HA-P12-FINAL-UX-AUTHORITY-ACCEPTANCE-CLOSURE-014H3

- UI policy context must resolve semantic role from the commissioned graph at the Core boundary for each request; a browser session proves identity but must not carry or choose authorization role.
- OAuth callback state needs a browser-bound nonce cookie in addition to a server-side expiring single-use state record; state-only validation does not bind the initiating browser.
- Capability health is a projection, not a static manifest label: plugin enablement, latest provider error, and external audit evidence must distinguish available from degraded and unavailable.
- Calendar UI mutation needs the server-projected optimistic-concurrency version; otherwise a later update can unknowingly reuse a stale expected version.
- Persistent PostgreSQL evidence targets must be rerunnable against existing fixtures. Synthetic commissioning IDs/scopes must not collide across separate targets, or the production resolver correctly fails closed on ambiguous mappings.

## ANIMA-HA-P12-VERIFIED-UX-E2E-CLOSURE-014H4

- Browser controls must adapt to the qualified semantic schema (`desired_on`); accommodating a browser alias in the HA manifest would weaken the Core contract.
- For coordinated actions, connector acknowledgement is only evidence. The UI gateway must project the Phase 9 terminal action record, and the browser should publish the semantic outcome after refetch so visible state and feedback converge.
- A real configured browser composition requires CI to provision the same PostgreSQL/OPA prerequisites as local Core validation; otherwise a test-only acceptance server fails before the UI starts.
- Passing Core/API and isolated-provider harnesses does not equal browser E2E. Dedicated browser journeys must be distinguished from supporting API/harness evidence, especially for denial, degraded providers, restricted content, and restart recovery.

## ANIMA-HA-P12-BROWSER-ACCEPTANCE-EVIDENCE-CLOSURE-014H5

- A hosted UI container can fail before health because installed package resources are absent from the image; the Phase 4 policy bundle must be copied into the runtime image when `PolicyBundle.from_repository()` resolves relative to the installed Python prefix.
- Compose cleanup in an intermediate CI step must not tear down shared PostgreSQL/OPA services needed by a later browser acceptance step. Stop only the temporary UI container and leave final cleanup to the job-level teardown.
- H5 hosted acceptance must use deterministic external fixtures; live public-provider responses are environment-dependent and are not a valid substitute for browser/Core provider degradation and audit evidence.
- Passing a deterministic Core/API target plus a green Playwright smoke matrix does not establish browser-visible denial, restricted-content reload/storage, same-session process restart/SSE, or browser-visible provider recovery. Those evidence classes remain explicit until dedicated journeys run.
- Hosted Compose readiness must be gated on container health plus a final database readiness check before migrations; a single readiness probe can pass during PostgreSQL startup and immediately fail on the next check.
