# Major Project Record

Use this ledger for major architecture decisions, strategic reversals, project milestones, important failures, governance migrations, and other events a future Architect/Coder must understand.

---

## ANIMA-HA-P0-RUNTIME-BASELINE-002 — Phase 0 runtime baseline

- Date: 2026-08-28/29
- Decision: Adopt Python 3.12.x, uv lockfiles, pinned Ruff/pytest/mypy tooling, Psycopg behind an ANIMA database boundary, and a pinned pgvector PostgreSQL 16 image for runtime-only persistence proof.
- Boundary: Phase 0 infrastructure only; no household intelligence or Phase 1 product semantics.
- Evidence: Full checks/build pass on an allowlisted local-filesystem reproduction; x86-64 database health/restart/persistence pass; ARM64 is manifest/wheel evidence only.
- Recheck: Before native Pi acceptance, image refresh, or Phase 1 schema/service expansion.

---

## AUTHORITY-BOOTSTRAP-001 — Authority 3.0 adopted for ANIMA HA

- Date: 2026-08-28
- Type: GOVERNANCE
- Related directive/outcome: AUTHORITY-BOOTSTRAP-001

### Context

ANIMA HA is a new project with an adopted working-prototype goal and no existing implementation state. A durable Architect → Codex → evidence → Architect loop is required before implementation begins.

### Decision / event

Applied Authority 3.0 as the project governance contract. Installed the root router, reusable Codex workflow, project-state/history ledgers, evidence/safety contracts, external-discovery workflow, and a project-specific Architect startup prompt.

### Evidence

Authority 3.0 Complete Installation Package retrieved from the connected Notion Authority documentation; initial project directory inspection found no pre-existing files or repository state.

### Consequence

Future work must begin by reading the mandatory state kernel, resolving one bounded directive, preserving append-only evidence, qualifying significant dependencies, and reporting the canonical Codex result. The adopted project goal may not be silently narrowed.

---

## ANIMA-HA-P0-GOVERNANCE-BASELINE-001 — Public governed repository baseline reconciled

- Date: 2026-08-28
- Type: MILESTONE
- Related directive/outcome: ANIMA-HA-P0-GOVERNANCE-BASELINE-001

### Context

The local Authority bootstrap predated discovery of the existing public GitHub repository and incorrectly recorded Git/GitHub as not created.

### Decision / event

Adopted the existing remote `main` history as the local parent, corrected the local repository/profile/checkpoint state, and published the reviewed Authority governance baseline without product implementation.

### Evidence

Remote `main` was observed at `088b267467fff93bfd225b9a94a6f4999759fb9f` with a clean two-file tree. Governance baseline commit `6fbabc892f53876fd94614ccc531dc7478a80288` preserves that parent. SSH fetch and public-safety review passed; the machine-specific local GVFS path was removed from the publishable profile, and no secrets or runtime data were found.

### Consequence

`main` now has one coherent governance history through `6fbabc892f53876fd94614ccc531dc7478a80288`. Product implementation remains deferred until the Architect reviews this checkpoint and issues a separate bounded directive.

## ANIMA-HA-P1-REALITY-SUBSTRATE-003 — Phase 1 reality substrate

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Related directive/outcome: `ANIMA-HA-P1-REALITY-SUBSTRATE-003`

### Decision / event

Adopted PostgreSQL 16 through the existing Psycopg boundary as the canonical Phase 1 event journal and derived truth substrate. Built the ANIMA event/observation contracts, deterministic reconciliation, projection retry boundary, and replay/rebuild. Deferred NATS/JetStream and aggregate event-sourcing frameworks; rejected KurrentDB/EventStoreDB as the prototype foundation.

### Evidence

Unit/static/build validation and synthetic x86-64 PostgreSQL integration passed for concurrent deduplication, append-only enforcement, source ordering, uncertainty/conflict semantics, journal-first projection retry, restart persistence, and rebuild equivalence. Full checkpoint details are in the completed task packet.

### Consequence

Phase 2 can consume a stable provider-independent reality substrate. No Household Graph, memory, policy, Home Assistant, Luna, or later behavior is included.

