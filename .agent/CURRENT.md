# Current Project State

Last updated: 2026-09-01

## Current stage

PHASE 11 RESTRICTED EXTERNAL-CONTENT PERSISTENCE HARDENING — IMPLEMENTED, PENDING ARCHITECT REVIEW

## Current objective

Close the Best Buy product-research gate without violating its published 72-hour content-retention limit. Best Buy is conditionally integrated behind a Core-owned `EPHEMERAL_RESTRICTED` persistence boundary; full provider content remains live-only and durable records retain structural projections/digests. Walmart remains preserved but deferred pending entitlement clarification. Phase 12 is unauthorized.

## Active directive

`ANIMA-HA-P11-RESTRICTED-CONTENT-PERSISTENCE-013R5` — implement Core-owned restricted external-content persistence, prove database/export safety, and conditionally integrate Best Buy behind the boundary. Phase 10 is Architect accepted at `2c8f88f62c27a728b2bf0861dabaf7a3a3d03e56`; Phase 11 remains `CONTINUE / HARDEN` pending Architect review; Phase 12 is unauthorized.

## Current verified state

- Phase 11 restricted-content implementation checkpoint: `b810c853b47470c4395dd1a5731e59da98ae41a5`; hosted CI `33525400264` passed on that exact SHA. Best Buy remains conditionally integrated behind the Core-owned retention boundary; its live key is absent.

- Best Buy qualification checkpoint: governance commit
  `7f5ddb0844195e2d558a2fbd24fac3101ae1d34e` is pushed to `origin/main` and
  hosted CI `33509082116` passed on that exact SHA. The final evidence-closure
  commit records the same outcome and its CI below.

- Product-research closure started from governed Phase 11 checkpoint `23aa71d774c75529d7e8412e3060446d42a9cf4d`.
- LedgerMind at `/home/sketch/Projects/LedgerMind` was inspected read-only on the Atlas laptop. Its status-only Walmart smoke test passed signature, catalogue, stores, and item-price probes; cart push remained unsupported. ANIMA copied the bounded contract, not credentials or runtime data.
- ANIMA now exposes `anima.external.shopping.search_products` through a fixed `developer.api.walmart.com` host, ANIMA-generated RSA-SHA256 request signatures, trusted `SecretBroker` references, normalized `ProductCandidate` plus `retail_offer` data, timestamped external price/availability, and `EXTERNAL_UNTRUSTED` results. No cart, checkout, browser automation, scraping, CAPTCHA bypass, or arbitrary host is implemented.
- Real AgentRuntime integration and provider tests pass. Credentialed Atlas live evidence returned 9 distinct candidates for `wireless headphones` and 10 for `air fryer`; both met the three-candidate usefulness threshold. Without the three operator secret references and a readable signing key, the provider remains an explicit `EXTERNAL_RESOURCE_GATE`.
- Fresh locked validation: `uv sync --locked --dev`, Ruff, strict mypy, full pytest (`139 passed`), OPA, package sdist/wheel, `git diff --check`, and public-safety review passed. SearXNG/Overpass and existing Phase 1–10 evidence remain unchanged.
- The product provider is implementation-complete and provisioned-resource qualified, but this record does not assert Architect acceptance of Phase 11. Phase 12 behavior remains absent and unauthorized.

### Current entitlement investigation

- Architect disposition: `INVESTIGATE — PROVIDER ENTITLEMENT QUALIFICATION`.
- Outcome: `BLOCKED — WALMART_CLARIFICATION_REQUIRED`.
- LedgerMind records identify the working endpoint as the signed Walmart.io affiliate Product API v2 path at `developer.api.walmart.com`, with consumer ID/key version/private-key credentials and optional Impact publisher ID. LedgerMind documentation does not establish that ANIMA HA is an approved Walmart affiliate surface or that the entitlement is transferable across applications.
- Current official Walmart Affiliate terms require acceptance, reserve approval of each Affiliate Website, require Qualifying Links rather than unqualified direct links, require clear/conspicuous advertising disclosure for Qualifying Links, restrict redistribution/repurposing of Qualifying Links, limit Walmart IP use to Program purposes, and require product information including price/availability to be updated within 24 hours of an update. These terms do not resolve whether a private local assistant is an approved surface or whether the exact legacy API path has separate data-use terms.
- Current official Walmart developer documentation found during this investigation is primarily Marketplace/API-license material and does not re-establish the exact affiliate `affil/product/v2` entitlement. The exact account/application metadata was not available through an already-authorized dashboard session. No inference is made from HTTP 200 or prior smoke-test success.
- Cost is `UNKNOWN` for the specific entitlement: the Affiliate Program FAQ says joining is free, while the current API-license terms allow fees if communicated. Exact affiliate-API rate limits and support/deprecation status are also `UNKNOWN`.
- Required operator/Walmart clarification: confirm the application's approved surface(s), production entitlement, cross-project reuse by ANIMA HA, private-local-assistant/data-display permission, qualifying-link/publisher-ID requirements, disclosure language, freshness/cache rule, and support status for `affil/product/v2`. Until resolved, Walmart remains a technically qualified but authorization-blocked candidate, not an accepted Phase 11 provider.

