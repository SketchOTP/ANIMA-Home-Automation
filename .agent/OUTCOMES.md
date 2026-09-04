# Outcome Ledger

---

## ANIMA-HA-P9-EXECUTION-HARDENING-011H — Phase 9 execution hardening

- Date: 2026-08-30
- Verdict: COMPLETE / PENDING ARCHITECT ACCEPTANCE
- Disposition: `CONTINUE`; Phase 10 unauthorized.
- Scope: Trusted safety profiles and mandatory preconditions, provider execution context with optional native idempotency, observation-first verification, ambiguous-dispatch reconciliation, per-effect evidence, and real AgentRuntime regression.
- Evidence: 63 focused tests, 94 full tests, strict mypy, Ruff, OPA 4/4, package build, migration repeat, Phase 1–8 regressions, Phase 6 isolated HA, Phase 7 restart/replay, Phase 8 persistence, and Phase 9 isolated HA all passed in a local-filesystem reproduction.
- Limitation: GVFS/SFTP mount was unavailable for reliable Python execution; no native ARM64/Pi, physical-home, high-risk, or production evidence is claimed.

---

## ANIMA-HA-P11-EXTERNAL-CAPABILITIES-013 — Bounded external capability implementation

- Date: 2026-08-31
- Verdict: COMPLETE IMPLEMENTATION / PENDING ARCHITECT ACCEPTANCE
- Disposition: Phase 11 authorized after Phase 10 acceptance; Phase 12 remains unauthorized.
- Starting accepted checkpoint: `2c8f88f62c27a728b2bf0861dabaf7a3a3d03e56`; hosted CI `33429217008` had passed.
- Implementation checkpoint: `17252304a4f0642bb654ec612cfcb55a01411804`; hosted CI `33442439042` passed on that exact SHA.

### Work performed

- Added ANIMA-owned bounded adapters for Open-Meteo weather, Brave web/place/product discovery, TheMealDB recipes, Google Calendar REST, and ntfy notifications.
- Added `ExternalResult`, explicit `EXTERNAL_UNTRUSTED` trust, source/attribution fields, fixed-host HTTPS egress, no redirects, method/path/host/IP/response-size bounds, and secret-free `ExternalRequestAudit` records with an Event Journal sink.
- Added independently evaluated provider-resource gates. Weather, recipes, and synthetic ntfy do not require a credential; Brave requires `BRAVE_SEARCH_API_KEY`; Google Calendar requires the runtime-only `GOOGLE_CALENDAR_ACCESS_TOKEN`; a configured ntfy topic is required for normal operation.
- Added Core-owned Phase 9 profiles for Calendar event creation and notification send. Calendar uses deterministic provider identity plus GET precheck/POST/GET readback; notification success records provider acceptance only. No connector effect claim can establish consequential success without the profile verifier.
- Added exact bounded tool schemas and retained provider IDs/URLs as external references only. No retailer cart/checkout API was adopted.

### Fresh validation and evidence

- `uv sync --locked --dev`: PASSED; locked environment resolved 67 packages.
- Full pytest: `130 passed`.
- Focused external/action suite: `25 passed`.
- Changed-file Ruff format/check: PASSED; strict mypy: `Success: no issues found in 40 source files`.
- Package sdist/wheel: PASSED; `git diff --check`: PASSED.
- Pinned OPA Docker tests: `PASS: 4/4`. The `opa` executable was absent locally; the repository-documented pinned container path passed.
- Fresh Phase 1–5, 7–10 PostgreSQL/integration harnesses: PASSED. Phase 6 isolated real Home Assistant harness: PASSED. Phase 7/8 restart-aware runs passed after supplying the repository-required local `ANIMA_DB_PASSWORD` environment variable.
- Live synthetic provider harness: Open-Meteo `PASS`, TheMealDB `PASS`, ntfy no-cache/Firebase-disabled `PASS`; Brave and Google Calendar correctly reported `EXTERNAL_RESOURCE_GATE`; no credentialed Brave/Google live claim is made.
- Public safety scan: PASSED; no private-key material, token values, runtime database/log state, household secrets, or credentials were added. Build output remains ignored.

### Evidence limits

Evidence is x86-64 Python 3.12 local/CI execution and bounded synthetic/public-provider traffic. It is not native ARM64/Pi qualification, physical-home evidence, production commercial-provider approval, production-scale capacity evidence, Google OAuth commissioning evidence, Brave credentialed live evidence, or human notification delivery/read evidence. Phase 12 behavior was not implemented.

---

## ANIMA-HA-P0-RUNTIME-BASELINE-002 — Phase 0 runtime baseline complete

- Completed: 2026-08-28/29
- Verdict: COMPLETE / PASS
- Retrieval confidence: ADEQUATE
- Evidence level: E4_REGRESSION_PROTECTED for the baseline checks; ARM64 remains E1_OBSERVED metadata evidence.
- Implementation checkpoint: `3fd0bfd1dc2c26798423a8077d2a1d9ca3bc3480`
- GitHub Actions: run `33232446199`, success.

### Work performed

Established the documented Python 3.12 modular package boundary, uv lockfile, environment-only configuration, JSON logging, strict test/lint/type validation, CI, pinned pgvector/PostgreSQL service, runtime-only migrations, simulator readiness entrypoint, and fresh-checkout workflow. Deferred all later-phase household intelligence.

### Acceptance results

- Repository structure documented: PASSED
- Versions reproducibly constrained: PASSED
- Startup/configuration documented: PASSED
- No committed secrets: PASSED; placeholder reviewed
- Configuration varies by environment: PASSED
- Structured logging: PASSED
- Tests/lint/static checks: PASSED
- CI: PASSED
- Database health and persistence: PASSED
- Migration initialization/repeat: PASSED
- Simulator readiness: PASSED
- ARM64/x86-64 compatibility: PASSED at documented evidence level only; native Pi run deferred
- Fresh-checkout reproduction: PASSED on local filesystem
- Dependency qualification records: PASSED
- Clean pushed checkpoint: PASSED

### Risks / blockers

- Native Raspberry Pi execution and target resource qualification remain future evidence items.
- Backup/restore is documented as a later explicit validation, not claimed complete here.
- SFTP-mounted workspace virtualenv symlink/mypy traversal limitation remains environment-specific.

---

## AUTHORITY-BOOTSTRAP-001 — Directive AUTHORITY-BOOTSTRAP-001

- Completed: 2026-08-28
- Verdict: COMPLETE
- Retrieval confidence: ADEQUATE
- Evidence level: E2_REPRODUCED
- Git state / commit: No Git repository initialized; working-tree artifact set inspected.

### Technical state discovered

The project directory was empty and had no existing implementation, tests, dependencies, Git metadata, or nested governance instructions. The connected Notion Authority 3.0 package defines the required root `AGENTS.md`, `.agent/` project-state records, `.agents/` reusable workflow, and Architect startup prompt.

### Work performed

Installed the Authority 3.0 governance package and tuned project identity/state records for ANIMA HA. Installed the user-provided adopted `PROJECT_GOAL.md` contract at the requested prototype boundary. Recorded the canonical Notion SSOT and the absence of a GitHub repository.

### Acceptance results

- Required Authority file set installed: PASSED
- ANIMA HA project identity and SSOT recorded: PASSED
- Adopted goal preserved at requested boundary: PASSED
- Empty implementation state represented honestly: PASSED
- Implementation started: NOT APPLICABLE
- Prototype goal complete: NOT RUN

### Validation

- Initial directory and repository inspection: PASSED
- Authority package retrieved from connected Notion: PASSED
- Installed file inventory/content inspection: PASSED
- Runtime/build/test validation: NOT APPLICABLE

### Assumptions confirmed

- The project directory was new/empty at bootstrap.
- Authority 3.0 Complete Installation Package is the applicable governance package.
- The supplied ANIMA HA goal is the authorized adopted contract.

### Assumptions disproven

- NONE

### Risks / blockers

- No implementation or GitHub history exists yet.
- Technology and dependency choices remain unqualified candidates.

### Architect decision required

YES — synchronize the new project and choose the first bounded implementation/discovery directive.

---

## ANIMA-HA-P0-GOVERNANCE-BASELINE-001 — Directive ANIMA-HA-P0-GOVERNANCE-BASELINE-001

- Completed: 2026-08-28
- Verdict: COMPLETE
- Retrieval confidence: ADEQUATE
- Evidence level: E3_TARGET_TESTED
- Git state / commit: `6fbabc892f53876fd94614ccc531dc7478a80288` (parent `088b267467fff93bfd225b9a94a6f4999759fb9f`).

### Technical state discovered

The local directory was not a Git repository at task start. The public remote was reachable over SSH and contained one clean `main` commit, `088b267467fff93bfd225b9a94a6f4999759fb9f`, with only `.gitignore` and `LICENSE`. No product implementation existed locally or remotely.

### Work performed

Initialized local Git, configured `SketchOTP <sketchotp@gmail.com>`, connected `origin` to `git@github.com:SketchOTP/ANIMA-Home-Automation.git`, preserved the remote baseline as the parent history, corrected portable/public Authority records, updated the public ignore policy, reviewed all candidate files for secrets and machine-specific data, and created governance-only checkpoint `6fbabc892f53876fd94614ccc531dc7478a80288`.

### Acceptance results

- Local project connected to the required GitHub repository: PASSED
- Existing GitHub baseline preserved in one coherent `main` history: PASSED
- No remote content lost: PASSED
- No secret/private runtime material selected for publication: PASSED
- Local Authority state corrected for GitHub/checkpoint: PASSED
- Adopted goal and completion marker preserved: PASSED
- Installed Authority validation: PASSED
- Working tree clean after checkpoint: PASSED
- Governance baseline pushed to GitHub `main`: PASSED
- Exact checkpoint SHA recorded: PASSED
- Product implementation introduced: NOT APPLICABLE / ZERO FILES

### Validation

- Starting Git status/branch/remotes/history: PASSED
- Remote `main` reachability and tree inspection: PASSED
- Candidate public-file inventory and sensitive-material scan: PASSED
- Installed Authority validation: PASSED
- Final Git status and history: PASSED
- Remote `main` contains checkpoint SHA: PASSED
- Product implementation file count: PASSED — zero

### Assumptions confirmed

- The existing remote baseline is the authorized parent history.
- The repository is public and governance files are intended to be published.
- Machine-specific repository paths should not be published; the profile now uses a portable root description.

### Assumptions disproven

- The prior local Authority statement that Git/GitHub were not created was stale; GitHub existed and was reachable.

### Risks / blockers

- The repository remains governance-only; no product or runtime evidence exists.
- Future implementation files require renewed public-safety review before publication.

### Architect decision required

YES — accept or reject this governance-only checkpoint, then authorize the first bounded Phase 1 discovery/implementation directive separately.

---

