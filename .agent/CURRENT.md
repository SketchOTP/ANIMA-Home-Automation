# Current Project State

Last updated: 2026-09-05

## Current stage

PHASE 14 RESILIENCE, REPLAY, BACKUP AND RECOVERY - 016A

## Current objective

Prove that the accepted ANIMA household-authority platform preserves authority,
verification, privacy, deterministic recovery, and exactly-once side-effect
boundaries across failure, duplication, concurrency, outage, replay, and
backup/restore. Phases 0-13 are Architect accepted. Phase 15 remains
unauthorized.

## Active directive

ANIMA-HA-P14-RESILIENCE-REPLAY-BACKUP-RECOVERY-016A - build one canonical
machine-readable destructive-scenario ledger, exercise existing lifecycle,
action, task, calendar, HA, plugin, OPA, SENTRY, replay, restart, and restore
boundaries, and report unrun infrastructure honestly. No new broker, database,
workflow engine, provider, or household feature is authorized.

## Current authority result

Phase 13 is Architect accepted at ANIMA
f0456d24fa09ed6873e882c89a9dce759f73a619 with exact-head CI 33938497635.
The accepted isolated SENTRY launcher compatibility patch is
00aa9ac3a35b7b012581160b961e01a9480bbbdf with CI 33939908542. Phase 14 is
active and not self-accepted. Phase 15 is unauthorized and unimplemented.

## Phase 14 initial execution - 2026-09-05

- Starting governed head: f0456d24fa09ed6873e882c89a9dce759f73a619; origin/main
  matched and the worktree was clean before the Phase 14 packet was created.
- Existing full pytest baseline passed at the starting checkpoint: 214 tests.
- Phase 13 packet was reconciled from active to completed. Historical R4
  negative evidence and resource limits were preserved.
- The canonical Phase 14 scenario/replay model and explicit test-only fault
  injector are now being added. Deterministic focused validation is pending.
- The protected SENTRY V0.4 worktree remains outside this repository and is not
  modified by Phase 14.

## Phase 14 destructive qualification update - 2026-09-05

- Real disposable PostgreSQL/OPA environment: PostgreSQL 16/pgvector and OPA
  were migrated and exercised on isolated ports 55433/18182. No credentials
  or private household data were published.
- Real PostgreSQL lifecycle passed: pre-provider crash reclaim, provider-start
  ambiguity with no blind replay, durable result without model rerun, concurrent
  claim winner, and stale-fence rejection across provider writes.
- Real Phase 1 PostgreSQL replay/projection passed; real Phase 4 OPA passed;
  real Phase 9 isolated Home Assistant action/idempotency/concurrency passed;
  real Phase 10 durable-task scheduling/lease recovery/fresh context passed.
- Real HA harness passed against Home Assistant 2026.8.2 after a bounded
  current-registry compatibility correction. It covered discovery, canonical
  mapping, state truth, OPA deny/confirmation/strong-auth gates, verified
  action, deliberate verification failure, reconnect/reconcile, auth failure,
  plugin restore, PostgreSQL restart, and secret non-persistence.
- Real 80-task/80-calendar history passed, including task lifecycle, calendar
  optimistic versioning, stale conflict, and versioned cancellation.
- Actual pg_dump/pg_restore passed into a clean pinned PostgreSQL container.
  Dump SHA-256 is
  f044742805867bad15df32cb8c88cb273597b99bc200677d87d6ec3844a6a10c;
  the bundle scan found no raw credential markers. Restored physical Truth
  remains UNKNOWN_UNTIL_REOBSERVED and executed effects are not replayed.
- These results are destructive/isolated evidence, not Phase 14 acceptance.
  Provider/action crash-window continuation, full process restart matrix,
  SENTRY outage/restart, plugin isolation, external-content attack matrix,
  real-store replay regression, and ARM64 execution remain open.

## Evidence boundary

Only executed scenarios may be marked PASSED. Missing PostgreSQL, HA, SENTRY,
or ARM64 infrastructure remains NOT RUN, NOT APPLICABLE, BLOCKED, or an
explicit external gate. No secrets, restricted provider content, or household
private data may enter committed evidence. Phase 15 behavior is absent.