- The project directory was empty before this bootstrap.
- Phase 0 now contains only runtime/engineering baseline code; no household intelligence or product behavior is implemented.
- The local project is a Git repository on `main`, configured with the required identity and connected to `git@github.com:SketchOTP/ANIMA-Home-Automation.git`.
- The existing GitHub baseline commit is `088b267467fff93bfd225b9a94a6f4999759fb9f` and contains `.gitignore` and `LICENSE`.
- The requested ANIMA HA goal is adopted at the prototype boundary `ANIMA_HA_PROTOTYPE_GOAL_COMPLETE`.
- The canonical Notion SSOT is the ANIMA HA Authority, Product Specification & Cold-Start Handoff page.
- Authority 3.0 governance files are installed and published in governance baseline commit `6fbabc892f53876fd94614ccc531dc7478a80288`.
- Python 3.12.x, uv 0.12.7, pinned development tooling, PostgreSQL 16.15/pgvector 0.8.6, migrations, structured logging, simulator scenarios, normalized event/observation contracts, append-only journal, deterministic truth projection, failure tracking, rebuild, tests, and CI are implemented in the current working tree.
- Phase 1 event identity, source deduplication, journal position, event/record time, source sequence, provenance, freshness, explicit unknown/unavailable/conflict states, projection retry, and replay/rebuild remain green.
- Phase 2 adds ANIMA-owned canonical graph nodes, typed relationships, recursive containment, entrance connectivity, separate resources/capabilities, aliases, provider references, Truth bindings, transactional commissioning, semantic queries, and graph mutation audit events.
- Phase 3 adds ANIMA-owned canonical memory records, provenance/taxonomy, deterministic precedence, correction/supersession, expiry/retraction, household-isolated retrieval, a rebuildable PostgreSQL lexical index with explicit fallback, and a journal-derived routine model.
- Phase 4 adds ANIMA-owned identity evidence and assurance aggregation, semantic action intents and risk classes, exact confirmation challenges, a local pinned OPA/Rego evaluator, PostgreSQL decision persistence, journaled policy audit, explicit autonomy configuration, and fail-closed policy behavior.

## Current hypotheses / unknowns

- Native Raspberry Pi execution has not yet been performed; ARM64 support is evidenced by image manifest and wheel metadata only.
- This SFTP-mounted workspace cannot reliably create a `.venv` symlink or complete mypy traversal; an allowlisted local-filesystem copy passes the full validation and build gate.
- No native Raspberry Pi run has been performed; ARM64 remains manifest/package evidence only.
- The canonical journal, truth projection, graph, memory store, derived lexical index, and routine model are PostgreSQL/Psycopg implementations behind ANIMA-owned interfaces. NATS/JetStream, graph extensions, NetworkX persistence, Graphiti, Mem0, FastEmbed, and River remain deferred or rejected for the current phase.
- OPA/Rego `1.20.1` remains the only Phase 4 policy evaluator, pinned by multi-architecture image digest. Cedar remains reference-only; Casbin and OpenFGA are not runtime dependencies.
- Phase 5 accepted prerequisite is Phase 4 governed SHA `50ea9c73e31b2037120da5d12e04555fa08b1da5` with CI run `33271197523`; Phase 5 implementation checkpoint is `c186c34bcf93e9ff03d39c3e966fcb540583d478` with CI `33277823326`. Any later closure commit contains metadata/evidence only.