## ANIMA-HA-P1-REALITY-SUBSTRATE-003 — Phase 1 reality substrate complete

- Completed: 2026-08-29
- Verdict: COMPLETE / PASS
- Retrieval confidence: ADEQUATE
- Evidence level: E4_REGRESSION_PROTECTED for unit/static/build checks; E3_TARGET_TESTED for x86-64 PostgreSQL integration; ARM64 remains E1_OBSERVED metadata evidence.
- Implementation checkpoint: `0ee72b736aa27e1b52d652eafb8e045e4b892148`; GitHub Actions run `33252987351` passed for that exact SHA.

### Work performed

Built ANIMA-owned immutable `EventEnvelope` and `TruthObservation` contracts, a PostgreSQL append-only journal with event/source idempotency, journal queries, a deterministic truth projection with explicit current/stale/unknown/unavailable/conflicting results, projection failure tracking/retry, and journal replay/rebuild. Added synthetic simulator scenarios and a repeatable PostgreSQL integration harness. No Home Assistant, Household Graph, memory, policy, agent, or action behavior was added.

### Acceptance results

- Valid normalized events persist durably: PASSED — PostgreSQL integration.
- Immutable identity, monotonic journal position, separate event/record time: PASSED — contracts/integration.
- Duplicate and concurrent duplicate ingestion: PASSED — unique constraints and 8-way integration test.
- Append-only journal protection: PASSED — database trigger integration test.
- Deterministic queries/order and source-sequence handling: PASSED — implementation/unit/integration.
- Known, stale, unknown, unavailable, and conflicting state with provenance: PASSED — reducer/integration.
- Projection failure preserves event and retries: PASSED — injected x86-64 PostgreSQL integration.
- Restart persistence and full rebuild equivalence: PASSED — x86-64 PostgreSQL integration.
- Unsupported event schema fails explicitly: PASSED — unit contract test.
- CI, Phase 0 regression, package build, public safety, and clean push: PASSED — GitHub Actions run `33252987351`; final metadata checkpoint follows this evidence closure.

### Risks / limitations

- Native Raspberry Pi execution/resource qualification and backup/restore remain future evidence items.
- Current truth reconciliation is generic and intentionally does not include Household Graph semantics, authority, or source-specific Home Assistant behavior.
- PostgreSQL integration evidence is synthetic and x86-64 only; it is not real-home or HA evidence.

## ANIMA-HA-P2-HOUSEHOLD-GRAPH-004 — Phase 2 Household Graph complete

- Completed: 2026-08-29
- Verdict: COMPLETE / PASS
- Retrieval confidence: ADEQUATE
- Evidence level: E4_REGRESSION_PROTECTED for unit/static/build checks; E3_TARGET_TESTED for x86-64 PostgreSQL graph integration; E2_REPRODUCED for synthetic simulator; ARM64 remains E1_OBSERVED manifest/package evidence.
- Implementation checkpoint: `ed261e8a3bc794ededdc3084f63b816152988820`; GitHub Actions run `33261359336` passed for that exact SHA.

### Work performed

Added forward migration `0003_household_graph.sql`, ANIMA-owned canonical graph contracts, deterministic commissioning validation and synthetic fixture, PostgreSQL recursive semantic queries, transactionally journaled graph mutations, provider remap/retirement, rename/alias preservation, Truth-backed presence query, simulator graph scenario, and Phase 2 integration evidence.

### Acceptance results

- Canonical identity, place containment, recursive traversal, cycle rejection, entrance topology, resources/capabilities, and security metadata: PASSED — unit/integration.
- Provider many-to-one mapping, capability mapping, collision/remap, and external-ID isolation: PASSED — PostgreSQL integration.
- Alias resolution, ambiguity behavior, canonical rename, and old-alias preservation: PASSED — unit/PostgreSQL integration.
- Truth binding with underlying event provenance and no new inference: PASSED — x86-64 PostgreSQL integration.
- Transactional commissioning, idempotent reload, graph mutation audit, retirement boundary: PASSED — PostgreSQL integration.
- Phase 1 regression, full tests, Ruff, mypy, build, CI, public safety, restart/persistence, and clean push: recorded at checkpoint closure.

### Evidence limits / risks

- The household is synthetic and provider references are examples; no Home Assistant or physical-home claim is made.
- ARM64 remains manifest/package metadata evidence only; native Raspberry Pi execution and resource measurement remain future gates.
- Current graph commissioning is a deterministic merge/upsert boundary; a future commissioning UI may add explicit replacement/deletion planning.
- Memory, policy, Home Assistant, Luna, plugins, action execution, durable tasks, UI, and voice remain unauthorized.

## ANIMA-HA-P3-GOVERNED-MEMORY-005 — Phase 3 governed memory complete

- Completed: 2026-08-29
- Verdict: COMPLETE / PASS pending independent Architect review
- Retrieval confidence: ADEQUATE
- Evidence level: E4_REGRESSION_PROTECTED for unit/static/build and Phase 1/2 regressions; E3_TARGET_TESTED for x86-64 PostgreSQL memory/routine integration; E2_REPRODUCED for simulator; ARM64 remains E1_OBSERVED manifest/package evidence.
- Implementation checkpoint: recorded in completed task evidence after final commit.

### Work performed

Added forward migration `0004_governed_memory.sql`, `MemoryRecord`/provenance/taxonomy contracts, append-oriented correction and lifecycle service, deterministic precedence and household-isolated retrieval, PostgreSQL full-text derived index with deletion/rebuild and lexical fallback, journaled memory mutation audit, deterministic routine aggregation/rebuild, simulator memory scenario, tests, and Phase 3 documentation.

### Acceptance results

- Canonical memory identity/type/provenance/confidence/lifecycle: PASSED — contract and PostgreSQL integration.
- Explicit preference and active temporary context outrank inferred routine; agent lessons cannot encode authority: PASSED — unit/integration.
- Correction/supersession, automatic/manual expiry, retraction, and index invalidation: PASSED — x86-64 PostgreSQL integration.
- Bounded relevance, subject/graph filters, cross-household isolation, index deletion/rebuild, degraded fallback: PASSED — x86-64 PostgreSQL integration.
- Truth remains separate from memory: PASSED — Truth projection retained its direct value after memory operations.
- Routine bucket probabilities, confidence/sample provenance, deterministic rebuild/update: PASSED — synthetic journal integration.
- PostgreSQL restart persistence, Phase 1/2 regression, simulator, Ruff, mypy, pytest, package build, CI, public safety, and clean push: PASSED — evidence packet.

### Risks / limitations

- Mem0, FastEmbed, pgvector embeddings, and River were qualified but not adopted; semantic retrieval is local lexical only in this checkpoint.
- No Mem0 runtime or external embedding network-egress test is applicable because neither is an adopted dependency; source/import scan and local-only integration observation passed.
- Native Raspberry Pi execution/resource qualification, backup/restore, Home Assistant, Luna, real household, and physical-device evidence remain future work.
- No autonomous memory extraction or agent-lesson loop exists.

## ANIMA-HA-P4-IDENTITY-POLICY-006 — Phase 4 identity and policy complete

- Completed: 2026-08-29
- Verdict: COMPLETE / PASS pending independent Architect review
- Retrieval confidence: ADEQUATE
- Evidence level: E4_REGRESSION_PROTECTED for unit/static/build and Phase 1–3 regressions; E3_TARGET_TESTED for x86-64 PostgreSQL + local OPA integration; E2_REPRODUCED for simulator; E1_OBSERVED for ARM64/amd64 image metadata.
- Implementation and final governed checkpoints are recorded in the completed task evidence after push verification.

### Work performed

Added migration `0005_identity_policy.sql`, ANIMA-owned identity evidence and
assurance contracts, semantic ActionIntent/risk classification, local pinned
OPA/Rego policy evaluation, explicit autonomy configuration, exact confirmation
challenge persistence/consumption, PostgreSQL decision records, Event Journal
policy audit, fail-closed behavior, policy tests, simulator policy scenario,
Phase 4 architecture/dependency documentation, and validation workflow updates.

### Acceptance results

- Identity claim/session/voice/proximity distinction, expiry, and conflict handling: PASSED — unit and integration.
- All required risk classes, four decisions, unknown-risk/admin denial, explicit autonomy, role separation, and memory exclusion: PASSED — OPA integration.
- Strong-auth, geofence-only access, stale Truth, confirmation binding/replay, and purchase approval: PASSED — OPA/PostgreSQL integration.
- OPA failure fail-closed, decision persistence, Event Journal audit, migration repeat, and PostgreSQL restart persistence: PASSED — integration.
- OPA policy check/test, 24 pytest tests, Ruff, strict mypy, Phase 1/2/3 regressions, simulator, package validation, public safety, and clean push: PASSED.

### Risks / limitations

- OPA native ARM64 execution and Pi-class resource measurement remain unverified; official multi-architecture image manifests are observed metadata only.
- Direct SFTP bind-mount/startup was limited by the colon-bearing GVFS path; local temporary policy copies and normal-path Docker behavior were used for runtime evidence.
- No physical identity, Home Assistant, Luna, plugin, action-execution, real-door, or real-house evidence is claimed.

## ANIMA-HA-P5-PLUGIN-CAPABILITY-RUNTIME-007 — Phase 5 plugin capability runtime complete

- Completed: 2026-08-29
- Verdict: COMPLETE / PASS pending independent Architect review
- Retrieval confidence: ADEQUATE
- Evidence level: E4_REGRESSION_PROTECTED for unit/static/build and Phase 1–4 regressions; E3_TARGET_TESTED for x86-64 PostgreSQL/OPA/MCP integration; E2_REPRODUCED for simulator and fresh-checkout reproduction; E1_OBSERVED for ARM64 package metadata.
- Implementation checkpoint: `c186c34bcf93e9ff03d39c3e966fcb540583d478`; CI run `33277823326` passed for that exact SHA.

### Work performed

Added forward migration `0006_plugin_runtime.sql`; ANIMA-owned versioned manifests, compatibility validation, lifecycle state, capability registry, canonical tool descriptors, bounded JSON Schema validation, native entry-point discovery, official MCP v2 stdio/Streamable HTTP adapter, policy-gated invocation, result normalization, scoped secret brokerage, configuration isolation, plugin-event ingress, PostgreSQL persistence/restore, lifecycle audit, native/MCP reference plugins, failing runtime containment, simulator coverage, and Phase 5 documentation.

### Acceptance results