## ANIMA-HA-P2-HOUSEHOLD-GRAPH-004 — Canonical semantic household graph

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Related directive/outcome: `ANIMA-HA-P2-HOUSEHOLD-GRAPH-004`

### Decision / event

Adopted an ANIMA-owned relational canonical graph on PostgreSQL 16 with
recursive CTE traversal, typed semantic relationships, commissioned UUID
identity, separate provider references, aliases, Truth bindings, and Phase 1
journal mutation audit. Brick/Haystack are reference material only; AGE and
NetworkX are not canonical persistence; Graphiti is deferred.

### Evidence

Pure validation and x86-64 PostgreSQL integration cover the synthetic topology,
cycle/reference/entrance validation, recursive resources, aliases, provider
mapping/remap, Truth provenance, idempotent commissioning, audit, and restart.
No Home Assistant or physical-home evidence is claimed.

### Consequence

Phase 3 may consume semantic household identity after Architect review. Memory,
policy, Home Assistant, Luna, plugins, actions, durable tasks, UI, and voice
remain out of scope until separately authorized.

## ANIMA-HA-P3-GOVERNED-MEMORY-005 — Governed local memory

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Related directive/outcome: `ANIMA-HA-P3-GOVERNED-MEMORY-005`

### Decision / event

Built canonical ANIMA memory on the existing PostgreSQL/Psycopg boundary with
typed provenance, deterministic precedence, append-oriented lifecycle, and a
disposable local lexical index. Added a deterministic journal-derived routine
model. Mem0, local embeddings, LangGraph, Letta, Graphiti, and River remain
deferred; no new service was introduced.

### Evidence

Contract/unit checks and synthetic x86-64 PostgreSQL integration passed for
memory lifecycle, explicit/inferred precedence, temporary expiry, retraction,
cross-household isolation, index rebuild/fallback, Truth separation, journal
audit, routine rebuild/update, and restart persistence. Phase 1/2 regressions,
full validation, package build, simulator, and public-safety checks passed.

### Consequence

Phase 4 may consume relevant governed memory after Architect review. Identity,
policy, permissions, Home Assistant, Luna, plugins, actions, durable tasks,
UI, and voice remain out of scope.

## ANIMA-HA-P4-IDENTITY-POLICY-006 — Deterministic identity and policy milestone

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Decision: Adopt and wrap local OPA/Rego 1.20.1 behind ANIMA-owned identity, intent, risk, confirmation, audit, and fail-closed contracts.
- Evidence: OPA policy tests, x86-64 PostgreSQL integration, restart persistence, simulator, Phase 1–3 regressions, static validation, package validation, and public-safety scan passed.
- Boundary: No policy-write runtime API, memory authority, Home Assistant, Luna, plugin, action-execution, physical identity, or real-home behavior was introduced.
- Consequence: Phase 5 Plugin Runtime remains gated on independent Architect review of this checkpoint.

## ANIMA-HA-P5-PLUGIN-CAPABILITY-RUNTIME-007 — Governed capability boundary

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Decision: Build an ANIMA-owned plugin/capability registry and adopt/wrap MCP Python SDK `2.1.1` plus `jsonschema 4.26.0`; keep plugin metadata subordinate to Phase 4 policy.
- Evidence: x86-64 unit/integration/simulator evidence, PostgreSQL migration/restart/persistence, real local MCP stdio exchange, OPA-gated invocation, CI `33277823326`, fresh-checkout build/validation, and public-safety scan passed at implementation checkpoint `c186c34bcf93e9ff03d39c3e966fcb540583d478`.
- Boundary: Native plugins are trusted in-process; optional MCP plugins are supervised out-of-process. No runtime package installation, policy/permission mutation, raw secrets, Home Assistant, Luna, physical actions, or later behavior were introduced. Subprocess is not a malicious-code sandbox.
- Consequence: Phase 6 Home Assistant Adapter remains pending Architect review.
## ANIMA-HA-P6-HOME-ASSISTANT-ADAPTER-008 — Governed Home Assistant substrate boundary

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Decision: Adopt/wrap `hass-client==1.2.3` behind an ANIMA-owned adapter and test against pinned Home Assistant Core `2026.8.2`; retain HA IDs as scoped provider references and require Phase 4/5 policy plus observed-state verification for low-risk control.
- Evidence: real isolated x86-64 HA WebSocket/registry/service runtime, PostgreSQL Truth/Journal/mapping persistence, OPA gating, restart/gap behavior, 43 tests, strict static/build validation, and CI `33284454470` on `ecae55af1894889e0948d11a9ae01288c217c646` passed.
- Boundary: no physical-device claim, generic HA service tool, credential persistence, blind canonicalization, API-acknowledgement success, Luna, or Phase 7 behavior.
- Consequence: Phase 7 remains gated on independent Architect acceptance.