## Phase 6 implementation state

- Phase 5 is Architect accepted at `b426d66e7293a132dcdb4abaa96bc7594cdf7b73`; CI `33277980009` passed.
- Phase 6 wraps `hass-client==1.2.3` against pinned HA Core `2026.8.2`, preserving provider references, Phase 1 normalization, Phase 2 mappings, Phase 4 policy, and Phase 5 lifecycle/tools.
- Real isolated HA evidence passes for discovery, WebSocket events, registry reconcile, explicit uncertainty, low-risk service execution, observed-state verification, deliberate verification failure, reconnect/gap, invalid auth, and restart.

## Phase 7 implementation state

- Phase 6 is Architect accepted at governed checkpoint `e1488d9a2d6280945cc2fd8bdba435733f0ba287`; GitHub Actions run `33284537147` passed.
- Phase 7 implementation checkpoint is `77aafbe5f78333b1c50d042fb1ceb19e74dbe698`; GitHub Actions run `33286882961` passed on that exact SHA.
- PostgreSQL-backed deterministic attention, guaranteed-event bypass, durable cursor/cooldown/rate/aggregation state, immutable decisions, durable reasoning triggers, sparse ContextPackets, trust/egress classification, and side-effect-free replay/profile comparison are implemented.
- Target evidence passed with 10,000 ordinary plus 20 guaranteed source events, restart after 5,000, exactly four aggregate and 20 guaranteed triggers, complete source journal, live/replay equivalence, context digest persistence, and Profile A/B comparison.
- Typed ANIMA predicates and existing PostgreSQL were selected; CloudEvents SQL, CEL, and OpenTelemetry remain reference material; CEL runtimes and NATS/JetStream remain deferred. No new service or runtime dependency was added.

## Phase 8 qualification state

- Phase 7 is Architect accepted at governed checkpoint `44d4f59737aeed9aa55583eb49823a37535d607d`; GitHub Actions `33287068428` passed.
- Codex CLI `0.150.0-alpha.8` reports `Logged in using ChatGPT` without credential inspection.
- The installed model catalog lists `gpt-5.6-luna` with `medium` reasoning support.
- An isolated strict-config live probe succeeded using ChatGPT OAuth, Luna, medium reasoning, ephemeral mode, ignored user config/rules, read-only sandbox, disabled shell/unified-exec/multi-agent/apps/plugins/web/image/memory/dependency-install controls, and no direct capability event.
- The documented `tools.view_image=false` spelling is unsupported by this CLI; the stable equivalent `features.view_image=false` is supported and is the required adapter mapping.
- Phase 8 implementation checkpoint is `8486cd10b7962df11898bc8b61b1ec46d0809dd5`; GitHub Actions `33293828743` passed without OAuth credentials.
- Durable episodes, cloud-safe projection, versioned instructions, strict isolated `codex exec`, structured sequential decisions, Phase 5/4 tool-policy routing, result filtering, budgets/timeouts, audit, fake CI adapter, and simulator parity are implemented.
- The final live A–I matrix passed with 14 Luna turns, model-selected one/two-tool sequences, three no-action outcomes, confirmation/stronger-auth stops, honest tool failure, prompt-injection containment, and zero forbidden direct capability events.

## Phase 9 implementation state

- ANIMA-owned `ActionExecutionCoordinator` is implemented in `src/anima_ha/action.py` and can be inserted between Phase 8 agent decisions and the Phase 5 gateway for consequential tools.
- Durable `anima_actions` and `anima_action_effects` records are added by migration `0010_action_execution.sql`; idempotency keys are unique and parameter mismatches are explicit conflicts.
- Canonical resource UUIDs use non-blocking PostgreSQL session-level advisory locks. Conflicts return immediately and are not queued behind stale intents; no PostgreSQL transaction remains open across the connector call.
- The coordinator refreshes latest state after lock acquisition, validates caller-supplied Truth preconditions, re-evaluates Phase 4 policy, records `EXECUTING` before the external call, refreshes again after the call, and requires observed verification for consequential tools.
- Ambiguous timeout/error results become `UNKNOWN_RESULT`; mixed effect results become `PARTIAL`; no blind retry or automatic compensation is performed. Restart reconciliation marks planned work `RECOVERY_REQUIRED` and in-flight work `UNKNOWN_RESULT`.
- Focused evidence: 10 Phase 9 tests plus existing suite; local-filesystem Ruff, strict mypy, and 94-test suite passed; PostgreSQL migration/repeat, durable replay, and real advisory-lock conflict passed; the isolated pinned HA coordinator harness passed real `set_power`, contradictory two-principal same-resource contention, post-action refresh, and durable replay.