- Manifest version, stable identity, core compatibility, duplicate/collision, schema bounds, and no-install boundary: PASSED — unit tests.
- Native discovery/enable separation, native lifecycle, normalized MCP stdio listing/call, disable/re-enable, persisted restore, and simulator: PASSED — unit/integration/simulator.
- Policy gating, required policy boundary, denial/structured outcomes, manifest risk authority, unknown-risk fail-closed path, and result validation: PASSED — unit and Phase 4 policy integration.
- MCP crash/start failure, timeout, bounded restart attempts, and healthy-plugin independence: PASSED — unit and integration.
- Declared-only fake secrets, sanitized child environment, configuration isolation, no raw secret persistence/audit, network declarations, and plugin event provenance: PASSED — unit/integration/code inspection.
- PostgreSQL migration/repeat, restart persistence (`4|2` plugin/tool rows before and after), Phase 1–4 regressions, full validation, package build, fresh checkout, CI, and public safety: PASSED.

### Evidence limits / risks

- MCP and PostgreSQL runtime evidence is synthetic and x86-64; no Home Assistant, Luna, physical action, real external service, or real household claim is made.
- Streamable HTTP is implemented behind the same adapter but not exercised against a permanent remote service; no remote service was added.
- Native Raspberry Pi execution/resource qualification remains unverified. Subprocess MCP is a failure-isolation boundary, not a malicious-code sandbox; container hardening is deferred.
- Direct build from the GVFS/SFTP checkout remains blocked by its known `.venv` symlink limitation; local-disk fresh-checkout build passed.
- Phase 6 Home Assistant Adapter and later behavior were not implemented.
## ANIMA-HA-P6-HOME-ASSISTANT-ADAPTER-008 — Phase 6 Home Assistant adapter complete

- Completed: 2026-08-29
- Verdict: COMPLETE / PASS pending independent Architect review
- Retrieval confidence: ADEQUATE
- Evidence level: E4_REGRESSION_PROTECTED for unit/static/build and Phase 1–5 regressions; E3_TARGET_TESTED for real x86-64 HA container/PostgreSQL/OPA integration; E2_REPRODUCED for simulator; E1_OBSERVED for ARM64 manifest/package metadata.
- Implementation checkpoint: `ecae55af1894889e0948d11a9ae01288c217c646`; CI `33284454470` passed for that exact SHA.

### Work performed

Added the ANIMA-owned Home Assistant adapter, stable provider scope/inventory, provider-reference mapping, Phase 1 state/event normalization, subscribe-buffer-snapshot synchronization, registry reconciliation, explicit health and bounded reconnect/gap semantics, secret-brokered authentication, and a trusted Phase 5 HA plugin exposing only bounded policy-gated semantic read/power tools with observed-state verification.

### Acceptance results

- Real pinned HA 2026.8.2 authentication, discovery, WebSocket state/registry events, ordinary/unknown/unavailable Truth, mapping/unmapped/many-to-one behavior, and duplicate/race handling: PASSED.
- OPA deny/confirmation/strong-auth gating before HA and low-risk service execution through the Phase 5 gateway: PASSED.
- Fresh observed-state success, deliberate acknowledged-but-unobserved verification failure, disconnect/reconnect/resubscribe/reconcile/gap, invalid authentication, disable/re-enable, and PostgreSQL restore: PASSED.
- Ruff, strict mypy, 43 pytest tests, Phase 1–5 integration regressions, migration repeat, simulator, local-disk fresh-copy locked install/build, public safety, and exact-SHA CI: PASSED.

### Evidence limits

- HA evidence uses isolated virtual/demo entities on x86-64; it is not physical-home/device evidence.
- ARM64/Pi is manifest/package metadata only; native execution and Pi resource qualification remain unverified.
- Customer OAuth, security-access actions, full action concurrency/leases, Luna, and Phase 7 Attention/Context Broker remain unimplemented and unauthorized.

## ANIMA-HA-P7-ATTENTION-CONTEXT-009 — Phase 7 attention/context complete

- Completed: 2026-08-29
- Verdict: COMPLETE / PASS pending independent Architect review
- Retrieval confidence: ADEQUATE
- Evidence level: E4_REGRESSION_PROTECTED for target/unit/static/build and Phase 1–6 regression coverage; E3_TARGET_TESTED for synthetic x86-64 PostgreSQL attention/context/restart; E2_REPRODUCED for simulator/replay CLI; ARM64 remains E1_OBSERVED metadata evidence.
- Implementation checkpoint: `77aafbe5f78333b1c50d042fb1ceb19e74dbe698`; GitHub Actions run `33286882961` passed for that exact SHA.

### Work performed

Built versioned typed attention profiles, immutable decisions, durable PostgreSQL cursor/cooldown/rate/aggregation/failure state, guaranteed reasoning, durable `ReasoningTrigger` records, sparse versioned ContextPackets, deterministic relevance/budgets/pruning, trust and egress controls, persisted packet digests, cloud-safe projection, pure replay/profile comparison, simulator scenario, and high-volume integration harness. No new dependency or service was introduced.

### Acceptance results

- Canonical journal input, transactional cursor, restart/no-skip/no-duplicate behavior: PASSED.
- Guaranteed bypass, duplicate/no-change, cooldown, rate, aggregation/restart, critical fail-toward-trigger: PASSED.
- Sparse Graph/Truth/Event/Memory/Routine/Identity/Tool context with provenance and uncertainty: PASSED.
- Explicit/inferred distinction, memory no-authority, bounded tools, no Rego dump, external distrust, egress redaction, secret exclusion, deterministic pruning, degraded source: PASSED.
- High volume: 10,000 ordinary + 20 guaranteed; expected/actual four aggregates + 20 guaranteed = 24 triggers; all source events retained; midstream restart and pure replay equivalence passed.
- Profile comparison: 24 versus 28 triggers, zero guaranteed loss, actual packet-byte difference reported; no automatic promotion.
- Migrations repeat, 50 tests, Ruff, strict mypy, package build, OPA, Phase 1–5 integration, real isolated Phase 6 HA regression, simulator, replay CLI, public safety, exact-SHA CI: PASSED.

### Risks / limitations

- Native Raspberry Pi/ARM64 execution remains unverified; Phase 7 runtime evidence is synthetic x86-64 PostgreSQL.
- Context budgeting is serialized-byte based and provider-neutral; Phase 8 may add a replaceable model tokenizer after qualification.
- NATS/JetStream and CEL remain deferred until measured consumer/rule complexity justifies them.
- No Luna, cloud cognition, autonomous action, new physical-home behavior, durable tasks, UI, or voice was implemented.

## ANIMA-HA-P8-CODEX-OAUTH-RUNTIME-010R — Phase 8 constrained cognition complete

- Completed: 2026-08-30
- Verdict: COMPLETE / PASS pending independent Architect review
- Retrieval confidence: ADEQUATE
- Evidence level: E4_REGRESSION_PROTECTED for unit/static/build/CI plus Phase 1–7 regressions; E3_TARGET_TESTED for real x86-64 ChatGPT OAuth/Luna A–I and PostgreSQL episode restart; E2_REPRODUCED for scripted simulator; ARM64 remains untested for this runtime.
- Implementation checkpoint: `8486cd10b7962df11898bc8b61b1ec46d0809dd5`; GitHub Actions `33293828743` passed for that exact SHA without OAuth credentials.

### Work performed

Built an ANIMA-owned durable episode runtime around isolated, ephemeral, strict-config `codex exec` turns authenticated by Codex-owned ChatGPT OAuth and explicitly using `gpt-5.6-luna` with medium reasoning. Added cloud-safe ContextPacket reprojection, versioned instructions, schema-only one-decision turns, sequential Phase 5/4 tool-policy routing, argument/result filtering, finite budgets/timeouts, process-group termination, JSONL capability guards, durable usage/outcome/audit, scripted CI adapter, simulator scenario, and local live harness. No new Python package or infrastructure service was introduced.

### Acceptance results

- OAuth status/model/medium configuration, no API-key fallback, exact isolation controls, empty workspaces, ignored user config/rules, bounded stdin/streams, and no raw reasoning persistence: PASSED.
- Dynamic allowed-tool schema, ANIMA argument revalidation, mandatory Phase 5/4 routing, runtime-owned outcomes, confirmation/stronger-auth stops, tool/provider/timeout/budget/boundary distinction: PASSED.
- Cloud-safe packet omission/redaction, tool-output re-filtering, external distrust, secret-free child environment, and server-side retention limitation documentation: PASSED.
- Live A–I broad-catalogue matrix: PASSED; 14 turns; one two-tool model-selected sequence; three no-action results; zero command/file/MCP/web/direct-capability events.
- Usage/latency: 112,592 input, 4,864 cached input, 1,555 output, 508 reasoning-output tokens; median 4,468.88 ms, p95 6,347.26 ms; no API dollar estimate applied.
- Migration repeat, PostgreSQL restart, duplicate claim, 84 tests, Ruff, strict mypy, package build, OPA, Phase 1–7 integrations, real isolated Phase 6 HA, simulator, public safety, and exact-SHA CI: PASSED.

### Risks / limitations

- Codex CLI `0.150.0-alpha.8` is the exact tested binary and requires requalification on update.
- Live evidence is x86-64, synthetic household/tool, and ChatGPT-hosted cognition; no native ARM64/Pi, physical-home, production external-service, API ZDR, or deterministic-model claim.
- One focused weather attempt returned invalid structured output and failed closed before the final complete matrix passed.
- Phase 9 generalized action execution/verification/concurrency, physical-resource locks/leases, durable future tasks, UI, voice, and later behavior remain unimplemented.

## ANIMA-HA-P9-ACTION-EXECUTION-CONCURRENCY-011 — Deterministic action execution complete

- Completed: 2026-08-30
- Verdict: COMPLETE / PASS pending independent Architect review
- Retrieval confidence: ADEQUATE
- Evidence level: E4_REGRESSION_PROTECTED for local static/unit regression evidence; E3_TARGET_TESTED for x86-64 PostgreSQL persistence/advisory-lock behavior and the isolated Home Assistant 2026.8.2 action path. No native ARM64/Pi or physical-home evidence.

### Work performed

Built `ActionExecutionCoordinator` with durable idempotency claims, canonical-resource non-blocking locks, latest-state refresh, Truth preconditions, final Phase 4 policy reauthorization, committed `EXECUTING` fencing before connector invocation, post-action refresh/verification, explicit partial/unknown outcomes, and restart reconciliation. Added migration `0010_action_execution.sql` for action and per-effect records. Added optional Phase 8 routing so consequential tool decisions can use the coordinator; read-only tools retain the existing direct gateway path. Phase 5 now accepts confirmation data on the final gateway policy evaluation.

### Acceptance results