## Preserved historical state

## Phase 13 R4 runtime compatibility certification — 2026-09-05

- Starting governed head: `1d82cb992482b6460d65eb88ac53f0ef013bfda9`; prior
  exact-head CI `33933528405` passed.
- Implementation/final published head: `20e3e0763328ed327c7d80d73264344d6054339f`;
  exact-head hosted CI `33938016240` passed and artifact `9960893002` was
  published.
- The client-only `anima-household` bundle now adapts to MCP 2.x `MCPServer`
  and MCP 1.x `FastMCP`, declares the minimal ANIMA boundary skill, and has an
  actual stdio MCP certification harness in hosted CI. Pinned evidence is
  Python 3.12.3 / MCP 2.1.1, with 10 listed tools and successful direct and
  queued read/mutation/result paths.
- Actual Codex CLI shadow loading and an `anima_health` call succeeded with a
  disposable profile and no ANIMA credentials. The protected SENTRY V0.4 tree
  remains unchanged, but its existing `sentry-office` launcher fails before
  initialization because it resolves `SENTRY/integrations/tools` instead of
  `SENTRY/tools`. Fixing that requires protected SENTRY-side authority.
- Result: `NEEDS_ARCHITECT_DECISION — PHASE13_RUNTIME_COMPATIBILITY_BLOCKED`.
  Phase 14/15 remain unauthorized; no ANIMA voice, Phase 14, or Phase 15
  behavior was implemented.

## Phase 13 R3 integration qualification — 2026-09-04

- Direct SENTRY request identity is deterministic over provider, household,
  server-registered client, and SENTRY request ID. Direct identity observations
  are persisted as actual ANIMA evidence records before request creation and
  the durable request binds the resulting evidence ID.
- Normalized non-snapshot HA events now flow through typed SenseGuard policy
  matching, deterministic guaranteed alert events, and the existing
  Attention-to-SENTRY bridge with duplicate alert suppression. Unrelated event
  types are rejected.
- Focused/full tests, Ruff, strict mypy, compileall, and diff-check pass.
  Exact-head hosted CI `33933037033` also passes on implementation head
  `da9b6de2aceb34e36a51c400dcf8b090e010115d`; artifact `9959297861` was
  published. Live/shadow SENTRY, physical SenseGuard, and voice evidence
  remain explicit unclaimed gates; Phase 13 is not accepted.

## Phase 13 HA device-control slice — 2026-09-04

- The ANIMA UI now includes a Devices view for the supported Home Assistant
  onboarding flow. It can open a bounded 1–120 second ZHA pairing window,
  refresh the HA registry, and commission a present discovered device into an
  existing ANIMA household place.
- `refresh_inventory` is read-only. `permit_zigbee_join` and
  `commission_device` are Core-owned policy-gated internal capabilities of the
  built-in HA plugin. The browser cannot choose an HA host, service, entity
  target, credential, graph relationship, or arbitrary configuration payload.
- Commissioning derives deterministic canonical resource/capability IDs,
  provider references, Truth bindings, and power controls from the refreshed
  registry. Existing power control remains the semantic `desired_on` contract
  and continues through Phase 5, Phase 4, Phase 9, and observed verification.
- Focused and full Python tests plus the frontend TypeScript check and Vite
  production build pass for this slice. Physical-device pairing and real-home
  behavior remain unclaimed until the existing isolated HA harness and operator
  commissioning are run; this does not authorize Phase 14, Phase 15, or raw HA
  administration.

## H5V-R1 result — historical completed Phase 12 packet — 2026-09-03

- The published H5V-R1 implementation adds continuation lifecycle migration
  `0017_continuation_lifecycle` plus compatibility migration `0018`, durable
  context/transcript loading, fenced continuation recovery, original
  tool-catalogue/runtime binding, cumulative active-runtime accounting, and a
  same-episode continuation in `AgentRuntime.resume_confirmation()`.
- Approval and rejection are both represented as normalized continuation tool
  results. The original action is not replayed; approval dispatches once and
  rejection dispatches zero times. The resumed model receives the action status,
  approval decision, and bounded evidence.