### Phase 9 hardening corrections

- Trusted `ActionSafetySpec` metadata owns canonical lock scopes, mandatory Truth preconditions, expected effects, and optional provider-native-idempotency capability. The live AgentRuntime path attaches baseline known-state preconditions before coordinator submission.
- `ProviderExecutionContext` carries ANIMA execution identity and an optional provider idempotency key outside model-visible schemas. Providers without native idempotency remain executable under local ANIMA deduplication and observation-first recovery.
- Connector acknowledgements/effect claims are evidence only. Fresh post-dispatch observation and verification derive terminal effect/outcome status, including timeout-success, unknown, definitive-failure, partial, and already-satisfied no-dispatch cases.

## Phase 10 hardening state

- Task mutations are ANIMA-owned `POLICY_GATED_INTERNAL` capabilities; task reads are `READ_ONLY`; physical/provider side effects remain `COORDINATED_CONSEQUENTIAL` and continue through Phase 9.
- Only Core-approved built-in durable-task tools receive the internal boundary; raw plugin metadata cannot lower an external tool into that boundary.
- AgentRuntime generates trusted household, principal, episode, tool-request, ordinal, origin, and system-idempotency context. Creator provenance and creation idempotency are absent from model-visible task schemas.
- PostgreSQL and in-memory lifecycle guards match. Dispatch requires the current worker's live unexpired claim; cancellation cannot leave an in-flight dispatch run orphaned.
- Due tasks still emit guaranteed deterministic `scheduled_reasoning_due` events, scheduled cognition builds a fresh ContextPacket, and later physical actions remain Phase 9-coordinated.
- Corrected implementation checkpoint: `945f89c13b67e52a9027d3f42cc3e2bccd5608d2`; hosted CI `33428295199` passed on that exact SHA.
- The earlier governed checkpoint `17d627b988aebb89b419671de8ee3c5a5525f516` is superseded for closure purposes by the corrected scheduled-cognition evidence. Final governed evidence checkpoint: `ae18833e2ddffd30b17b613248d1c2206062b66a`; hosted CI `33428938215` passed on that exact SHA.

## Current blockers

- Best Buy is conditionally implemented, but its live credential is absent: `EXTERNAL_RESOURCE_GATE_BEST_BUY_KEY`. No live Best Buy product claim is made.
- Implementation checkpoint `b810c853b47470c4395dd1a5731e59da98ae41a5` and hosted CI `33525400264` passed on the exact SHA. The final governed evidence checkpoint and CI will be recorded after the governance closure commit.
- The 72-hour retention conflict is addressed by Core classification `EPHEMERAL_RESTRICTED`: full bounded provider results exist only in the active process; PostgreSQL episode/tool/turn rows and whole-database JSON export contain only structural projections, hashes, metadata, and explicit retention markers.
- A restricted result taints the episode. The active caller receives the full live answer, but durable response/decision/argument records are redacted and all later tool requests are blocked with `RESTRICTED_EXTERNAL_CONTENT_SIDE_EFFECT_BLOCKED`.
- Walmart remains `DEFER — ENTITLEMENT_CLARIFICATION`; it is not an active fallback. Phase 11 remains `CONTINUE / HARDEN`, pending final publication and Architect review.
- Native ARM64/Pi, physical-home, production-scale, commercial-provider, human-notification-delivery, and high-risk external-write evidence remain unclaimed.
- Phase 12 custom interfaces, UI, voice, checkout, compensation, and other successor behavior remain unauthorized.

## Latest accepted evidence