- Fresh-state and stale-precondition rejection before connector invocation: PASSED.
- Non-blocking same-resource conflict with no queueing and distinct-resource lock behavior: PASSED in in-memory/unit and real PostgreSQL advisory-lock harness.
- Duplicate same-key replay executes once; same-key parameter mismatch is an explicit idempotency conflict: PASSED.
- Final policy denial prevents execution; connector timeout/error after execution begins is `UNKNOWN_RESULT`: PASSED.
- Post-action refresh/verifier, verification failure, and connector success without observed verification: PASSED.
- Mixed multi-effect outcome is durable as `PARTIAL`; no compensation or blind retry: PASSED.
- Restart reconciliation distinguishes abandoned plans (`RECOVERY_REQUIRED`) from in-flight side effects (`UNKNOWN_RESULT`): PASSED.
- Local-filesystem Ruff, strict mypy, 93 tests, migration repeat, durable PostgreSQL action replay, and advisory-lock conflict: PASSED.
- `scripts/verify_phase9_action_execution.py`: PASSED — real isolated HA `set_power` execution through the coordinator, contradictory authenticated requests from two household principals, real PostgreSQL same-resource race with no queueing, post-action provider refresh, and durable replay without a second connector call.

### Risks / limitations

- The live action harness uses isolated virtual/demo HA entities on x86-64; it does not establish physical-home behavior or general provider qualification.
- Native ARM64/Raspberry Pi execution is unverified. No production external connector or Phase 10 durable task behavior was added.
- Connector idempotency is represented by the ANIMA durable key and connector metadata; providers that do not support idempotent execution are rejected before invocation.
- A process crash after an external call begins is conservatively `UNKNOWN_RESULT`; reconciliation is explicit and never retries or compensates automatically.

## ANIMA-HA-P9-CHECKPOINT-CLOSURE-011C — Published Phase 9 checkpoint

- Completed: 2026-08-30
- Verdict: COMPLETE / Phase 9 `COMPLETE — PENDING ARCHITECT ACCEPTANCE`
- Retrieval confidence: ADEQUATE
- Starting accepted checkpoint: `7153b127106c8e921185a38b1b4606fa42e5f92b` (Phase 8).
- Implementation checkpoint: `7b3d759992ce6cef56914ef19aa8626df0214031`; GitHub Actions run `33323237014` passed on the exact SHA.
- Final governed checkpoint: this closure commit; exact SHA and final GitHub Actions run are recorded in the Notion SSOT after push verification.

### Fresh validation

- Local-filesystem `uv sync --locked --dev`, Ruff format/check, strict mypy, 94 tests, migration repeat, OPA 4/4, and package sdist/wheel: PASSED.
- Phase 1–8 regression harnesses, including real isolated HA Phase 6 and PostgreSQL Phase 7/8 restart evidence: PASSED.
- Phase 9 real isolated HA coordinator harness: PASSED for real `set_power`, contradictory Alex/Sam same-resource contention, post-action verification, and durable replay without a second connector call.
- Additional critical checks: sorted multi-resource lock order, concurrent duplicate at-most-once dispatch, committed `EXECUTING` before connector dispatch, and advisory-lock release on session loss: PASSED.
- `git diff --check` and public repository safety scan: PASSED before implementation publication.

### Publication boundary

- The implementation and evidence are now visible on GitHub `main`; no unrelated files, household/private runtime artifacts, secrets, or Phase 10 behavior were included.
- Evidence remains x86-64 and isolated virtual/demo Home Assistant only; native ARM64/Raspberry Pi, physical-home, high-risk/security, production-provider, and Architect acceptance evidence are not claimed.

## Authority snapshot correction — Phase 9 closure metadata

- Corrected the mutable `CURRENT.md` wording to identify Phase 9 as `COMPLETE — PENDING ARCHITECT ACCEPTANCE` and to record the exact published implementation/final checkpoints and CI runs. No product or architecture behavior changed.

## ANIMA-HA-P9-EXECUTION-HARDENING-011H — Phase 9 execution hardening published

- Completed: 2026-08-30
- Verdict: COMPLETE — PENDING ARCHITECT ACCEPTANCE; Architect disposition remains `CONTINUE`.
- Starting checkpoint: `1b546f8cfbde0e8009adb769e2817ff03a7cc51e` (published Phase 9 checkpoint under review).
- Implementation checkpoint: `fd9cd822cc6bb10d5ab49b705a9e365c9fd42160`.
- Implementation GitHub Actions: `33339779556` passed on the exact implementation SHA.

### Corrective result

- Trusted `ActionSafetySpec` metadata now owns canonical lock scopes, mandatory Truth preconditions, expected effects, and provider-native-idempotency capability; Luna/model arguments cannot remove or weaken those requirements.
- The live AgentRuntime path derives baseline known-state preconditions before creating `ActionRequest`, and the coordinator performs its own trusted safety-spec checks.
- `ProviderExecutionContext` carries ANIMA execution identity and an optional provider key outside model-visible schemas; unsupported native idempotency remains executable with local ANIMA deduplication and no blind ambiguous retry.
- Connector acknowledgements and effect claims are persisted as evidence only. Observable consequential effects require fresh post-dispatch observation, Truth reconciliation, and verification before terminal outcome derivation.
- Possible-dispatch timeout/error outcomes are refreshed and reconciled. Verified success returns success with ambiguity retained; inconclusive state returns `UNKNOWN_RESULT`; definitive mismatch returns verification failure; mixed verified/unknown effects return `PARTIAL`.
- Already-satisfied actions return success with `executed=false`, fresh evidence, and zero connector calls.

### Fresh evidence

- 63 focused hardening/coordinator/provider/agent tests and 94 full pytest tests: PASSED.
- Ruff on changed files, strict mypy (36 source files), OPA 4/4, package sdist/wheel, migration initial/repeat, Phase 1–5 integrations, Phase 7 restart/replay (10,020 events), Phase 8 persistence/restart, and Phase 6/9 isolated HA harnesses: PASSED.
- PostgreSQL advisory-lock conflict/ordering/release, local idempotency, concurrent duplicate at-most-once dispatch, stale/manual-change rejection through AgentRuntime, provider-context forwarding, connector-claim non-authority, timeout reconciliation, partial verification, crash/restart recovery, and no-op dispatch tests: PASSED.
- Targeted public-safety scan and `git diff --check`: PASSED.

### Limits and publication

- Evidence was reproduced from a local filesystem because the GVFS/SFTP workspace was unreliable for environment execution. HA evidence is isolated virtual/demo HA on x86-64; native ARM64/Pi, physical-home, high-risk/security, and production-provider behavior are not claimed.
- This outcome does not accept Phase 9. It records a bounded correctness continuation for Architect review. No Phase 10 behavior was implemented.
- Governed evidence closure is a subsequent metadata-only checkpoint; its exact SHA and final GitHub Actions result are recorded in the Notion SSOT after push verification.

## ANIMA-HA-P10-DURABLE-TASK-ENGINE-012 — Durable task engine

- Completed: 2026-08-31
- Verdict: COMPLETE — PENDING ARCHITECT ACCEPTANCE
- Retrieval confidence: ADEQUATE
- Starting accepted checkpoint: `7f09b52f8773901ea73221f60b40414874809fda` (Phase 9).
- Implementation checkpoint: to be filled with exact SHA and hosted CI after publication.
- Final governed checkpoint: to be filled with exact SHA and hosted CI after evidence closure publication.

### Result

Built ANIMA-owned declarative `DurableTask`, `TaskSchedule`, and `DurableTaskRun` contracts with one-shot, fixed-duration interval, and five-field cron schedules; explicit IANA timezone, misfire, expiry, and DST policy; recursive executable-payload rejection; household-scoped task lifecycle; idempotent creation; PostgreSQL persistence; `FOR UPDATE SKIP LOCKED` claims; bounded leases/attempts; deterministic occurrence/event identities; guaranteed `scheduled_reasoning_due` events; a local worker entry point; and a bridge into the existing Attention → Context → AgentRuntime path.

### Evidence

- Phase 10 unit tests cover DST spring/fall behavior, declarative payload safety, creation idempotency/conflict, deterministic due events, concurrent in-memory claims, lease reclaim/replay, misfire/pause/resume/cancel, and household isolation.
- PostgreSQL evidence is produced by `scripts/verify_phase10_durable_tasks.py`: migration/repeat, idempotent creation, two-worker claim race, journal source-event deduplication, and lease recovery.
- Full Phase 0–9 regression/static/build/OPA/isolated HA validation and exact-SHA hosted CI are required before Architect closure.

### Limits

Evidence is x86-64 and local/isolated; native ARM64/Pi, physical-home, production-scale scheduler capacity, Phase 11, and production external connectors are not claimed. No Phase 11 behavior was implemented.

## ANIMA-HA-P10-TASK-POLICY-INTEGRATION-012H — Task integration and ownership hardening

- Completed: 2026-08-31
- Verdict: COMPLETE — PENDING ARCHITECT ACCEPTANCE; Architect disposition remains `CONTINUE`.
- Retrieval confidence: ADEQUATE.
- Starting governed checkpoint: `21dde3cddc3ea4aa5af3e59e6a0334b62d37a7a2`; hosted CI `33418246958` had passed.
- Implementation checkpoint: `27f7c3fb8ce53c4eb988d7de22c63672770998a8`; hosted CI `33425928381` passed on that exact SHA.

### Corrective result

- ANIMA Core now assigns `READ_ONLY`, `POLICY_GATED_INTERNAL`, or `COORDINATED_CONSEQUENTIAL` execution boundaries. Only the exact trusted built-in durable-task manifest receives the internal boundary; arbitrary plugin metadata cannot self-declare a Phase 9 exemption.
- AgentRuntime sends all task reads/mutations through the Phase 5 gateway. Task mutation schemas contain only declarative task content and schedule; ANIMA injects current household, principal, episode, origin, tool-request identity, ordinal, and deterministic system idempotency through trusted `InvocationContext`.
- Task creation replay is idempotent by that system identity and the existing parameter fingerprint. Creator provenance is recorded as historical evidence and is not reused as future authentication.
- In-memory and PostgreSQL lifecycle guards match. Pause is only `ACTIVE -> PAUSED`, resume is only `PAUSED -> ACTIVE`, cancellation is terminal, and a current unexpired claimant is required for dispatch transitions. A cancelled `DISPATCHING` run can be terminalized before event append, preventing an orphan.
- Due tasks still emit guaranteed deterministic `scheduled_reasoning_due` events. The integration harness proves a new due-time ContextPacket and re-entry through AgentRuntime; later physical/provider actions remain Phase 9-coordinated.

### Validation and evidence

- `uv sync --locked --dev`, Ruff format/check, strict mypy, 122 pytest tests, OPA 4/4, package sdist/wheel, and migration initial/repeat: PASSED.
- Phase 1–5, Phase 7–8, isolated real Home Assistant Phase 6, isolated real Home Assistant Phase 9, and fresh PostgreSQL Phase 10 harness: PASSED.
- Target evidence: real AgentRuntime task schedule and lifecycle mutation, ALLOW/DENY/confirmation/stronger-auth policy outcomes, trusted provenance/idempotency replay, lifecycle parity, stale-worker rejection, cancellation cleanup, deterministic event replay, lease recovery, fresh scheduled cognition, and creator-identity non-authority: PASSED.
- Public safety and `git diff --check`: PASSED. No secrets, household/private runtime state, or Phase 11 behavior were included.