- Focused tests and the real-OPA PostgreSQL verifier pass locally. The verifier
  seeds a real journal → attention → trigger → context chain and proves two
  model turns in one PostgreSQL episode, durable continuation rows, `SUCCEEDED`
  approval, `POLICY_DENIED` rejection, and provider execution context forwarding.
- H5V implementation checkpoint `8bcff850a56b0bd8b3a70cc4d837e1268e12716f`
  was followed by the CI port-isolation checkpoint
  `58636eaec87a9ad4ddd0958b916a4d74b2d9fe74`; hosted CI `33818551425` passed
  on the exact latter SHA and published artifact `9917602062` with digest
  `sha256:257886d0b85f485bc2b103cdfc55b159618a00bb6c72f46f14f8b0352237464b`.
- At the contemporaneous H5V-R1 handoff, real PostgreSQL/OPA approve/reject continuation,
  two dedicated browser approval/rejection journeys, full Python/static/
  frontend/package validation, and the existing Core evidence passed. Browser
  denial/strong-auth, provider recovery, restricted lifecycle, same-browser
  process restart/SSE, complete crash/concurrency ledger, dirty-data and
  browser-visible isolated-HA journeys remained unproven. A subsequent
  Architect decision accepted Phase 12 while preserving those limitations as
  historical carry-forward evidence.

## H5U current result — historical 2026-09-03

- Durable PostgreSQL pending-approval persistence and UI approval/rejection
  routing are implemented locally; the public payload omits executable
  arguments while the bounded server envelope permits exact reconstruction.
- AgentRuntime confirmation remains the same episode and does not replay the
  original tool. Wrong principal, expiry, rejection, and replay fail closed;
  the real PostgreSQL verifier observes exactly one provider call.
- Fresh local validation and supporting H4/H5/isolated-HA/restricted-content
  targets pass. The historical H5T task `FAILED / ValueError` is preserved;
  current H5 Core task mutation passes after the bounded correction.
- Implementation checkpoint `dbb4720882b25ad1d840c2c270191227f0c4ea1d` is
  published and hosted CI `33746353829` passed on that exact SHA. The governed
  closure checkpoint is the subsequent governance commit; Phase 12 is not
  accepted.

## Prior closure history

H5T same-browser restart/SSE evidence remains `PARTIAL / CONTINUE`; its live
SSE and durable-task duplicate-accounting limits remain historical negative
evidence. H5S/H5R/H5/H4 records remain preserved below and in the append-only
ledgers.

The repository's former H5 pointer below is retained as historical context only:

`ANIMA-HA-P12-BROWSER-ACCEPTANCE-EVIDENCE-CLOSURE-014H5` — close only the remaining browser behavior/evidence gaps without changing accepted Phase 0–11 architecture. Starting checkpoint: `33440106ea629eda0386a062924e1f84c4b32c14` with hosted CI `33686702038` passed. Implementation/evidence head is `800d8cf4a183ce0e7548545182ed09f0687ad98f`; hosted CI `33696481738` passed on that exact SHA. Latest governance/CI reliability head is `828230a73d3c9097bab448192747a3f6786c0d4f`; hosted CI `33697593173` passed on that exact SHA. Phase 12 remains CONTINUE and pending Architect acceptance; Phase 13 is unauthorized.

## Current verified state