## ANIMA-HA-P7-ATTENTION-CONTEXT-009 — Deterministic cognition-opportunity boundary

- Date: 2026-08-29
- Type: MILESTONE / ARCHITECTURE
- Decision: Build typed ANIMA attention and sparse ContextPackets on the existing PostgreSQL journal/state stack; preserve guaranteed reasoning, immutable profile-qualified decisions, restart-safe aggregation, explicit Truth uncertainty, ANIMA-owned trust/egress, and side-effect-free replay. CloudEvents SQL/CEL/OpenTelemetry remain reference; CEL runtimes and NATS remain deferred.
- Evidence: implementation `77aafbe5f78333b1c50d042fb1ceb19e74dbe698`, CI `33286882961`, 50 tests, strict static/build checks, 10,020-event PostgreSQL restart/replay target, Phase 1–5 integrations, real isolated Phase 6 HA regression, simulator/replay CLI, and public-safety review passed.
- Boundary: attention selects when future cognition may run; no rule selects an action. Context inclusion does not grant authority. No Luna, cloud call, autonomous behavior, new physical-device behavior, CEL, or NATS was introduced.
- Consequence: Phase 8 remains gated on independent Architect review and explicit authorization.

## ANIMA-HA-P8-CODEX-OAUTH-RUNTIME-010R — Operator-selected constrained cognition milestone

- Date: 2026-08-30
- Type: MILESTONE / ARCHITECTURE / OPERATOR RULING
- Decision: Preserve the prior Agents SDK/API-key directive as superseded history and adopt/wrap Codex CLI ChatGPT OAuth for Luna 5.6 medium cognition behind an ANIMA-owned durable structured loop. Codex receives no direct shell, file, MCP, web, app, plugin, database, HA, or policy capability; all requested tools remain Phase 5/4 governed.
- Evidence: live x86-64 OAuth A–I matrix, 84 tests, PostgreSQL episode restart/duplicate protection, strict static/build/OPA, Phase 1–7 regressions, real isolated Phase 6 HA, public safety, and GitHub Actions `33293828743` on `8486cd10b7962df11898bc8b61b1ec46d0809dd5` passed.
- Boundary: no OAuth token inspection, API key, API-dollar estimate, raw reasoning persistence, physical action, native ARM64/Pi claim, generalized Phase 9 execution/concurrency, durable task, UI, or voice behavior.
- Consequence: Phase 9 remains gated on independent Architect acceptance of the governed Phase 8 closure.

## ANIMA-HA-P9-ACTION-EXECUTION-CONCURRENCY-011 — Deterministic action boundary

- Date: 2026-08-30
- Type: MILESTONE / ARCHITECTURE
- Decision: Build ANIMA-owned action coordination and durable action/effect records; adopt/wrap PostgreSQL session-level advisory locks for non-blocking canonical-resource conflict detection; reuse Phase 4 policy, Phase 5 gateway, Phase 6 provider refresh/verification, and Phase 8 bridge. Reference Stripe-style parameter-bound idempotency; reject Redis/Redlock as foundational fencing; defer Temporal/Hatchet and future work to Phase 10.
- Evidence: 10 focused tests, 94-test local-filesystem regression, Ruff, strict mypy, migration repeat, durable PostgreSQL replay, real PostgreSQL advisory-lock conflict, and the isolated HA coordinator harness passed. The live harness executed the real pinned HA 2026.8.2 virtual entity through the coordinator, verified post-action state, demonstrated a contradictory two-principal same-resource conflict, and replayed without a second connector call.
- Boundary: no transaction spans an external call; stale conflicting requests are not queued; ambiguous effects are not retried; partial effects are not compensated; live HA evidence is isolated virtual/demo x86-64 only; no native Pi or physical-home claim.
- Consequence: Phase 9 is complete pending independent Architect review; Phase 10 remains unauthorized.