### Limits and publication

- Evidence is local x86-64 and isolated virtual Home Assistant; native ARM64/Pi, physical-home, production-provider, high-risk, and production-scale scheduler behavior are not claimed.
- Final governed checkpoint: `ae18833e2ddffd30b17b613248d1c2206062b66a`; hosted CI `33428938215` passed on that exact SHA. Phase 10 remains pending Architect acceptance.

### 012H corrected scheduled-action evidence

- The Phase 10 evidence harness now drives a due-time scripted cognition episode into a synthetic consequential home action. The action uses the existing AgentRuntime → Phase 9 coordinator path, fresh pre/post Truth snapshots, and one connector dispatch; it reports `scheduled_future_action_phase9=PASS` with a verified `SUCCEEDED` action record.
- Corrected implementation checkpoint: `945f89c13b67e52a9027d3f42cc3e2bccd5608d2`; GitHub Actions `33428295199` passed on that exact SHA.
- Fresh validation passed: 122 tests; Ruff format/check; strict mypy; OPA 4/4; sdist/wheel; migration initial/repeat; Phase 1–5, 7–10 harnesses; isolated real HA Phase 6 and Phase 9; `git diff --check`; and public-safety scan.
- The rebuilt authoritative `.venv` produced one transient MCP stdio startup failure during the first full run; the focused test and immediate full rerun passed. No source or test correction was required for that transient environment event.
- The earlier governed checkpoint `17d627b988aebb89b419671de8ee3c5a5525f516` is superseded for final closure by the corrected evidence. Final governed checkpoint `ae18833e2ddffd30b17b613248d1c2206062b66a` passed CI `33428938215`. Phase 10 remains `COMPLETE — PENDING ARCHITECT ACCEPTANCE`; Phase 11 was not implemented.

## ANIMA-HA-P11-EXTERNAL-GATE-CLOSURE-013H — Calendar OAuth and cognition integration hardening

- Architect disposition: `CONTINUE`; Phase 11 remains `COMPLETE — PENDING ARCHITECT ACCEPTANCE`. Phase 12 remains unauthorized.
- Starting governed checkpoint: `0aaad4a287efaf26d02afac7f1d55d1edbbc0405`; hosted CI `33442786332` passed.
- Implementation checkpoint: `dde3e2bc42fc5004ddf06690ddbd9dc9941999f8`; hosted CI `33445636772` passed on the exact SHA.
- Replaced the short-lived Calendar access-token dependency with an ANIMA-owned `google-auth` refresh boundary using brokered client ID, client secret, and refresh token references. The adopted owned-calendar scope is `https://www.googleapis.com/auth/calendar.events.owned`; cached, expired, restart, revoked, and 401 refresh paths are covered.
- Expanded `scripts/verify_phase11_external.py` to report independent Brave web/place/product and Google Calendar list/create-readback results. Current statuses are `EXTERNAL_RESOURCE_GATE` for both credentialed provider families because no operator credentials are present; no live credential claim is made.
- Added actual AgentRuntime shared-catalogue selection tests for weather, recipes, web research, and places; actual next-turn hostile external-content containment; and a durable-task restart-mode follow-up with a distinct ContextPacket and fresh external read. Existing PostgreSQL Phase 10 harness remains the durable scheduler/lease evidence; the new external comparison fixture is deterministic and in-memory.
- Fresh validation: full pytest, changed-file Ruff, strict mypy, `uv build --sdist --wheel`, `git diff --check`, live synthetic Open-Meteo/TheMealDB/ntfy, and public-safety scan passed. The GVFS/SFTP workspace could not launch processes; `/srv/ATLAS` was used for reproduction.
- Prior governed checkpoint: `439c12a5872b7844f77ad36fa57672f634d0ee52`; hosted CI `33445878287` passed on the exact SHA.
- Final governed evidence checkpoint: `abc9bece8b4827828ca759993191a1f20338d442`; hosted CI `33446946952` passed on the exact SHA.
- No Phase 12 behavior was implemented.

### 013H PostgreSQL fresh-external-follow-up amendment

- Evidence amendment checkpoint `f069e5c0d1d42d0a74eba3267f8393f325509429`; hosted CI `33446725375` passed on the exact SHA.
- `scripts/verify_phase10_durable_tasks.py` now proves through PostgreSQL persistence/restart and the actual scheduled-cognition bridge: external weather value `17` at task creation, fresh value `23` after the due-time episode, distinct ContextPacket identity, and a future consequential action verified through the existing Phase 9 coordinator.
- Existing lifecycle parity, stale-worker, cancellation, idempotency, replay, and lease-recovery evidence remains green. The provider is deterministic MockTransport; no live external credential claim is made.
- Phase 11 remains `COMPLETE — PENDING ARCHITECT ACCEPTANCE`; Phase 12 remains unauthorized.

## ANIMA-HA-P11-PRODUCT-RESEARCH-CLOSURE-013R2 — Walmart-backed product research

- Completed: 2026-09-01
- Verdict: `IMPLEMENTATION COMPLETE — PENDING ARCHITECT ACCEPTANCE`; Architect disposition remains `CONTINUE`.
- Starting governed checkpoint: `23aa71d774c75529d7e8412e3060446d42a9cf4d`.
- Existing LedgerMind Walmart source was inspected read-only on Atlas. Its status-only smoke test passed signed catalogue/search/store/price probes, with cart push unsupported. ANIMA copied the bounded API contract and normalization approach, not credentials or runtime data.
- ANIMA now provides `shopping.search_products` through a fixed-host signed Walmart adapter. It preserves product identity separately from retail offers, timestamps price/availability, keeps results `EXTERNAL_UNTRUSTED`, and does not implement cart, checkout, scraping, CAPTCHA bypass, or arbitrary network access.
- Actual AgentRuntime product-catalogue integration passed. Credentialed Atlas live evidence returned 9 distinct `wireless headphones` candidates and 10 distinct `air fryer` candidates; both passed the three-candidate usefulness threshold.
- Fresh validation passed: locked environment sync, Ruff, strict mypy, full pytest (`139 passed`), OPA, package build, diff check, and public-safety scan. Local absent-secret execution remains an explicit Walmart resource gate.
- Limitation: the operator's Walmart entitlement cost/terms were not independently requalified in this bounded continuation; no universal zero-cost claim is made. Phase 12 remains unauthorized.
- Implementation checkpoint: `fb0a6a02c9a48aaa7254e1eb69ec77c1fcd8469a`; hosted CI `33501513385` passed on the exact SHA. Final governed SHA/CI follow this evidence-only closure commit.

## ANIMA-HA-P11-FREE-LOCAL-REALIGNMENT-013R — Implementation result

- Verdict: `IMPLEMENTATION COMPLETE — PENDING ARCHITECT ACCEPTANCE`; Architect disposition remains `CONTINUE` until the published checkpoint is independently reviewed.
- Brave Search and Google Calendar are superseded/deferred for this prototype. Private pinned SearXNG supplies bounded web/product JSON search; OpenStreetMap Overpass supplies category-mapped POI reads; the first-party PostgreSQL calendar supplies household-scoped event CRUD.
- SearXNG is loopback-only/private, uses fixed `duckduckgo` and `wikipedia` engines, and runs without Valkey. Local calendar mutations are Core-approved `POLICY_GATED_INTERNAL`; model-controlled host, engine, raw query, provenance, and idempotency inputs are rejected or absent.
- Fresh evidence passed: 134 tests; Ruff; strict mypy; OPA 4/4; package sdist/wheel; migration initial/repeat including `0012_local_calendar`; healthy SearXNG live web/product JSON; Overpass live synthetic POI; local calendar AgentRuntime integration; `git diff --check` and public-safety review.
- Evidence limits: local x86-64 reproduction, synthetic/public provider traffic, no native ARM64/Pi, production scale, physical-home, or human-notification claim. Phase 12 was not implemented.
- Implementation checkpoint: `558c689cac96f3bddbd636b4d1b9e20d055b221d`; hosted CI `33458814906` passed on that exact SHA. Final governed checkpoint is recorded after the closure publication commit and its exact hosted CI.

## ANIMA-HA-P11-WALMART-ENTITLEMENT-QUALIFICATION-013R3 — Entitlement investigation

- Completed: 2026-09-01
- Verdict: `BLOCKED — WALMART_CLARIFICATION_REQUIRED`; Architect disposition `INVESTIGATE — PROVIDER ENTITLEMENT QUALIFICATION`.
- Starting repository state: clean `main` at `a1122b32d1e9d6548b5c78bd1256185d60b4d281`, matching `origin/main`; no implementation files changed.
- LedgerMind was inspected read-only on Atlas. Its runbook/source identifies Walmart.io affiliate APIs, the signed `https://developer.api.walmart.com/api-proxy/service/affil/product/v2` family, stage/production application keys, and optional Impact publisher ID. The sanitized prior smoke evidence establishes technical operation only, not permission for ANIMA.
- Official current sources establish: Walmart Affiliate enrollment is free but subject to acceptance; Walmart may approve each Affiliate Website; qualifying links must be Walmart/Platform-provided and direct to Walmart; qualifying-link displays require clear/conspicuous advertising disclosure; qualifying links may not be redistributed/repurposed; current product price/availability must be maintained within 24 hours of updates; and the license is limited, non-transferable, revocable, and tied to Program purposes. Current Marketplace API-license terms are recorded as contextual only because they do not establish governance of the exact affiliate endpoint.
- Entitlement result: the existing application name/type, approved site/application surface, production approval, cross-project reuse permission, private-local-assistant permission, exact qualifying-link/publisher-ID rule, exact affiliate API rate limit, and current support/deprecation status could not be established from public sources, LedgerMind records, or an already-authorized dashboard session. HTTP success was not treated as authorization.
- Cost result: `UNKNOWN` for the specific API entitlement. The affiliate program itself is free to join, but current API-license material allows fees if communicated and no account-specific pricing exhibit was available.
- No Walmart/Impact login, account change, application registration, agreement acceptance, support request, secret inspection, private-key inspection, credential copy, or implementation change occurred.
- Phase 12 remains unauthorized. The Walmart provider implementation remains preserved as a candidate pending the exact operator/Walmart clarification.

## ANIMA-HA-P11-FREE-LOCAL-HARDENING-013R1 — Policy and target qualification