- The H4 implementation delta is limited to Phase 12: Home controls send the qualified `desired_on` field, UI action results project the Phase 9 terminal record, mutation outcomes are surfaced after the corresponding refetch, calendar edits use optimistic versions, and all persisted presentation settings drive the rendered UI.
- The real H4 Core target composes PostgreSQL graph/Truth/journal/Attention/Context Broker/AgentRuntime/PluginManager/OPA/task/calendar/action dependencies with only a scripted model adapter. It proves a real journal/context/episode trace, task lifecycle, calendar edit/stale-version/cancel, settings persistence across restart, and `fallback_enabled=false`.
- The isolated HA target reuses the Phase 6 harness and proves UI HTTP → CoreUICommandGateway → Phase 5 → OPA → Phase 9 → Home Assistant → observed verification: `SUCCEEDED` for the commissioned virtual control and `VERIFICATION_FAILED` for a deliberate mismatch. Connector acknowledgement is retained as evidence and cannot override the terminal record.
- Local/frontend evidence passed the current deterministic Core conversation, task lifecycle, calendar versioning/cancel, settings, display geometry/order, responsive storage inventory, same-origin, and keyboard smoke. Hosted CI passed 11 tests with 10 responsive/functional skips. Browser-specific denial, degraded-provider recovery, restricted-content reload/storage, original-session process restart/SSE, and browser-visible isolated-HA outcome journeys remain evidence limitations rather than completed claims.
- Normal configured `create_app()` composes PostgreSQL graph/Truth/journal/Attention/Context Broker/AgentRuntime/PluginManager/OPA/task/calendar/action dependencies. Only the model adapter is scripted in the deterministic target; `UnavailableCommandGateway` and the echo fallback are not selected in configured runtime.
- `scripts/verify_phase12_final_ux.py` passed with `fallback_enabled=false`, a real Journal → Attention → ContextPacket → AgentRuntime trace, policy-gated task success, persisted settings, and explicit `EXTERNAL_RESOURCE_GATE_HA_COMMISSIONING` status.
- Fresh validation passed: `uv sync --locked --dev`, `scripts/validate.sh` (168 Python tests, Ruff, strict mypy, OPA 7/7), package sdist/wheel, frontend unit tests, TypeScript/Vite build, Playwright (11 passed/10 skipped across desktop/tablet/phone), migration repeat, H4/H5 Core targets, isolated-HA target, restricted-content target, `git diff --check`, public-safety review, and hosted Docker UI health.
- Phase 11 active providers remain Open-Meteo, private SearXNG, OSM Overpass, TheMealDB, UPCitemdb, local PostgreSQL calendar, and ntfy. Walmart and Best Buy remain deferred historical candidates; no provider gate is silently substituted.

### H5 evidence and publication state (historical)

- H5 implementation/evidence sequence: `2bc175852afc4003176f9be910f70618d8a1b827`, `aa0f24e12577dc536fb6cecf331aae6544ea3c94`, `e6ab72618ee5fdf2aebaaadaf83a9ebbb4adb485`, `5882d9e0047b8d07d7f5d45b5081a59d3340fbf3`, and `800d8cf4a183ce0e7548545182ed09f0687ad98f`. Hosted CI `33696481738` passed on the exact current head and published artifact `phase12-h5-evidence-800d8cf4a183ce0e7548545182ed09f0687ad98f`, artifact ID `9872060277`, ZIP digest `33e32d1966462416f27b1fec109cfac7097de2d15dac0f5e8086a580ce31a383`.
- H5 deterministic Core evidence proves real `create_app()` PostgreSQL/OPA/Graph/Truth/Journal/Attention/Context/AgentRuntime composition, original session reuse across reconstruction, post-restart task mutation, external audit digest redaction, deterministic provider degraded/recovery states, restricted live response with zero PostgreSQL sentinel occurrences, and the reused isolated-HA API path. Display-mode CSS now produces measured wall/tablet/phone/desktop geometry differences.
- H5 was not complete: hosted browser coverage remained the pre-existing functional/smoke matrix and did not independently run browser-visible denial, provider recovery, restricted-content reload/storage, process restart/SSE with the same browser session, or browser-visible isolated-HA outcomes. These are preserved `NOT RUN`/`UNSUPPORTED BY CURRENT TARGET` limits; H5U supersedes this work unit for the current continuation.
- The governance/CI reliability follow-up is `828230a73d3c9097bab448192747a3f6786c0d4f`; hosted CI `33697593173` passed on that exact head after the workflow was bounded to wait for healthy PostgreSQL/OPA containers before migration. This is publication/CI evidence only and does not close the unrun browser journeys.

### H4 evidence and publication state