## Phase 10 task-policy integration hardening — 2026-08-31

- Architect disposition: `CONTINUE`; Phase 9 is accepted and Phase 11 remains unauthorized.
- The Phase 10 scheduler substrate remains valid. The bounded correction hardens the AgentRuntime execution boundary, trusted task provenance/idempotency, PostgreSQL lifecycle parity, worker lease ownership, cancellation cleanup, and fresh scheduled-cognition integration.
- Implementation checkpoint `27f7c3fb8ce53c4eb988d7de22c63672770998a8` passed hosted CI `33425928381`. Governed evidence closure follows as a separate documentation checkpoint and remains pending Architect acceptance.

## Phase 10 scheduled-action evidence correction — 2026-08-31

- The bounded Phase 10 correction adds an explicit due-time synthetic consequential action to the scheduled-cognition harness. It verifies fresh due-time cognition, Phase 9 routing, fresh pre/post observation, one connector call, and a verified successful action record without changing the scheduler architecture.
- Corrected implementation checkpoint `945f89c13b67e52a9027d3f42cc3e2bccd5608d2` passed exact hosted CI `33428295199`.
- The earlier governed checkpoint `17d627b988aebb89b419671de8ee3c5a5525f516` is superseded for this closure. Phase 10 remains pending Architect acceptance and Phase 11 remains unauthorized.

## Phase 11 external-by-intent capabilities — 2026-08-31

- Type: MILESTONE / ARCHITECTURE / EXTERNAL-DISCOVERY
- Decision: Build bounded ANIMA-owned weather, discovery, recipes, Calendar, notification, trust, egress, audit, and provider-gate contracts. Wrap Open-Meteo, Brave, TheMealDB, Google Calendar REST, ntfy, and httpx; retain Google auth packages for the commissioning boundary; defer Calendar MCP preview and retailer checkout/cart automation.
- Safety: Provider data is `EXTERNAL_UNTRUSTED`; credentials/configuration/hosts/topics are runtime-owned; Calendar and notification writes use exact Core-owned Phase 9 profiles and observation/receipt verifiers, never connector claims alone.
- Evidence: implementation `17252304a4f0642bb654ec612cfcb55a01411804`, CI `33442439042`, 130 tests, pinned OPA 4/4, package build, Phase 1–10 harnesses, isolated real HA Phase 6, and live synthetic Open-Meteo/TheMealDB/ntfy traffic passed.
- Boundary: Brave and Google Calendar are explicit `EXTERNAL_RESOURCE_GATE` without credentials; no production-provider, native ARM64/Pi, physical-home, human-delivery, or Phase 12 claim is made.

## Phase 11 free/local realignment — 2026-08-31

- Type: MILESTONE / ARCHITECTURE / VALIDATION
- Directive: `ANIMA-HA-P11-FREE-LOCAL-REALIGNMENT-013R`; Architect disposition `CONTINUE`; Phase 12 unauthorized.
- Decision: supersede/defer Brave and Google Calendar; adopt/wrap private pinned SearXNG and OpenStreetMap Overpass; build first-party PostgreSQL calendar with migration `0012_local_calendar.sql`.
- Evidence: 134 tests, Ruff, strict mypy, OPA 4/4, package build, ordered migration initial/repeat, healthy no-Valkey SearXNG web/product JSON, Overpass synthetic POI, and actual AgentRuntime local-calendar path passed in local-filesystem reproduction.
- Boundary: calendar mutations are Core-approved `POLICY_GATED_INTERNAL`; physical/provider actions remain Phase 9-coordinated; no Phase 12 behavior, native ARM64/Pi, production-scale, physical-home, or human-delivery claim.

## Phase 11 free/local hardening — 2026-09-01