- Date: 2026-09-01
- Verdict: `IMPLEMENTATION COMPLETE — EXTERNAL_RESOURCE_GATE`
- Disposition: `CONTINUE`; Phase 12 remains unauthorized.
- Starting checkpoint: `179f36e98c5c31595231bee8bbbd17a1ed89dea7`, clean `main` tracking `origin/main`.
- Calendar correction: local mutations use `LOW_RISK_HOME_CONTROL` while remaining Core-owned `POLICY_GATED_INTERNAL`. Real pinned OPA allowed an authenticated resident with `LOW_RISK_HOME_CONTROL_AUTHORIZED` and default-denied an anonymous direct request.
- PostgreSQL target evidence: create/replay, creation-key misuse conflict, get/list, update, stale-update conflict, cancel/repeat cancel, reconnect persistence, household isolation, trusted bounded audit provenance, and zero Phase 9 action rows passed.
- SearXNG target evidence: adopted digest manifest lists amd64, arm64, and arm/v7; local x86-64 qualification measured approximately 95 MiB idle, 2.4 seconds startup-to-query, and 3.3 seconds restart-to-query. Wikipedia returned one source-linked result; DuckDuckGo, Startpage, and Qwant returned CAPTCHA during qualification. No second free general engine was adopted; strict product search remains an external-resource gate.
- Strict live harness: Open-Meteo, TheMealDB, Overpass, and web reference passed; product target failed honestly with nonzero strict-mode status. Focused tests, changed-file Ruff, strict mypy, package build, migration checks, diff check, and public-safety review passed. Full pytest passed (`136 passed`) after refreshing the locked development environment; the first run had one transient, pre-existing Phase 5 MCP stdio startup failure and no Phase 5 code was changed.
- Implementation checkpoint: `c24b8eab5abe9acc31b4f54a321b0270399f3549`; hosted CI run `33462705630` passed on the exact SHA. The governed evidence-closure checkpoint follows this implementation checkpoint.
- Governed evidence closure checkpoint: `bf62877bcddd4683e4e7c046c2cb0233ef84f0b5`; hosted CI run `33462809329` passed on the exact SHA. Phase 11 remains `IMPLEMENTATION COMPLETE — EXTERNAL_RESOURCE_GATE`, pending Architect acceptance.
- No Phase 0–10 architecture or Phase 12 behavior changed.

## Phase 11 Best Buy product-provider qualification — 2026-09-01

- Directive: ANIMA-HA-P11-BEST-BUY-PRODUCT-PROVIDER-013R4; Architect disposition REPLAN; Phase 12 remains unauthorized.
- Starting SHA: b5635d07505de2ceba071f984fd7189c8ba18cd9; starting tree clean and tracking origin/main.
- Official Best Buy sources confirm the active Products API, ordinary API-key registration, fixed REST host, product search syntax, product catalog fields, 50,000/day and 5/sec rate limits, Commerce API separation, attribution/link/branding obligations, and a maximum 72-hour Content storage/cache period.
- Current ANIMA persistence evidence is decisive: sanitize_tool_result() retains full bounded provider result data, and PostgresEpisodeStore.record_tool_request() stores it indefinitely in anima_agent_tool_requests.sanitized_result; no expiry or purge path exists.
- Result: BLOCKED — BEST_BUY_RETENTION_COMPLIANCE. Best Buy was not integrated, no key or live request was used, no production behavior changed, and no commit was required. Walmart remains preserved but deferred, not an active fallback.
- Required next action is Architect authorization for a bounded retention/compliance design; provider implementation and Phase 12 remain blocked.

## ANIMA-HA-P11-RESTRICTED-CONTENT-PERSISTENCE-013R5 — Restricted content hardening

- Completed: 2026-09-01
- Verdict: `CONTINUE / HARDEN` — implementation/evidence complete for Architect review; live provider gate remains `EXTERNAL_RESOURCE_GATE_BEST_BUY_KEY`.
- Starting SHA: `67b72bf52e1f45e33b9c35a1c0c89e87cf47f7ee`, clean `main == origin/main`; prior CI `33509333301` passed exact.
- Core correction: Best Buy is `EPHEMERAL_RESTRICTED` by ANIMA-owned tool identity. Full content remains in the active process only; durable episode/tool/turn/export paths store structural projections, hashes, provenance, trust, policy, counts, and explicit redaction markers.
- Taint rule: after a successful restricted result, the active caller receives the full live answer, while final durable response content is replaced by `[CONTENT_NOT_DURABLY_RETAINED]` and all later tool requests are rejected with `RESTRICTED_EXTERNAL_CONTENT_SIDE_EFFECT_BLOCKED`.
- Provider: bounded Best Buy Products API adapter and manifest were added behind fixed `api.bestbuy.com` HTTPS and model-visible `query`/`count` only. Attribution, source links, external price provenance, and future branding metadata are preserved. The key is absent; no live Best Buy evidence is claimed.
- Evidence: targeted provider/AgentRuntime tests, full pytest, strict mypy, changed-scope Ruff, OPA `4/4`, package build, `git diff --check`, real PostgreSQL database/export sentinel scan, duplicate replay, unrestricted durability, and Phase 10 regression harness passed. Repository-wide Ruff remains non-clean only in pre-existing unrelated Phase 5 evidence script `scripts/verify_phase5_plugins.py`.
- Limitations: `pg_dump` is not installed, so export safety used an in-process JSON export of every public `anima_*` table; validation used `/srv/ATLAS` because GVFS/SFTP cannot reliably launch Python; native ARM64/Pi and credentialed Best Buy live evidence remain unclaimed.
- Phase 12 was not implemented.

## ANIMA-HA-P11-UPCITEMDB-PRODUCT-PROVIDER-013R6 — Product-provider closure

- Completed: 2026-09-01
- Verdict: `UPCITEMDB_PRODUCT_PROVIDER_PASS` technically; Phase 11 remains pending Architect acceptance.
- Starting SHA: `5ddf1eceb1346377d1ab3f857f1cadb9eeb3cf61`, clean `main == origin/main`.
- Implementation SHA: `2031f0a9ebded7e7a444516ab619f685d519349f`; hosted CI `33562526807` passed on that exact SHA.
- Qualification: official UPCitemdb free Explorer was live at `https://api.upcitemdb.com/prod/trial/search`; no signup or API key was used. The two live queries returned five distinct EAN-identified products each. `wireless headphones` returned 13 bounded offers and `air fryer` 19; response headers reported a 100 combined-request ceiling and decreasing remaining counts.
- Provider: added fixed-host `UPCItemDBProductProvider`, Core-restricted manifest, no-secret factory, bounded product/offer normalization, separate historical-price ranges, preserved provider-returned offer links, and a conservative 20-search/day plus 15-second local pacing limiter honoring rate-limit headers and `Retry-After`.
- Integration: actual deterministic AgentRuntime product selection passes through `shopping.search_products`; restricted results remain external/untrusted, live-only, and taint the episode. Existing PostgreSQL/export sentinel hardening was rerun with UPCitemdb sentinels.
- Validation: targeted tests, full pytest, strict mypy, Ruff, package build, OPA, Phase 10 regression, restricted PostgreSQL/export scan, live Phase 11 harness, diff-check, and public-safety scan passed. SearXNG remained an explicit unavailable live gate in this environment; this did not affect the UPC strict target.
- Limitations: offer timestamps show historical/stale observations in the live catalog; no current-price guarantee is made. Native ARM64/Pi and production-scale evidence remain unclaimed. Phase 12 was not implemented.

## ANIMA-HA-P12-CUSTOM-LOCAL-INTERFACE-014 — Local implementation checkpoint

- Status: implemented locally; pending validation, publication, and Architect acceptance.
- Starting governed SHA: `918365ce7c6145780112a808411d750fb0e289eb`; Phase 11 accepted with CI `33562645002`.
- Implementation: ANIMA-owned FastAPI API/view models, OAuth/session boundary, `0013_ui_sessions.sql`, React/Vite responsive UI, SSE invalidation, Docker/Compose, deterministic UI harness, and Playwright desktop/tablet/phone evidence.
- Security posture: HttpOnly SameSite session cookie, server-side SHA-256 session/CSRF digests, exact same-origin mutation checks, CSP/no-store/security headers, no browser localStorage/IndexedDB/service worker/external assets, and no raw HA/DB/policy exposure.
- Evidence boundary: deterministic TestClient and browser evidence establish the local interface contract. Production conversation/command bridges remain explicit host-injected seams and are not claimed as live Core integration until wired and tested.
- Phase 13 remains unauthorized.

## ANIMA-HA-P12-BROWSER-ACCEPTANCE-EVIDENCE-CLOSURE-014H5 — governance/CI reliability checkpoint

- Governance checkpoint: `828230a73d3c9097bab448192747a3f6786c0d4f`; hosted CI `33697593173` passed on the exact head.
- The workflow now waits for healthy PostgreSQL/OPA Compose containers before migration. The prior run `33697435341` failed only at transient database readiness; no H5 target had started.
- H5 remains partial and `CONTINUE`; browser-visible denial, provider recovery, restricted-content reload/storage, same-session process restart/SSE, and browser-visible isolated-HA journeys remain unrun. Phase 13 remains unauthorized.

## ANIMA-HA-P12-CUSTOM-LOCAL-INTERFACE-014 — Governed closure

- Starting accepted SHA: `918365ce7c6145780112a808411d750fb0e289eb`; Phase 11 hosted CI `33562645002` passed on that exact SHA.
- Implementation SHA: `8a8f798d5d2319e690572d69a323e10459924bce`; hosted CI `33572829176` passed on that exact SHA.
- Fresh local validation: `uv sync --locked --dev`, Ruff, strict mypy, full pytest, deterministic UI harness, TypeScript checks, Node unit tests, Vite production build, Playwright 9-test desktop/tablet/phone matrix, package sdist/wheel, Docker UI build, Compose config, `git diff --check`, and public-safety scan passed.
- API evidence: public health and unauthorized boundaries pass; test OAuth state is single-use; sessions retain only digests; exact HA-user mapping is fail-closed; semantic view models contain no raw table names; CSRF and exact same-origin mutation checks pass; SSE is bounded invalidation-only.
- UI evidence: same-origin API use, no localStorage/IndexedDB/service worker/external assets, responsive dashboard/navigation/conversation/task/capability views pass in Playwright across desktop, tablet, and phone.
- Security/evidence limits: real HA OAuth consent, live household commissioning, native ARM64/Pi, production TLS, and host composition of the existing journal→attention→context→AgentRuntime and Phase 5/4/9 command bridges remain unclaimed. The production service fails closed until those bridges are injected; the test echo is not production cognition evidence.
- CI correction: the first implementation run `33572285917` failed at strict-mypy test typing; the bounded test-typing fix and MCP stdio startup-handshake bound are included in the implementation SHA above. No Phase 13 behavior was added.
- Final governed checkpoint: this governance closure commit, published after the implementation checkpoint and tracked by the exact Git SHA and hosted CI recorded in the final handoff/Notion readback.
- Verdict: `COMPLETE — PENDING ARCHITECT ACCEPTANCE` at the published Phase 12 evidence boundary; Phase 13 remains unauthorized.