- Implementation commits: `02a958590f8c1c1dab38b1143af12c9fea6033cc` (H4 contract implementation), `a4b0c40b084f9dfbd127b43bd80e84c45977ab0d` (strict-mypy test-double correction), `94f665fd6a4bbc2246124bb5df06d81bdb2fb987` (CI PostgreSQL/OPA bootstrap), `22c1af9a01d7db02abfdc4ef788222f9783c8c53` (post-refetch outcome publication), and `9e12f6e295b52ec382c1952a21a1a95287100740` (overlapping refresh-generation protection). Hosted CI `33686351783` passed on the exact implementation head.
- Local validation: `anima-validate` passed 168 tests with Ruff and strict mypy; TypeScript, frontend unit tests, Vite build, package build, OPA, Phase 6 isolated HA, Phase 11 restricted-content, and H4 Core targets passed. Full hosted CI for the current head remains the publication gate.
- Status is `IMPLEMENTED — PENDING ARCHITECT ACCEPTANCE`; this record does not promote Phase 12 to accepted and does not authorize Phase 13.

### Current product-provider replan

- Architect disposition: `REPLAN / CONTINUE`; Best Buy is `DEFER — DEVELOPER_ONBOARDING_UNAVAILABLE`; Walmart is `DEFER — ENTITLEMENT_CLARIFICATION`.
- UPCitemdb is adopted/wrapped behind `shopping.search_products` at fixed `https://api.upcitemdb.com/prod/trial/search`, with no signup, no API key, no paid tier, and Core-owned `EPHEMERAL_RESTRICTED` content persistence.
- Live public synthetic evidence: `wireless headphones` returned 5 distinct EAN-identified products, 13 bounded offers, and `X-RateLimit-Remaining=93`; `air fryer` returned 5 distinct EAN-identified products, 19 bounded offers, and `X-RateLimit-Remaining=92`. Historical prices and old offer timestamps remain explicitly non-current external observations.
- Conservative limiter: at most 20 search requests per in-process rolling day and at least 15 seconds between searches; the live harness uses a 16-second margin and records provider rate-limit headers. A 429 honors `Retry-After` without retrying.
- Terms posture: official terms grant a limited, terminable service-use license, disclaim accuracy/availability, and require the customer not to infringe third-party rights; API documentation states affiliate-bound Amazon/eBay sales information is not redistributed. Product results remain restricted/untrusted and are not persisted as a catalog.
- Provider resource state: `EXTERNAL_RESOURCE_GATE_UPCITEMDB_PRODUCT_SEARCH=AVAILABLE`; no Best Buy/Walmart fallback is active. This is historical Phase 11 evidence and does not block the authorized Phase 12 interface work.

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

- Historical H5V implementation was published at
  `d3c8beacef23e20e69a6cafd31eae1b7e6a9edb2` with exact-head hosted CI
  `33777520224` passed. Local real-OPA/PostgreSQL continuation evidence also
  passes. Dedicated browser confirmation/rejection and same-browser
  restart/SSE continuation evidence remain open; this governance checkpoint
  records that bounded implementation state without self-accepting Phase 12;
  later Architect acceptance of Phase 12 is recorded at the top of this file.
- Real Home Assistant OAuth commissioning, physical-home behavior, production TLS, native ARM64/Pi execution, and live Luna credentials remain unclaimed. The local target proves real PostgreSQL/OPA/Core composition with only a scripted model adapter and reports HA as an explicit commissioning gate.
- At the time of this historical checkpoint Phase 12 was `CONTINUE — H5V
  IMPLEMENTATION/EVIDENCE IN PROGRESS`; later Architect acceptance is current.
  Phase 13 voice, checkout, compensation, and other successor behavior remain
  unauthorized.

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

Review `ANIMA-HA-P13-SENTRY-READY-INTELLIGENCE-PLATFORM-015B` with its R1
amendment after the exact-head hosted CI is verified. Evidence must cover the
credential-isolated Core service, request fencing/catalogue binding, direct
SENTRY interaction binding, device/SenseGuard integration, and real SENTRY
host qualification. Phase 14 and Phase 15 remain unauthorized.

## Phase 12 publication state — historical 014H checkpoint