- Architect directive `ANIMA-HA-P11-FREE-LOCAL-HARDENING-013R1` remains `CONTINUE`; Phase 11 implementation hardening is complete but the strict product-search live target is `EXTERNAL_RESOURCE_GATE`. Phase 12 remains unauthorized.
- Decision: retain the existing Phase 4 vocabulary and classify local calendar mutation as `LOW_RISK_HOME_CONTROL` under the Core-owned `POLICY_GATED_INTERNAL` boundary. Do not weaken external/provider or physical Phase 9 semantics.
- Evidence: real OPA/PostgreSQL calendar target matrix passed authorization, replay/key conflict, lifecycle/version/reconnect/isolation/audit, and no-Phase-9-record checks. SearXNG bang controls, engine failures, image manifest, resource, restart, and strict-target behavior were qualified.
- Provider finding: DuckDuckGo, Startpage, and Qwant all returned upstream CAPTCHA during local target qualification; no second free general engine was adopted. Wikipedia reference search remained available for a public result, while product search remains blocked by the external resource gate.
- Implementation checkpoint `c24b8eab5abe9acc31b4f54a321b0270399f3549` passed hosted CI `33462705630` on the exact SHA; governed evidence closure follows.
- Governed evidence closure checkpoint `bf62877bcddd4683e4e7c046c2cb0233ef84f0b5` passed hosted CI `33462809329` on the exact SHA. Phase 11 remains `CONTINUE` / `IMPLEMENTATION COMPLETE — EXTERNAL_RESOURCE_GATE`; Phase 12 remains unauthorized.

## Phase 11 product research provider decision — 2026-09-01

- Architect continuation `ANIMA-HA-P11-PRODUCT-RESEARCH-CLOSURE-013R2` remains `CONTINUE` pending acceptance. The remaining shopping blocker was resolved at implementation/evidence level by wrapping the already-provisioned LedgerMind Walmart signed product API path.
- This is a bounded provider decision: Walmart read-only product search is ANIMA-owned, fixed-host, locally signed, SecretBroker-backed, provenance-preserving, timestamped, and untrusted. General web search remains private SearXNG. No retailer scraping, CAPTCHA bypass, browser automation, cart, checkout, or new service was introduced.
- Provisioned live evidence met the target with 9 distinct headphone candidates and 10 distinct air-fryer candidates. Absent operator settings remain an explicit Walmart resource gate. The operator's external entitlement terms/cost were not independently requalified in this continuation and remain a stated limitation.
- Phase 12 remains unauthorized.

## Phase 11 Walmart entitlement qualification — 2026-09-01

- Type: GOVERNANCE / EXTERNAL-DISCOVERY / BLOCKER
- Directive: `ANIMA-HA-P11-WALMART-ENTITLEMENT-QUALIFICATION-013R3`; Architect disposition `INVESTIGATE — PROVIDER ENTITLEMENT QUALIFICATION`.
- Technical state is preserved: Walmart-backed product research at governed SHA `a1122b32d1e9d6548b5c78bd1256185d60b4d281` and CI `33501648332` remains technically qualified, with no implementation change.
- Decision: `BLOCKED — WALMART_CLARIFICATION_REQUIRED`. The current public Affiliate terms require approved affiliate surfaces and qualifying-link/disclosure/data-freshness compliance, while LedgerMind records do not prove that ANIMA HA is an approved or covered surface. The exact legacy affiliate API support and account-specific application scope remain unresolved.
- Phase 12 remains unauthorized. No account mutation or secret handling was performed.

## Phase 11 Best Buy provider qualification — 2026-09-01

- Type: EXTERNAL-DISCOVERY / GOVERNANCE / BLOCKER
- Best Buy was requalified as the proposed replacement for Walmart. Official sources support an active Products API with ordinary key registration, bounded search, 50,000/day and 5/sec limits, and separate invite-only Commerce API. Terms require attribution, preserved links, branding where content appears, and Content storage/cache no longer than 72 hours.
- Direct repository evidence shows current PostgreSQL agent tool-request persistence stores full sanitized external results indefinitely. Because this violates the Best Buy retention rule and the directive requires a stop before changing accepted evidence semantics, no provider code was added.
- Result: BLOCKED — BEST_BUY_RETENTION_COMPLIANCE. Walmart is preserved but deferred; Phase 12 remains unauthorized.