## ANIMA-HA-P12-CORE-INTEGRATION-PORTFOLIO-CLOSURE-014H — Integrated implementation checkpoint

- Date: 2026-09-02
- Starting accepted checkpoint: `800c4cc4b1783e3f755cabff37c3db091b0c9ab1`.
- Implementation checkpoint: `208b7e546d8485539d2ae06427d268af116f9ceb`; hosted CI `33580734640` passed on that exact SHA.
- Result: the configured UI now composes the existing Core journal, Attention, Context Broker, AgentRuntime, PluginManager/Tool Gateway, OPA policy service, durable tasks, local calendar, and Phase 9 coordinator through `src/anima_ha/ui_runtime.py`.
- Evidence: real AgentRuntime journal-trigger trace, policy-gated task mutation, configured-app composition smoke test, 160 Python tests, OPA 4/4, package build, TypeScript/frontend tests/build, Playwright 9-test responsive matrix, Compose config, UI container build, public-safety scan, and three actual synthetic-data screenshots passed.
- Status: Phase 12 remains pending Architect acceptance until governance closure is published and independently reviewed. Phase 13 was not implemented.

## ANIMA-HA-P12-COMMISSIONED-RUNTIME-TRUTH-CLOSURE-014H2 — Local implementation result

- Date: 2026-09-02
- Verdict: `IMPLEMENTATION COMPLETE — PENDING ARCHITECT ACCEPTANCE` locally; publication and hosted CI remain required.
- Implementation: `PostgresCommissionedIdentityResolver` resolves HA users only through commissioned graph provider references and canonical `PERSON` → `MEMBER_OF` household edges. `build_postgres_core()` composes the accepted PostgreSQL/OPA Core and qualified Phase 11 providers, and registers HA only from complete operator commissioning configuration. `PostgresHouseholdReadModel` no longer calls `DemoHouseholdReadModel`.
- Evidence: focused unit tests pass; the real local PostgreSQL/OPA target passes task and local-calendar mutation plus Journal → Attention → ContextPacket → AgentRuntime conversation. The target uses a scripted model adapter and synthetic commissioned graph fixture; HA remains an explicit resource gate on this host.
- Evidence limits: no live HA OAuth/physical-home, native ARM64/Pi, production TLS, or real household-data claim. Phase 13 was not implemented.

## ANIMA-HA-P12-COMMISSIONED-RUNTIME-TRUTH-CLOSURE-014H2 — Published implementation checkpoint

- Implementation checkpoint: `5d52c45c72520611de56361af9010419f2869c6c`; hosted CI `33654654675` passed on that exact SHA.
- The checkpoint publishes the commissioned graph-identity resolver, graph/Truth/plugin-backed PostgreSQL UI read models, accepted Phase 11 provider composition, explicit HA commissioning configuration, and the deterministic real PostgreSQL/OPA verification target. No Phase 13 behavior was added.
- Governed closure checkpoint: `bc7849dba3b65b837aacf2b16e8b7653fae97d08`; hosted CI `33655337251` passed on that exact SHA. Status: `COMPLETE — PENDING ARCHITECT ACCEPTANCE`.

## ANIMA-HA-P12-FINAL-UX-AUTHORITY-ACCEPTANCE-CLOSURE-014H3 — Final convergence

- Starting governed checkpoint: `7524cd67daee305e8e4bc4446623fa022fee0cd2`; hosted CI `33655737686` passed on that exact SHA.
- Implementation checkpoint: `37116b03c65bfac54a5261f30160e9030aa6011c`; hosted CI `33671817841` passed on that exact SHA.
- Implementation result: configured `create_app()` now composes the existing PostgreSQL/OPA/Core cognition and command stack; semantic role is resolved from commissioned graph authority per operation; OAuth state is browser-bound and single-use; external audit sinks and capability-health projections are active; allowlisted UI preferences persist in PostgreSQL; calendar versions support honest UI concurrency; task/calendar/control UI operations use the existing governed gateways.
- Evidence: `scripts/validate.sh` passed 166 Python tests, Ruff, strict mypy, and OPA 7/7; frontend unit tests, TypeScript/Vite build, Playwright 9-test responsive matrix, package build, repeat migrations, commissioned-runtime target, final-UX target, screenshot capture/MIME checks, diff-check, and public-safety review passed.
- Final governed checkpoint: this governance closure commit, pushed after the implementation checkpoint and exact implementation CI. Its exact SHA and hosted CI are recorded in the final Notion readback; the closure files avoid a self-referential hash claim.
- Verdict: `COMPLETE — PENDING ARCHITECT ACCEPTANCE`. Evidence limits remain live HA commissioning, physical-home behavior, live Luna credentials, native ARM64/Pi execution, production TLS, and real household data. Phase 13 was not implemented.

## ANIMA-HA-P12-VERIFIED-UX-E2E-CLOSURE-014H4 — H4 verified UX/E2E closure

- Starting governed SHA: `a059898be1c9e85291cf73fd7bde912ad6c3c7c2`; starting CI `33672285860` passed.
- Implementation sequence: `02a958590f8c1c1dab38b1143af12c9fea6033cc`, `a4b0c40b084f9dfbd127b43bd80e84c45977ab0d`, `94f665fd6a4bbc2246124bb5df06d81bdb2fb987`, `22c1af9a01d7db02abfdc4ef788222f9783c8c53`, and `9e12f6e295b52ec382c1952a21a1a95287100740`; implementation CI `33686351783` passed on the exact final implementation head.
- Result: browser Home controls use `desired_on`; Core projects Phase 9 terminal status; mutation notices wait for refetch; task/calendar/settings UI behavior is real and versioned; the normal Core cognition trace and reused isolated-HA UI-to-Phase9 path pass.
- Hosted CI history required bounded corrections: strict test-double typing, CI PostgreSQL/OPA provisioning, and browser mutation synchronization. The exact current implementation CI and subsequent governed CI are recorded in the final handoff/Notion readback.
- Limitations: the current Playwright matrix does not independently execute browser denial, degraded-provider recovery, restricted-content reload, backend restart/session/SSE recovery, or an isolated-HA browser target. These remain unpromoted evidence limits.
- Verdict: `COMPLETE — PENDING ARCHITECT ACCEPTANCE`; Phase 13 was not implemented.

## ANIMA-HA-P12-BROWSER-ACCEPTANCE-EVIDENCE-CLOSURE-014H5 — H5 continuation

- Starting governed checkpoint: `33440106ea629eda0386a062924e1f84c4b32c14`; current published implementation/evidence head: `800d8cf4a183ce0e7548545182ed09f0687ad98f`.
- Hosted CI `33696481738` passed on the exact current head. It passed H4/H5 Core targets, isolated-HA API verification, restricted-content PostgreSQL scanning, Docker UI health, frontend checks, and Playwright with 11 passed and 10 skipped tests across desktop/tablet/phone.
- H5 added measurable display-mode CSS behavior and deterministic Core/API evidence for external audit redaction, provider degraded/recovery projection, restricted live-only content, and same-session reconstruction. Artifact `9872060277` (`phase12-h5-evidence-800d8cf4a183ce0e7548545182ed09f0687ad98f`) has ZIP digest `33e32d1966462416f27b1fec109cfac7097de2d15dac0f5e8086a580ce31a383`.
- H5 remains `CONTINUE — IMPLEMENTATION/EVIDENCE PARTIAL; PENDING ARCHITECT ACCEPTANCE`: browser-visible denial, provider recovery, restricted-content reload/storage, same-browser restart/SSE, and browser-visible isolated-HA journeys remain not run. Phase 13 was not implemented.

## ANIMA-HA-P12-PRODUCT-SURFACE-ACCEPTANCE-CLOSURE-014H5R — H5R product-surface closure

- Date: 2026-09-03
- Disposition: `IMPLEMENTED_UNVERIFIED / CONTINUE`; Phase 12 remains unaccepted and Phase 13 remains unauthorized.
- Baseline: `fe1833987aeaac60e680fca7035fa3e915ca1d70`.

### Work performed

Reconciled the active Notion H5R replan with local Authority pointers while
preserving the published H5 implementation and evidence. Added a
household-scoped graph place query, Core-owned semantic rooms/devices,
sanitized journal notifications, episode reports, action summaries and
pending-confirmation state, capability-derived health, corrected Activity
rendering, and additive version-2 preference migration/order normalization.

### Acceptance results

- Confirmation contract investigation: `PASSED` for exact action-intent and
  principal binding, expiry, durable challenge storage, single-use consumption,
  and Phase 8 `WAITING_CONFIRMATION` transition.
- Product-surface API/browser target: `PASSED` — 13 focused Python tests and
  one isolated desktop browser journey.
- Broader code regression: `PASSED` — 169 Python tests, Ruff, TypeScript/Vite
  build, and frontend policy tests 3/3.
- Desktop browser regression: `FAILED` one existing calendar lifecycle test in
  a shared development database with 34 historical calendar rows; the create
  request returned HTTP 200 but the bounded first-20 response omitted the new
  row. Seven other desktop tests passed. No destructive cleanup or reseed was
  performed.

### Evidence limits and next gate

New surface evidence is `E3_TARGET_TESTED`; broader regression is
`E4_REGRESSION_PROTECTED`. No live confirmation continuation was added because
the repository has no safe UI/API continuation contract; the UI states that
pending confirmation is unavailable and provides no bypass. Phase 12 still
requires the remaining H5 browser/runtime evidence, a pristine bounded
calendar run, and Architect reconciliation of the confirmation-continuation
decision.

- Resulting implementation SHA: `764c8fac52ddcd565a3f1c3fd46ec8071ae8bcb7`;
  remote `main` was verified at this SHA. No new hosted workflow run was
  associated with this commit (`NOT RUN`).

## ANIMA-HA-P12-BROWSER-ACCEPTANCE-EVIDENCE-CLOSURE-014H5S — decisive evidence closure

- Date: 2026-09-03
- Disposition: `PARTIAL / CONTINUE`; Phase 12 remains unaccepted and Phase 13 remains unauthorized.
- Baseline: `0bc4a1d1826a4f8c874c90ed935587206a2f4935`.
- Reran `verify_phase12_h5_core.py` successfully, including real Core composition, provider degraded/recovery, restricted sentinel absence, session reconstruction, and post-restart durable mutation.
- Reran `verify_phase12_h4_isolated_ha.py` successfully: HTTP → CoreUICommandGateway → Phase 5 → OPA → Phase 9 → isolated HA, with success and deliberate verification failure.
- Browser readback passed on isolated candidate runtime `127.0.0.1:18091` after session recovery: H5R product surfaces and widget settings were visible after reload; the future Voice label was absent.
- Preserved negative evidence: browser-only denial, provider recovery, restricted reload/storage, same-session restart/SSE, isolated-HA UI, pristine calendar, and confirmation continuation remain `NOT RUN`/unproven. Existing calendar lifecycle remains `FAILED` against the dirty shared database's bounded first-20 window; no cleanup/reseed occurred.
- Evidence: new browser/Core targets `E3_TARGET_TESTED`; broader prior regression `E4_REGRESSION_PROTECTED`. No Phase 8 redesign or Phase 13 work was performed.
- Source: H5/H5R packets, current Notion SSOT, and exact repository/GitHub reconciliation.