- Starting accepted checkpoint: `918365ce7c6145780112a808411d750fb0e289eb`; Phase 11 CI `33562645002` passed on that exact SHA.
- Implementation checkpoint: `8a8f798d5d2319e690572d69a323e10459924bce`; hosted CI `33572829176` passed on that exact SHA. The prior implementation-only CI `33572285917` failed on a strict-mypy test typing issue; the bounded fix and rerun passed.
- Implemented: FastAPI/Uvicorn semantic API, HA OAuth bootstrap, exact user mapping, hashed sessions/CSRF, migration `0013_ui_sessions.sql`, responsive React/Vite UI, bounded SSE invalidations, Docker/Compose, deterministic harness, and Playwright browser matrix.
- Current integration evidence: `src/anima_ha/ui_runtime.py` composes the existing PostgreSQL journal, Attention, Context Broker, AgentRuntime, PluginManager/Tool Gateway, OPA policy service, durable tasks, local calendar, and Phase 9 coordinator. The UI service uses this composition whenever `ANIMA_DATABASE_URL` is configured; without required Core configuration it remains explicitly unavailable, and the test echo is available only under the explicit test flag.
- Evidence limits: real Home Assistant OAuth/commissioning, native ARM64/Pi, production TLS, and live household data remain unclaimed. The deterministic integrated pipeline uses the real AgentRuntime with a scripted model adapter.
- Phase 12 status: `COMPLETE — PENDING ARCHITECT ACCEPTANCE` after the governed closure checkpoint and exact-head CI are verified. Phase 13 remains unauthorized.

## Phase 12 commissioned-runtime truth closure — current 014H2

- Starting governed checkpoint: `8650da07f132d49987abe32fe86e94a44ff79844`; hosted CI `33581039085` passed on that exact SHA.
- Implemented locally: `PostgresCommissionedIdentityResolver` uses commissioned HA `user` provider references and canonical `PERSON`/`MEMBER_OF` graph edges; `build_postgres_core()` composes the qualified Phase 11 portfolio and optional HA adapter; `PostgresHouseholdReadModel` uses graph/Truth/plugin state and never delegates to `DemoHouseholdReadModel`.
- Target evidence: `scripts/verify_phase12_commissioned_runtime.py` passed against local PostgreSQL and live OPA, including exact identity mapping, OPA-authorized task/calendar mutation, active-provider registry, and Journal → Attention → ContextPacket → AgentRuntime trace.
- Implementation checkpoint: `5d52c45c72520611de56361af9010419f2869c6c`; hosted CI `33654654675` passed on that exact SHA.
- Governed closure checkpoint: `bc7849dba3b65b837aacf2b16e8b7653fae97d08`; hosted CI `33655337251` passed on that exact SHA. Current status is `COMPLETE — PENDING ARCHITECT ACCEPTANCE`; HA commissioning, physical-home behavior, live Luna, native ARM64/Pi, production TLS, and real household data remain unclaimed. Phase 13 remains unauthorized.

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
- Historical Phase 11 entry: it was then `COMPLETE — PENDING ARCHITECT ACCEPTANCE`. It is superseded by the accepted Phase 11 checkpoint recorded at the top of this file; Phase 12 is now authorized.

## Phase 11 free/local realignment state (historical; superseded by 013R3)

- Historical Phase 11 realignment entry: Brave and Google Calendar remain `SUPERSEDED / DEFERRED` for this prototype. It is superseded by the accepted Phase 11 checkpoint and does not change current Phase 12 authorization.
- Free/local discovery is implemented with a pinned private SearXNG service (JSON API, loopback-only host exposure, fixed engines `duckduckgo` and `wikipedia`, no public instance, no image proxy, no Valkey) and OpenStreetMap Overpass for category-mapped POI queries. Model input cannot choose hosts, engines, raw Overpass QL, or arbitrary URLs.
- First-party calendar is implemented in `src/anima_ha/calendar.py` with migration `0012_local_calendar.sql`, household isolation, trusted invocation provenance/idempotency, CRUD, optimistic versioning, and PostgreSQL persistence. Calendar mutations are Core-approved `POLICY_GATED_INTERNAL`; later physical/provider actions remain Phase 9-coordinated.
- Fresh local-filesystem evidence: 134 tests, Ruff, strict mypy, package sdist/wheel, OPA 4/4, migration initial/repeat, SearXNG healthy/no-Valkey live JSON web/product search, Overpass synthetic POI search, and local calendar AgentRuntime integration passed. SFTP Docker bind mounts remain a known limitation; reproduction used `/tmp`.
- Historical provider gates were `EXTERNAL_RESOURCE_GATE_SEARXNG_SEARCH=CONFIGURED` and `EXTERNAL_RESOURCE_GATE_OVERPASS=CONFIGURED`; no Brave or Google credential gate remained active for that superseded path. Native ARM64/Pi, production scale, physical-home, and high-risk external-write behavior remain unclaimed.
- Historical Phase 11 implementation checkpoint `558c689cac96f3bddbd636b4d1b9e20d055b221d`; hosted CI `33458814906` passed on that exact SHA.