## Phase 11 restricted external-content persistence — 2026-09-01

- Architect directive `ANIMA-HA-P11-RESTRICTED-CONTENT-PERSISTENCE-013R5`; disposition `CONTINUE / HARDEN`; Phase 12 unauthorized.
- Starting repository head was `67b72bf52e1f45e33b9c35a1c0c89e87cf47f7ee` with hosted CI `33509333301` passed. The directive authorized a bounded retention correction and conditional Best Buy integration, not a Phase 12 expansion.
- Decision: Core maps Best Buy tool identities to `EPHEMERAL_RESTRICTED`. The active process may answer from full bounded provider content, but durable episode/tool/turn/database-export paths receive structural metadata, hashes, provenance, trust, policy, and explicit redaction markers. Tainted episodes block all later tools.
- Decision: add a fixed-host Best Buy Products API wrapper with SecretBroker-only API-key input and bounded semantic `shopping.search_products`; no Walmart fallback, scraping, Commerce API, or UI was added.
- Evidence: real PostgreSQL scan across all public `anima_*` text/JSON/JSONB columns and an in-process full-table JSON export found zero synthetic product/price sentinels, while the live response contained them. Duplicate replay did not reconstruct a live response. Full pytest/static/type/build/OPA and Phase 10 regression evidence passed; one known pre-existing unrelated Phase 5 script remains repository-wide Ruff-dirty.
- Current gate: `EXTERNAL_RESOURCE_GATE_BEST_BUY_KEY`; no live Best Buy request or credential value was inspected. Phase 11 remains pending Architect review.

## ANIMA-HA-P11-UPCITEMDB-PRODUCT-PROVIDER-013R6 — Product-provider replan

- Date: 2026-09-01
- Architect disposition: `REPLAN / CONTINUE`; Best Buy `DEFER — DEVELOPER_ONBOARDING_UNAVAILABLE`; Walmart `DEFER — ENTITLEMENT_CLARIFICATION`; Phase 12 unauthorized.
- Decision: adopt/wrap UPCitemdb free Explorer behind the existing semantic `shopping.search_products` action after live qualification. Use fixed `api.upcitemdb.com` HTTPS, no credentials, Core `EPHEMERAL_RESTRICTED` content persistence, and no provider fallback.
- Evidence: direct live `wireless headphones` and `air fryer` searches returned five distinct EAN-identified products each, with 13 and 19 bounded offers respectively. The live API reported `X-RateLimit-Limit=100`, and the harness observed remaining counts `93` and `92` after the two required calls.
- Governance result: implementation and live public-synthetic product gate are complete, but this record does not claim Architect acceptance of Phase 11. No Phase 12 behavior was implemented.

## ANIMA-HA-P12-CUSTOM-LOCAL-INTERFACE-014 — Local interface implementation

- Date: 2026-09-01
- Authority: Phase 11 accepted at `918365ce7c6145780112a808411d750fb0e289eb`, CI `33562645002`; Phase 12 authorized; Phase 13 unauthorized.
- Implemented locally: FastAPI/Uvicorn ANIMA API, HA OAuth bootstrap adapter, exact user-to-principal mapping, hashed server sessions and CSRF, semantic household read models, bounded invalidation SSE, React/Vite UI, migration `0013_ui_sessions.sql`, Dockerfile/Compose, and deterministic/browser validation.
- Not claimed: real HA OAuth, native Pi deployment, or production Core conversation/command composition. The default production service fails closed until the existing Core bridges are injected; test auth's echo response is explicitly test-only.
- Governance state: pending fresh validation, implementation publication, final governed evidence closure, hosted CI, Notion reconciliation, and Architect review.

## 2026-09-02 — H5 browser acceptance evidence continuation

- Architect disposition remains `CONTINUE`; Phase 12 is not accepted.
- H5 current published head is `800d8cf4a183ce0e7548545182ed09f0687ad98f`; hosted CI `33696481738` passed on that exact SHA and artifact `9872060277` was published.
- The head includes bounded display-mode behavior, deterministic H5 Core/API evidence, and CI fixes for the runtime policy bundle and Compose service lifetime. Missing browser-level denial, provider recovery, restricted-content reload/storage, same-session restart/SSE, and browser-visible isolated-HA evidence remain open.
- Phase 13 remains unauthorized.