## ANIMA-HA-P12-BROWSER-ACCEPTANCE-EVIDENCE-CLOSURE-014H5T — same-session restart/SSE closure

- Date: 2026-09-03
- Disposition: `PARTIAL / CONTINUE`; Phase 12 remains unaccepted and Phase 13 remains unauthorized.
- Baseline: `09f1402bdff34a79b0b08b882752c491f89c0959`.
- Same browser tab remained authenticated across real candidate UI process PIDs `1059121` → `1073682`, with no new login or browser context. Post-restart bootstrap, home, settings, and events refetches succeeded; visible light/phone presentation state and H5R surfaces persisted.
- A bounded task mutation attempt returned UI `FAILED / ValueError`; no matching durable task row was found. No duplicate-mutation claim is made. Browser cookie/storage inspection was intentionally not performed.
- Evidence: same-browser restart/refetch `E3_TARGET_TESTED`; no-duplicate mutation remains `NOT RUN`. Candidate runtime was stopped and the pre-existing port-18090 service was preserved.
- Source: H5T packet, browser runtime observations, server PIDs/logs, PostgreSQL read-only check, and current repository/Notion reconciliation.

### H5T evidence amendment — 2026-09-03

- A second real restart sequence used process PIDs `1079567` → `1080604`.
- One bounded settings `PUT` returned visible `SUCCEEDED` before restart; the
  same browser tab remained authenticated afterward and showed the persisted
  `normal` text scale, `phone` display mode, and H5R surfaces. Logs show one
  settings PUT and post-restart refetches, with no duplicate settings PUT.
- Live SSE event delivery and durable-task duplicate accounting remain
  unproven. The final H5T disposition remains `PARTIAL / CONTINUE`.

## ANIMA-HA-P12-CONFIRMATION-CONTINUATION-FINAL-ACCEPTANCE-014H5U — implementation and local evidence

- Date: 2026-09-03
- Starting SHA: `684806ae53832ddd40cd0ee000ffbe35609a8ff2`.
- Disposition: `CONTINUE — FINAL PHASE 12 CORRECTNESS CLOSURE`; Phase 12 is not accepted and Phase 13 remains unauthorized.
- Implemented: durable PostgreSQL pending approvals, exact-intent preservation, same-episode AgentRuntime continuation, authenticated UI approval/rejection, and the PostgreSQL H5U verifier. Pending payloads omit executable arguments; the bounded server envelope is retained only to reconstruct the exact trusted request.
- Focused evidence passed: exact-intent confirmation, rejection, expiry, wrong-principal rejection, single-use replay rejection, same-episode continuation without tool replay, and one-provider-call PostgreSQL approval.
- Broader local evidence passed: `uv sync --locked --dev`, `scripts/validate.sh` (172 tests, Ruff, strict mypy, OPA 7/7), migrations initial/repeat, H4/H5 Core, isolated-HA API, restricted-content, frontend checks/build, and a clean-filesystem Playwright reproduction (12 executed passes plus 12 responsive skips by design).
- Historical H5T `FAILED / ValueError` task evidence is preserved; current H5 Core task mutation passes after the bounded correction. No Phase 13 behavior was implemented.
- Publication and hosted exact-head CI passed; the result is handed to the Architect with Phase 12 still pending acceptance.

### H5U publication readback — 2026-09-03

- Implementation checkpoint `dbb4720882b25ad1d840c2c270191227f0c4ea1d` was
  pushed and passed hosted CI `33746353829` on the exact SHA.
- Final governed checkpoint `b2049f306416a1d0cd4f61cd370d0686c5bec2d7` was
  pushed and passed hosted CI `33747181905` on the exact SHA. Remote `main`
  resolves to that checkpoint and the tree was clean at verification.
- H5U is complete as a bounded implementation/evidence work unit;
  Phase 12 remains `COMPLETE — PENDING ARCHITECT ACCEPTANCE`. Phase 13 was not
  implemented.

## ANIMA-HA-P12-TRUE-AGENT-RESUME-INTEGRATED-ACCEPTANCE-014H5V — implementation and local evidence

- Date: 2026-09-03
- Starting checkpoint: `a94bd3cbe27922088bbb24256f548e2605a71bcd`; H5U final hosted CI `33747792370` passed on that exact head.
- Disposition: `CONTINUE`; Phase 12 remains unaccepted and Phase 13 remains unauthorized.
- Implemented: append-only `anima_agent_continuations` persistence; durable episode context/transcript loading; same-episode AgentRuntime continuation after approval or rejection; normalized action/approval/verification evidence; UI confirmation routing through the continuation; real-OPA PostgreSQL verifier wiring.
- Focused evidence passed: approval gives two model turns, one provider dispatch, `SUCCEEDED`, provider execution context, and one durable continuation record; rejection gives two model turns, zero provider dispatch, `POLICY_DENIED`, and one durable continuation record. Both preserve the original episode ID and transcript continuity without replaying the original model tool request.
- Local migration, Ruff, strict mypy, focused agent/action tests, and `scripts/verify_phase12_h5v_true_resume.py` passed. The verifier uses a real PostgreSQL journal → attention → trigger → context chain, PostgreSQL episode/action/approval stores, and real OPA.
- Remaining evidence: dedicated Phase 12 browser confirmation/restart/SSE and broader acceptance matrix. The implementation checkpoint and its exact-head hosted CI are published; this record does not self-accept Phase 12.

## ANIMA-HA-P12-TRUE-AGENT-RESUME-INTEGRATED-ACCEPTANCE-014H5V-R1 — bounded continuation hardening

- Date: 2026-09-03
- Architect disposition: `CONTINUE`; Phase 12 remains unaccepted and Phase 13 remains unauthorized.
- Starting checkpoint: `761f6214993a676bdd43f911e237dffbbee7a684`.
- Implementation checkpoint: `8bcff850a56b0bd8b3a70cc4d837e1268e12716f`.
- CI isolation checkpoint: `58636eaec87a9ad4ddd0958b916a4d74b2d9fe74`; hosted CI `33818551425` passed on the exact SHA. Artifact `9917602062` was published with digest `sha256:257886d0b85f485bc2b103cdfc55b159618a00bb6c72f46f14f8b0352237464b`.
- Implemented: durable continuation lifecycle/fencing/reclaim, pre-dispatch context/transcript/catalogue/runtime preflight, cumulative active-runtime accounting, exact approval policy-intent propagation, dedicated task/calendar projections, and test-only browser approval/rejection coverage.
- Fresh evidence: 174 Python tests, Ruff, strict mypy, OPA 7/7, migrations, package build, frontend check/test/Vite build, 24 existing browser checks (12 executed and 12 intentional responsive skips), 2/2 dedicated H5V browser journeys, H5V PostgreSQL/OPA true-resume verifier, H5 Core verifier, diff-check, and public-safety scan passed.
- Remaining evidence limits: browser denial/strong-auth, provider recovery, restricted browser lifecycle/storage, same-browser process restart/SSE, dirty task/calendar fixture, complete crash/concurrency accounting, and browser-visible isolated-HA outcomes remain unproven. This is an implementation/evidence checkpoint, not a Phase 12 acceptance claim.

## ANIMA-HA-P13-SENTRY-READY-INTELLIGENCE-PLATFORM-015B — ANIMA boundary slice

- Date: 2026-09-04.
- Disposition: implementation in progress; no Phase 13 acceptance claim.
- Implemented the durable intelligence request/result schema, fenced
  PostgreSQL claims, Attention-to-SENTRY queue pump, Core-owned SENTRY
  boundary, stdio MCP transport, explicit bridge entry point, and installable
  SENTRY compatibility bundle. The existing HA adapter remains the only HA
  integration and all consequential tools still route through Phase 9.
- Fresh local evidence: full pytest passed; Ruff and strict mypy passed;
  migration `0019` applied once and was idempotent on repeat; a live local
  PostgreSQL request completed enqueue → claim → provider-running → bounded
  result; direct sentry-mode composition returned a SentryConversationPipeline
  and available Core boundary.
- The dirty SENTRY V0.4 working tree was not modified. Live SENTRY claim,
  voice broadcast, and physical-household mutation remain unclaimed pending
  host commissioning and compatibility validation. Phase 14/15 remain
  unauthorized.

## ANIMA-HA-P13-HA-DEVICE-CONTROL — bounded UI onboarding slice

- Date: 2026-09-04.
- Disposition: implementation in progress under the Phase 13 SENTRY-ready
  platform transition; no Phase 13 acceptance claim.
- Implemented a Devices view and authenticated API routes for bounded ZHA
  pairing, HA registry refresh, and commissioning a present discovered device
  into an existing ANIMA room. The plugin derives canonical resource,
  capability, provider-reference, and Truth-binding records from the registry.
- `refresh_inventory` is read-only. Pairing and commissioning are Core-owned
  policy-gated capabilities of the trusted built-in HA plugin; the browser
  cannot choose a host, raw HA service, entity target, credential, relationship,
  or arbitrary configuration payload. Existing `desired_on` semantic power
  controls remain Phase 5/4/9 verified actions.
- Focused and full Python tests passed, as did the frontend TypeScript check
  and Vite production build. Physical pairing and real-household behavior are
  not claimed until the existing isolated HA evidence path is run with the
  operator-commissioned instance.

## ANIMA-HA-P13-SENTRY-BOUNDARY-HARDENING-LIVE-COMMISSIONING-015B-R1 — boundary hardening

- Date: 2026-09-04; starting governed checkpoint: `8ee91b3ffa4af28a1dc6bb3d1bf0f0a41b90f5c9` (hosted CI `33919471594` passed).
- Disposition: bounded implementation in progress; no Phase 13 acceptance claim.
- Implemented locally: ANIMA-owned Unix-socket Core service, client-only `anima-household` bundle, private credential-file checks and rotation, server-issued request/household/provider/fencing bindings, provider-scoped claiming, no-blind-replay handling for possible provider dispatch, request-bound catalogue enforcement, current HA child-device/config-entry metadata, and typed SenseGuard alert-policy storage/matching.
- Fresh local evidence: full pytest, Ruff, strict mypy, focused boundary, current HA registry, and SenseGuard policy tests pass. The protected dirty SENTRY V0.4 tree was not modified.
- Evidence limits: no live SENTRY host turn, physical SenseGuard trigger, voice broadcast, or live household action is claimed. Phase 14/15 remain unauthorized.