This file is a mutable snapshot. Do not use it to erase historical outcomes or decisions.


## Phase 14 R2 current state — 2026-09-05

Phase 14 remains `CONTINUE — FINAL DESTRUCTIVE QUALIFICATION PARTIALLY EXECUTED`. Starting governed checkpoint was `979560442bf412c440f0c3f1399b830dd3d6acf0`; the current implementation checkpoint is `616964f395f9808ac3453b3eddc8cb8b84372767`. The real-store R2 ledger passes 13 scenarios, including stable cursor pagination over 250 tasks and 250 calendar records and real-store replay/diff checks. R1's accepted real PostgreSQL/OPA/isolated-HA/backup evidence is retained. Approval/action continuation, outage/restart, plugin, external-content, clean-store replay, and ARM64 runtime evidence remain open. Phase 15 is unauthorized and unimplemented.

## Phase 14 R2 latest increment — 2026-09-05

The current governed continuation head is `25c5d4f1f239a265afef335aa8d1a698e5cea835`.
It adds `scripts/verify_phase14_events_plugins_r2.py` and runs it in hosted CI.
Real PostgreSQL Journal/Truth/Attention evidence now covers duplicate event and
source-ID collapse, out-of-order source-sequence resolution, append-before-
projection recovery with one observation, and duplicate guaranteed
SenseGuard-style Attention with one trigger. Real PluginManager/PostgreSQL
evidence covers independent failure of Home Assistant, external-read, and
notification-side-effect plugin classes while an unrelated plugin remains
healthy, with durable failure audits. Phase 14 remains `CONTINUE`; this does
not close the remaining HA/SENTRY outage, full in-flight process, clean-store
replay, or ARM64 runtime matrices. Phase 15 remains unauthorized.
The clean-store replay increment is published at `25c5d4f1f239a265afef335aa8d1a698e5cea835` pending exact-head CI. Two fresh pinned PostgreSQL environments ran the real 13-scenario R2 verifier with matching durable behavior fingerprints, and the replay comparator detected a deliberate expected divergence. This closes only that replay subset; Phase 14 remains `CONTINUE` and Phase 15 remains unauthorized.

The next current increment adds bounded SENTRY bridge restart evidence: the
actual bridge process creates one durable request from a unique guaranteed
event, and a restarted bridge does not create a duplicate. No model or
embedded fallback was used. Phase 14 remains `CONTINUE`; full SENTRY provider,
HA outage, in-flight process, and ARM64 runtime matrices remain open.

The isolated Home Assistant outage target now passes locally and is wired into
CI: a disconnected latest-state refresh yields `UNKNOWN_RESULT` with zero
dispatches, reconnect restores `ONLINE`, and replay does not redispatch. This
closes the exercised HA no-redispatch boundary only; Phase 14 remains
`CONTINUE` for full in-flight process and SENTRY-provider outage coverage.

The latest local Phase 14 increment adds a real PostgreSQL SENTRY provider-crash
target. The actual `SentryBridgeWorker` and `CoreSentryBoundary` persist
`PROVIDER_RUNNING` before the deterministic provider callback; a child-process
loss then recovers to `UNKNOWN_RESULT` with no reclaim and no second callback.
The isolated-HA outage and SENTRY provider-crash targets are queued for the next
exact-head hosted run. Phase 14 remains `CONTINUE`; full process/restart,
approval-continuation, and ARM64 runtime matrices remain open. Phase 15 remains
unauthorized and unimplemented.