- `AUTHORITY-BOOTSTRAP-001`: governance package installed and inspected; `E2_REPRODUCED` for the bootstrap artifact set only. This is not implementation or prototype acceptance evidence.
- Remote baseline `088b267467fff93bfd225b9a94a6f4999759fb9f`: observed and preserved as the Git history parent.
- Phase 0 acceptance checkpoint is `e68fc6240e5ae922f4e289b9ccdb7ed9f9babfe0`; GitHub Actions run `33232686789` passed.
- Phase 1 implementation checkpoint is `0ee72b736aa27e1b52d652eafb8e045e4b892148`; GitHub Actions run `33252987351` passed for that exact SHA.
- Phase 1 evidence is recorded in `.agent/tasks/completed/ANIMA-HA-P1-REALITY-SUBSTRATE-003/EVIDENCE.md`.
- Phase 2 evidence is recorded in `.agent/tasks/completed/ANIMA-HA-P2-HOUSEHOLD-GRAPH-004/EVIDENCE.md` after checkpoint closure.
- Phase 2 implementation checkpoint is `ed261e8a3bc794ededdc3084f63b816152988820`; GitHub Actions run `33261359336` passed for that exact SHA.
- Phase 3 implementation checkpoint is `0410cdb148cfcf42021d83bf73a6d239fab37a1d`; the final governed metadata checkpoint is recorded in the completed task evidence and Notion after push verification.
- Phase 4 accepted governed checkpoint is `50ea9c73e31b2037120da5d12e04555fa08b1da5`; accepted CI run is `33271197523`. Later metadata-only self-reference is not treated as a new product acceptance.

## Current risks

- Native Raspberry Pi runtime/resource qualification and backup/restore remain future evidence items.
- Truth bindings currently consume generic Phase 1 keys; Home Assistant source adapters must remain external-reference mappings when introduced.
- Public-repository publication requires continued exclusion of secrets, credentials, and runtime state.
- Mem0/FastEmbed remain unadopted; any future semantic index must first qualify telemetry, offline behavior, model licensing, native ARM64/Pi resource use, and canonical-store rebuild.
- OPA has official amd64/arm64 image manifests and local REST/policy-test support, but native Raspberry Pi execution and resource measurement remain unverified. No remote bundle or decision-log egress is configured.
- Phase 5 MCP and subprocess evidence will be synthetic/x86-64 unless a native ARM64 run is explicitly performed; subprocess isolation is not a malicious-code sandbox.
- Phase 5 adds `mcp==2.1.1` and `jsonschema==4.26.0`, ANIMA-owned manifest/lifecycle/registry contracts, policy-gated native/MCP invocation, scoped secrets/configuration, declared plugin events, persistence, and failure containment. Streamable HTTP is adapter-supported but not exercised against a permanent remote endpoint.
- Phase 9 action coordination is implemented against the Phase 5 gateway and PostgreSQL; live provider evidence is isolated virtual HA on x86-64. No native ARM64/Pi or physical-home execution evidence exists. The installed Codex CLI remains pre-stable and Phase 9 does not add a production connector.

## Next Architect decision point

Review `ANIMA-HA-P11-RESTRICTED-CONTENT-PERSISTENCE-013R5` after exact-SHA publication. The implementation/evidence result is `CONTINUE / HARDEN`; Best Buy live validation remains `EXTERNAL_RESOURCE_GATE_BEST_BUY_KEY`. Phase 12 remains unauthorized.

## Phase 10 publication state

- Starting governed checkpoint: `21dde3cddc3ea4aa5af3e59e6a0334b62d37a7a2`; hosted CI `33418246958` passed.
- Earlier implementation checkpoint: `27f7c3fb8ce53c4eb988d7de22c63672770998a8`; hosted CI `33425928381` passed.
- Corrected implementation checkpoint: `945f89c13b67e52a9027d3f42cc3e2bccd5608d2`; hosted CI `33428295199` passed.
- Status remains `COMPLETE — PENDING ARCHITECT ACCEPTANCE`; this is not an Architect acceptance claim.
- Final governed evidence checkpoint: `ae18833e2ddffd30b17b613248d1c2206062b66a`; hosted CI `33428938215` passed on that exact SHA.

## Phase 11 external capability state (superseded historical record)

The earlier Brave/Google provider record below is retained for audit history only.
It is superseded for current implementation and gate decisions by
`ANIMA-HA-P11-FREE-LOCAL-REALIGNMENT-013R`.