## 2026-09-03 — H5 governance/CI reliability checkpoint

- Published governance checkpoint `828230a73d3c9097bab448192747a3f6786c0d4f`; hosted CI `33697593173` passed on the exact head.
- A bounded workflow readiness fix waits for healthy PostgreSQL/OPA containers before migration after governance-head run `33697435341` hit a transient PostgreSQL readiness race.
- H5 remains `CONTINUE — IMPLEMENTATION/EVIDENCE PARTIAL; PENDING ARCHITECT ACCEPTANCE`; no Phase 13 behavior was implemented.

## ANIMA-HA-P12-CORE-INTEGRATION-PORTFOLIO-CLOSURE-014H — Implementation publication

- Date: 2026-09-02
- Architect disposition: `CONTINUE`; Phase 12 production integration and portfolio closure authorized; Phase 13 unauthorized.
- Published implementation checkpoint: `208b7e546d8485539d2ae06427d268af116f9ceb`; hosted CI `33580734640` passed on the exact head.
- Decision: wire the normal configured UI into accepted Core services through one composition module; retain test-only echo and demo seams only for explicit test/development configuration.
- Evidence boundary: deterministic integrated cognition and policy-gated task mutation are reproduced; real Home Assistant OAuth/commissioning, live Luna, physical-home behavior, native ARM64/Pi, production TLS, and live household data remain unclaimed.

## ANIMA-HA-P12-COMMISSIONED-RUNTIME-TRUTH-CLOSURE-014H2 — 2026-09-02

- Architect disposition: `CONTINUE`; Phase 12 remains pending acceptance; Phase 13 unauthorized.
- Decision: make commissioned graph identity, PostgreSQL Truth/read models, Core plugin registry, and configured accepted providers the normal production composition. Retain demo/test seams only behind explicit test configuration.
- Local evidence: exact graph identity mapping, real OPA task/calendar mutation, and real PostgreSQL Journal/Attention/Context/AgentRuntime conversation passed; HA is explicitly unavailable without operator commissioning.

## ANIMA-HA-P12-CONFIRMATION-CONTINUATION-FINAL-ACCEPTANCE-014H5U — 2026-09-03

- Architect disposition: `CONTINUE — FINAL PHASE 12 CORRECTNESS CLOSURE`; starting governed checkpoint `684806ae53832ddd40cd0ee000ffbe35609a8ff2`; Phase 13 unauthorized.
- Decision: implement durable exact-intent confirmation continuation inside the accepted Phase 4/5/8/9 boundaries. No new workflow engine, broker, database, provider, or authority store was added.
- Local evidence: PostgreSQL pending-approval migration/verifier passed; focused and full validation passed; H4/H5 Core, isolated-HA API, restricted-content, frontend, and clean-filesystem browser reproduction passed. H5T's prior task `ValueError` remains historical negative evidence.
- Publication state: implementation and final governed SHA/CI are recorded by superseding governance entries after push; Phase 12 remains pending Architect acceptance.

### H5U publication correction — 2026-09-03

- Implementation SHA `dbb4720882b25ad1d840c2c270191227f0c4ea1d` passed hosted CI
  `33746353829` on the exact head.
- Final governed SHA `b2049f306416a1d0cd4f61cd370d0686c5bec2d7` passed hosted CI
  `33747181905` on the exact head and was verified on `origin/main`.
- Phase 12 remains pending Architect acceptance; Phase 13 was not implemented.

## ANIMA-HA-P12-TRUE-AGENT-RESUME-INTEGRATED-ACCEPTANCE-014H5V — 2026-09-03

- Architect review disposition: `CONTINUE — H5U PARTIALLY ACCEPTED; PHASE 12 NOT ACCEPTED`.
- Decision: continue inside the accepted Phase 4/5/8/9 boundaries by making approval/rejection a genuine same-episode AgentRuntime continuation. No workflow engine, new infrastructure, or Phase 13 behavior was added.
- Current implementation adds migration `0016_agent_continuations`, durable context/transcript reconstruction, normalized continuation result persistence, UI continuation routing, and a real-OPA PostgreSQL verifier.
- Current local evidence is `E3_TARGET_TESTED` for the H5V target. Full regression, hosted CI, final governance, and Architect acceptance remain open.