The current uncommitted increment adds the actual Compose process restart target
for PostgreSQL, OPA, SearXNG, and ANIMA UI, with service health and Journal
continuity checks. It remains explicitly a service-continuity slice and does
not claim the full in-flight process matrix. Phase 14 remains CONTINUE and
Phase 15 remains unauthorized.

## Phase 14 R2 latest governed checkpoint — 2026-09-05

The current exact governed head is `631d6de89ca6591ade1afe273aa1fe2c98a4d352`;
hosted CI `33983789113` passed on that exact SHA and published artifact
`9974663615`. The checkpoint adds real OPA outage fail-closed evidence
(`POLICY_DENIED`, durable `POLICY_UNAVAILABLE`, zero provider dispatch) and
hosted execution of the real isolated-HA Phase 9 opposing-request race. It
retains the R2 real-store ledger, 250-task/250-calendar stable pagination,
clean-store replay/diff detection, event/Truth/Attention replay, plugin and
external-content isolation, HA outage/no-redispatch, SENTRY bridge/provider
crash, service continuity, and ARM64 image-build evidence.

Phase 14 remains `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`. The active
Phase 14 packet remains under `.agent/tasks/active/`; Phase 15 is unauthorized
and unimplemented. Remaining software-controllable work is the full approval/
continuation crash matrix, SENTRY outage/local-platform continuity, complete
in-flight process restart coverage, broader external attack/restricted-content
coverage, and ARM64 replay/runtime beyond image build. R1 backup/restore is
retained as real accepted carry-forward evidence and is not falsely relabeled
as a new R2 run.

Hosted CI `33980726478` on `59a72fe...` reached the process matrix but exposed
a workflow-ordering defect: the preceding UI health-check cleanup stopped the
UI container before inspection. The workflow now keeps UI alive through the
matrix and stops it in an always-run cleanup step; this failed attempt remains
retained as harness evidence. Phase 14 remains CONTINUE.

## Latest exact hosted checkpoint

The current governed implementation head is
`194079699b9c55e5e4311fd5a0454729ecd4cac3`, matching `origin/main`. Exact-head
CI `33984850396` passed. Artifact `9974957442` is the current reviewable
artifact. It includes the real OPA outage fail-closed target, isolated-HA
Phase 9 concurrency, real-store replay and divergence detection, event/Truth/
Attention and plugin isolation, HA outage/no-redispatch, SENTRY bridge/provider
crash evidence, service continuity, 250-record pagination, and the corrected
`linux/arm64` runtime import smoke. The prior `631d6de...` checkpoint remains
historical evidence, not the current head.

Phase 14 remains `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`. The active
packet remains under `.agent/tasks/active/`; Phase 15 is unauthorized and
unimplemented. Native Pi 5 hardware remains an external gate. Remaining
software closure is the full approval/continuation crash matrix, SENTRY outage
with local-platform continuity, complete in-flight process restart coverage,
broader external-content/restricted-content attack coverage, and ARM64 replay
runtime evidence beyond the import smoke. R1 backup/restore remains accepted
carry-forward evidence.

## Phase 14 R2 exact-head checkpoint — 2026-09-05

The current exact governed head is `0283b648620e18ae4b771b9099673ec4d81eac88`,
matching `origin/main`. Hosted CI `33991073890` passed on that exact SHA in
9m36s. Artifact `9976506229` is reviewable.

This checkpoint makes the real SENTRY provider-crash verifier robust on an
accumulated qualification database: it runs the genuine queue-level expired
provider reclaim, proves the tested request becomes `UNKNOWN_RESULT`, and
does not misattribute unrelated pending SENTRY work to the scenario. Local
real-store SENTRY outage, bridge restart, Journal/Truth replay, and three-class
plugin isolation checks also passed.

Phase 14 remains `CONTINUE — FINAL DESTRUCTIVE CLOSURE REQUIRED`. The active
packet remains under `.agent/tasks/active/`; Phase 15 is unauthorized and
unimplemented. Remaining software-controllable closure is the full approval/
continuation crash matrix, broader action/manual-reality proof, complete
SENTRY/HA/plugin/process in-flight restart coverage, wider external-content
coverage, and ARM64 replay/runtime evidence beyond the current hosted smoke.
