# Outcome Ledger

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