## ANIMA-HA-P12-TRUE-AGENT-RESUME-INTEGRATED-ACCEPTANCE-014H5V-R1 — 2026-09-03

- Architect disposition: `CONTINUE`; H5V-R1 implementation is retained, Phase 12 remains unaccepted, and Phase 13 remains unauthorized.
- Starting checkpoint `761f6214993a676bdd43f911e237dffbbee7a684`; implementation checkpoint `8bcff850a56b0bd8b3a70cc4d837e1268e12716f`; CI isolation checkpoint `58636eaec87a9ad4ddd0958b916a4d74b2d9fe74`.
- Hosted CI `33818551425` passed on the exact final checkpoint. Artifact `9917602062` digest: `sha256:257886d0b85f485bc2b103cdfc55b159618a00bb6c72f46f14f8b0352237464b`.
- H5V-R1 adds continuation lifecycle/fencing/recovery, original catalogue/runtime binding, pre-dispatch durable preflight, cumulative active-runtime accounting, exact policy-intent propagation, dedicated management projections, and test-only browser approval/rejection tests.
- Local evidence: 174 Python tests, Ruff, strict mypy, OPA 7/7, migrations, H5V Core/true-resume verifiers, frontend checks/tests/build, existing browser matrix, dedicated H5V browser 2/2, package build, diff-check, and public-safety scan passed.
- Remaining evidence is explicitly open: complete browser denial/strong-auth/provider/restricted/restart/SSE journeys, dirty task/calendar fixture, crash/concurrency ledger, and browser-visible isolated-HA outcomes. This record does not self-accept Phase 12.

## ANIMA-HA-P13-SENTRY-INTEGRATION-QUALIFICATION-015B-R3 — 2026-09-04

- Architect continuation retained the R2 SENTRY boundary while requiring
  household/client-scoped direct interaction identity, persisted evidence-ID
  binding, consistent origin enforcement, and actual SenseGuard event routing.
- The ANIMA-side correction is implemented and locally regression-protected.
  Phase 13 remains pending Architect acceptance because the protected SENTRY
  host, physical SenseGuard trigger, and voice path were not available for live
  qualification. Phase 14/15 remain unauthorized.

## R3 exact-head hosted validation — 2026-09-04

- Head `da9b6de2aceb34e36a51c400dcf8b090e010115d` passed hosted CI
  `33933037033` on the exact head; artifact `9959297861` was published.
- The hosted targets covered the existing deterministic boundary, Core/UI,
  frontend, container, safety, and evidence checks. Live/shadow SENTRY,
  physical SenseGuard, voice, and live household mutation remain unclaimed.
- Phase 13 remains `CONTINUE` and is not self-accepted; Phase 14/15 remain
  unauthorized.

## ANIMA-HA-P13-SENTRY-RUNTIME-COMPATIBILITY-CERTIFICATION-015B-R4 — 2026-09-05

- R4 qualifies the actual installed MCP/SENTRY runtime without modifying the
  protected SENTRY V0.4 source. ANIMA implementation head
  `20e3e0763328ed327c7d80d73264344d6054339f` passed exact-head hosted CI
  `33938016240`; artifact `9960893002` was published.
- Actual MCP 2.1.1/Python 3.12.3 stdio evidence passes direct and queued
  request flows, schemas, provider-start ordering, read, governed mutation,
  result submission, and terminal status. Codex CLI `0.153.1` shadow loading
  and `anima_health` succeeded without ANIMA credentials.
- The protected SENTRY office launcher remains incompatible: it points to
  `SENTRY/integrations/tools/sentry_mcp_server.py`, but the server is at
  `SENTRY/tools/sentry_mcp_server.py`. Because fixing that requires protected
  SENTRY-side authority, the result is
  `NEEDS_ARCHITECT_DECISION — PHASE13_RUNTIME_COMPATIBILITY_BLOCKED`.
- Phase 14/15 and ANIMA voice remain unauthorized; this record does not
  self-accept Phase 13.