- Phase 10 is Architect accepted at `2c8f88f62c27a728b2bf0861dabaf7a3a3d03e56`; hosted CI `33429217008` passed.
- Phase 11 baseline implementation checkpoint `17252304a4f0642bb654ec612cfcb55a01411804`; hosted CI `33442439042` passed on the exact SHA.
- Bounded ANIMA-owned adapters now cover Open-Meteo weather, Brave web/place/product discovery, TheMealDB recipes, Google Calendar REST, and ntfy notifications. External content is `EXTERNAL_UNTRUSTED`; fixed-host HTTPS egress and secret-free Event Journal-compatible request audit are implemented.
- Calendar event creation and notification send use Core-owned Phase 9 profiles. Calendar requires provider readback for verified success; ntfy records provider acceptance only and never claims human delivery/read.
- Live synthetic Open-Meteo, TheMealDB, and ntfy traffic passed. Brave and Google Calendar are independent `EXTERNAL_RESOURCE_GATE` states without runtime credentials; no credentialed live claim is made.
- Phase 11 gate-closure implementation checkpoint `dde3e2bc42fc5004ddf06690ddbd9dc9941999f8`; hosted CI `33445636772` passed on the exact SHA. It adds refreshable `google-auth` Calendar credentials using the owned-calendar scope `https://www.googleapis.com/auth/calendar.events.owned`, same-catalogue AgentRuntime evidence, hostile external-result containment, and durable-task fresh external follow-up evidence.
- Phase 11 evidence amendment checkpoint `f069e5c0d1d42d0a74eba3267f8393f325509429`; hosted CI `33446725375` passed on the exact SHA. It strengthens the durable follow-up claim with the actual PostgreSQL Phase 10 harness: external value `17` before task creation and fresh value `23` after restart/scheduled cognition, while the future physical action remains Phase 9-coordinated.
- Phase 11 is `COMPLETE — PENDING ARCHITECT ACCEPTANCE`. The prior governed closure `439c12a5872b7844f77ad36fa57672f634d0ee52` with CI `33445878287` remains historical. Final governed evidence checkpoint: `abc9bece8b4827828ca759993191a1f20338d442`, CI `33446946952`; the final Authority synchronization commit follows this record. Phase 12 remains unauthorized.

## Phase 11 free/local realignment state (historical; superseded by 013R3)

- Architect directive `ANIMA-HA-P11-FREE-LOCAL-REALIGNMENT-013R` supersedes the blocked Brave/Google gate-closure path. Brave and Google Calendar are `SUPERSEDED / DEFERRED` for this prototype; Phase 12 remains unauthorized.
- Free/local discovery is implemented with a pinned private SearXNG service (JSON API, loopback-only host exposure, fixed engines `duckduckgo` and `wikipedia`, no public instance, no image proxy, no Valkey) and OpenStreetMap Overpass for category-mapped POI queries. Model input cannot choose hosts, engines, raw Overpass QL, or arbitrary URLs.
- First-party calendar is implemented in `src/anima_ha/calendar.py` with migration `0012_local_calendar.sql`, household isolation, trusted invocation provenance/idempotency, CRUD, optimistic versioning, and PostgreSQL persistence. Calendar mutations are Core-approved `POLICY_GATED_INTERNAL`; later physical/provider actions remain Phase 9-coordinated.
- Fresh local-filesystem evidence: 134 tests, Ruff, strict mypy, package sdist/wheel, OPA 4/4, migration initial/repeat, SearXNG healthy/no-Valkey live JSON web/product search, Overpass synthetic POI search, and local calendar AgentRuntime integration passed. SFTP Docker bind mounts remain a known limitation; reproduction used `/tmp`.
- Historical provider gates were `EXTERNAL_RESOURCE_GATE_SEARXNG_SEARCH=CONFIGURED` and `EXTERNAL_RESOURCE_GATE_OVERPASS=CONFIGURED`; no Brave or Google credential gate remained active for that superseded path. Native ARM64/Pi, production scale, physical-home, and high-risk external-write behavior remain unclaimed.
- Implementation checkpoint: `558c689cac96f3bddbd636b4d1b9e20d055b221d`; hosted CI `33458814906` passed on that exact SHA. The governed evidence-closure checkpoint and CI follow after this Authority update.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.
