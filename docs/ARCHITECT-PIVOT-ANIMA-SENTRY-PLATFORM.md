# Architect Report: ANIMA HA → SENTRY Intelligence Platform Pivot

**Date:** 2026-09-04
**Audience:** AI Architect / project authority
**Repository:** `SketchOTP/ANIMA-Home-Automation`
**Status:** Direction adopted; Phase 13 R1 implementation is published and remains pending live SENTRY/physical qualification and Architect acceptance.

## Executive decision summary

ANIMA HA has pivoted from being a standalone household assistant with its own primary conversational intelligence and voice path into the household platform and trusted execution substrate for SENTRY.

The intended production composition is now:

```text
SENTRY = the sole production intelligence, persona, voice, interaction and planning layer
ANIMA  = the household system of record, authority boundary and verified control plane
HA     = an underlying home-automation provider integrated through ANIMA
```

This is not a replacement of ANIMA's accepted architecture. It is a change in which system supplies production intelligence and user interaction. The accepted ANIMA capabilities remain the foundation: event capture, Truth, Household Graph, memory, Attention, Context Broker, identity evidence, policy, typed tools, action coordination, observation/verification, durable tasks, calendar, external providers, UI, audit, health, replay, backup and recovery.

The goal is to make SENTRY the user-facing way to operate the home so the user does not need to use the Home Assistant interface for ordinary operation or configuration. SENTRY can request the full set of household capabilities registered by ANIMA, including device setup, automations, triggers, alerts, notifications and other supported Home Assistant operations. Those requests still cross the ANIMA boundary and are executed through the existing typed, audited and observed paths.

The key rule is:

> SENTRY decides intent and proposes an operation. ANIMA decides authorization, performs the operation, observes the resulting state and reports the actual terminal result.

“Full access” therefore means complete access to the commissioned and registered household capability surface through ANIMA, not a raw SENTRY-to-Home-Assistant bypass or an untracked Codex shell escape. This preserves safety, provenance, auditability and truthful state while allowing SENTRY to be the practical household interface.

## 1. Direction before the pivot

The original ANIMA direction treated ANIMA itself as the complete assistant surface. The project progressively built:

- a PostgreSQL-backed event journal and deterministic Truth projection;
- a canonical Household Graph and memory model;
- identity and assurance aggregation;
- OPA policy and confirmation semantics;
- a typed Tool Gateway;
- coordinated action execution with PostgreSQL advisory locks, idempotency, preconditions and post-action verification;
- durable tasks and scheduled cognition;
- bounded external providers and restricted-content handling;
- a local React/FastAPI household interface;
- an embedded AgentRuntime using the qualified Luna/Codex path as its model-facing implementation.

That work established a strong household control plane, but it also created a strategic risk: ANIMA and SENTRY could evolve into two competing intelligence surfaces. The user already has SENTRY as the preferred voice, desktop and general assistant environment, with existing PC/office capabilities and an ongoing personal-continuity implementation. Duplicating persona, memory, conversation, voice and planning in ANIMA would create two brains, two interaction surfaces and potentially two sources of intent.

## 2. Why the project direction changed

The pivot resolves that duplication directly.

SENTRY is the natural production interaction layer because it already owns the user's preferred voice and desktop experience. ANIMA is the stronger location for household authority because it already owns the normalized HA state, household identity, Truth, Graph, policy, execution and verification contracts.

The combined design gives each system one clear job:

- SENTRY handles the human relationship and intelligence loop.
- ANIMA handles the household reality and authority loop.
- Home Assistant remains a provider and device system, not a second assistant interface.

This is a convergence of responsibilities, not a broad rewrite. It avoids introducing another broker, database, agent runtime, provider architecture or direct control path.

## 3. Revised project goal

The revised goal is to deliver a local-first household platform in which a user can interact with SENTRY and have SENTRY operate the home through ANIMA without needing to open Home Assistant.

In practical terms, the target experience is:

1. Home Assistant emits a state change, device event or alert.
2. ANIMA captures and normalizes it into the Event Journal, Truth and Graph.
3. Attention determines whether the event requires durable reasoning work.
4. ANIMA creates a bounded intelligence request for SENTRY.
5. SENTRY claims the request, receives sparse authorized context and chooses a semantic operation when appropriate.
6. ANIMA validates policy, executes through the correct provider boundary and verifies the result.
7. SENTRY receives the factual result and communicates it through its native UI or voice path.

For a user-originated request, the direction is reversed at the interaction edge but not at the authority edge:

```text
User voice/UI → SENTRY cognition → ANIMA typed boundary → policy → execution
             → fresh observation/verification → ANIMA terminal result → SENTRY response
```

The end-state is not “ANIMA becomes a voice assistant.” The end-state is “ANIMA makes SENTRY a trustworthy whole-home assistant.”

## 4. Ownership model

### ANIMA owns

- Home Assistant connectivity, device/entity discovery and event ingestion.
- Canonical household identity, resource references and semantic roles.
- Event Journal, Truth projection and Household Graph.
- Governed household memory and provenance.
- Attention, guaranteed event delivery and Context Broker assembly.
- Identity evidence, assurance and current authorization context.
- Registered capability catalogue and typed tool schemas.
- Phase 4 deterministic policy, confirmation and stronger-auth requirements.
- Phase 5 Tool Gateway validation and invocation boundary.
- Phase 9 action execution, concurrency, idempotency, preconditions, verification and recovery posture.
- Phase 10 durable tasks, scheduled-reasoning events and local calendar.
- Phase 11 bounded external providers and external-content trust classification.
- Household UI, audit projections, capability health, replay and backup/recovery surfaces.
- The final decision about whether an operation may execute and what actually happened.

### SENTRY owns

- Assistant identity, personality and natural interaction.
- Persistent Codex/Luna cognition and reasoning.
- Planning, decomposition and semantic tool selection.
- Natural-language responses and follow-up conversation.
- Wake word, microphone/VAD/STT/TTS and room-aware voice interaction when separately commissioned.
- Native GTK/orb/desktop interaction and office-room perception.
- Existing SENTRY PC, office and general-assistant capabilities within the SENTRY project.
- Presenting ANIMA's factual terminal results to the user.

### Home Assistant owns

- Device/provider integration and low-level home-automation state.
- The HA UI and native provider configuration surfaces where commissioning still requires them.

ANIMA is the authoritative household layer between HA and SENTRY. SENTRY does not become a second HA client with its own device model.

## 5. Non-negotiable authority boundary

SENTRY is intentionally powerful as an intelligence and interaction layer, but it cannot manufacture authority. It cannot:

- mint or alter household identity evidence;
- write Truth or canonical Graph state directly;
- bypass OPA or confirmation requirements;
- invent provider success or physical success;
- call Home Assistant directly;
- write ANIMA SQL directly;
- access raw household credentials;
- choose arbitrary hosts, providers or network destinations;
- create a second household persistence model;
- turn historical creator identity into current authentication.

ANIMA must reject, require confirmation for, require stronger authentication for or execute a requested operation according to the current deterministic policy and execution contract. SENTRY receives the result as evidence and must communicate uncertainty honestly.

This preserves the user's intended “SENTRY can do what I ask” experience while preventing an LLM-generated instruction from becoming unreviewed household authority.

## 6. Target signal and control flows

### HA-originated event or alert

```text
SenseGuard / HA device / HA event
        ↓
ANIMA HA adapter
        ↓
Phase 1 normalization and Truth projection
        ↓
Event Journal
        ↓
Attention and guaranteed-event handling
        ↓
Context Broker creates sparse ContextPacket
        ↓
Durable IntelligenceRequest
        ↓
SENTRY claims through ANIMA-owned MCP boundary
        ↓
SENTRY reasons and selects a registered semantic operation
        ↓
ANIMA Tool Gateway → OPA → Phase 9 when consequential
        ↓
HA/provider execution and fresh observation
        ↓
ANIMA terminal result and audit evidence
        ↓
SENTRY voice/UI notification and follow-up handling
```

For the paired devices already commissioned in HA, the intended names are `SenseGuard Kitchen` and `SenseGuard Basement`. Their HA events enter ANIMA first. A future overnight alert policy can use the recorded event time, household timezone, device semantic role and current user preferences to determine whether SENTRY should be interrupted. That behavior requires end-to-end host/voice qualification; it is not claimed merely because the ingestion boundary exists.

### Direct SENTRY request

```text
User speaks/types to SENTRY
        ↓
SENTRY intent, reasoning and tool selection
        ↓
ANIMA Core SENTRY boundary
        ↓
Sparse context/catalogue validation
        ↓
Phase 5 Tool Gateway
        ↓
Phase 4 OPA and current identity evidence
        ↓
Phase 9 coordinator for physical/external consequential work
        ↓
Provider call, observation and verification
        ↓
Structured ANIMA result
        ↓
SENTRY response
```

### Durable future cognition

```text
ANIMA durable task
        ↓
scheduled_reasoning_due
        ↓
fresh due-time ContextPacket
        ↓
new SENTRY intelligence request/episode
        ↓
current identity, policy and Truth evaluation
        ↓
optional semantic operation through ANIMA
```

The future episode must not replay stale action authority, reuse a creation-time context packet or treat the task creator's old identity as current authentication.

## 7. What is implemented on the ANIMA side

The current ANIMA SENTRY-ready checkpoint at `57779449a90375e1fb3853019ee380506690a6cb` contains the initial durable integration boundary.

### Durable intelligence handoff

`src/anima_ha/intelligence.py` adds:

- `IntelligenceRequest` and `IntelligenceResult` contracts;
- provider modes for `sentry`, `embedded_reference` and `unavailable`;
- origins for direct UI, Attention, durable tasks, approval resolution and testing;
- PostgreSQL request storage and append-only lifecycle transitions;
- deterministic request identity and idempotency;
- claims, leases, renewal and fencing;
- bounded context, catalogue, result and provider-health metadata;
- an `IntelligenceRequestFactory`;
- an Attention-to-SENTRY bridge and health events.

### Core-owned SENTRY boundary

`src/anima_ha/sentry_boundary.py` provides:

- boundary health;
- durable request claim and renewal;
- sparse ContextPacket retrieval;
- registered semantic tool catalogue access;
- nonconsequential tool invocation through the PluginManager/Phase 5 path;
- consequential action conversion into the existing `ActionRequest` and Phase 9 coordinator;
- structured terminal-result submission;
- bounded provider invocation evidence.

The boundary does not expose SQL, raw HA calls, raw HTTP, shell, secrets, policy editing or arbitrary provider access.

### ANIMA-owned SENTRY MCP surface

`src/anima_ha/sentry_mcp.py` and `integrations/sentry/anima-core/` provide the `anima-sentry-core` stdio MCP package with operations for:

- health;
- claiming intelligence requests;
- retrieving bounded intelligence context;
- listing registered tools;
- invoking a registered semantic tool;
- submitting a structured intelligence result.

The MCP surface is a transport/interface boundary, not a second authority system.

### Attention bridge and UI composition

`src/anima_ha/sentry_bridge.py` provides the explicit Attention pump. `src/anima_ha/ui_runtime.py` provides `SentryConversationPipeline` and composes direct UI requests into the same Journal → Attention → Context Broker → durable SENTRY request path when SENTRY mode is selected.

The composition root supports `ANIMA_INTELLIGENCE_PROVIDER=sentry`. The prior embedded AgentRuntime remains available as a reference/test provider, but the intended production mode has exactly one active intelligence provider: SENTRY.

### Home Assistant event foundation

The existing HA adapter remains the only ANIMA-to-HA integration. It normalizes commissioned HA state and events into ANIMA Truth and the Event Journal. The SenseGuard devices are therefore part of the same household event foundation rather than being connected directly to SENTRY.

### Follow-up transport correction

The latest local fix derives HA WebSocket TLS from the configured `ws://` or `wss://` scheme. This preserves the configured local HA transport without hard-coding an incompatible secure/insecure mode.

## 8. What remains intentionally preserved

The pivot does not authorize a rewrite of the accepted phases.

- Phases 0–12 remain the accepted ANIMA platform baseline in the current authority record.
- PostgreSQL remains the durable state and coordination substrate.
- OPA remains the deterministic policy evaluator.
- The Tool Gateway remains the common invocation boundary.
- Phase 9 remains mandatory for physical/provider consequential actions.
- Phase 10 remains the durable task/scheduled-cognition substrate.
- Phase 11 remains the bounded provider portfolio: Open-Meteo, private SearXNG, OSM Overpass, TheMealDB, UPCitemdb, local PostgreSQL calendar and ntfy.
- Restricted external content remains untrusted and ephemeral/restricted according to its existing classification.
- The ANIMA UI remains a Core client and operational control panel, not a second intelligence persona.
- The existing SENTRY feature branch remains separate and dirty; ANIMA work has not modified, reset, cleaned, rebased or merged it.

## 9. Current evidence status

### Observed/implemented on the ANIMA side

- Current ANIMA `main` equals `origin/main` at `57779449a90375e1fb3853019ee380506690a6cb`.
- The initial SENTRY boundary checkpoint `0ab99ce682596b89babb1d8eb6fff7bfba2ef9e2` was pushed and passed hosted CI `33909922639`.
- The follow-up transport fix is included in `57779449a...` and passed hosted CI `33910453977` on the exact SHA.
- Full local Python validation passed with 174 tests.
- Ruff format/check passed.
- Strict mypy passed.
- Migration repeat was clean.
- Direct SENTRY-mode composition selected `SentryConversationPipeline`, reported an available Core boundary and exposed 17 registered tools.
- A local PostgreSQL intelligence lifecycle smoke passed enqueue → claim → delivered → provider running → bounded result → completed.
- Public-safety scanning found no committed credentials, private keys or runtime-state material in the new SENTRY boundary.
- The repository contains explicit installable SENTRY MCP and bridge entry points.

### Proven only as deterministic or local integration evidence

- ANIMA can create and persist a durable intelligence request.
- ANIMA can expose bounded context and a registered catalogue through the Core boundary.
- ANIMA can translate a consequential SENTRY request into the accepted Phase 9 action path.
- Direct UI requests can be routed into the durable SENTRY queue in SENTRY provider mode.
- HA WebSocket scheme handling is corrected for the configured local transport.

### Not yet proven and therefore not claimed

The following are the next evidence obligations, not completed capabilities:

- a live SENTRY host process claiming a real ANIMA request;
- a representative Codex/Luna SENTRY model turn using the ANIMA MCP surface;
- a real SenseGuard event becoming a SENTRY reasoning request;
- SENTRY deciding to notify the user from a real SenseGuard event;
- actual voice/STT/TTS/interruption delivery from the SENTRY host;
- a live SENTRY-initiated physical mutation through ANIMA and isolated or physical HA;
- full device setup/automation creation/configuration through the SENTRY path;
- outage, crash, duplicate-claim, backup/restore and restart qualification at the integrated boundary;
- native ARM64/Raspberry Pi operation;
- physical household commissioning;
- production TLS/remote access;
- human notification delivery/read confirmation.

The distinction is important: the platform boundary is implemented, but “fully intertwined and in sync” is a final integration demonstration claim that requires host-level SENTRY and end-to-end HA evidence.

## 10. SENTRY integration contract

The SENTRY side should consume ANIMA through the checked-in `integrations/sentry/anima-core` bundle or an equivalent explicit Core client. It should not import ANIMA internals or implement a parallel HA adapter.

The expected SENTRY behavior is:

1. Check ANIMA boundary health.
2. Claim a durable intelligence request using the assigned worker identity.
3. Retrieve only the sparse context and registered catalogue supplied by ANIMA.
4. Reason about the user's or household's request.
5. Select a semantic registered operation, not a raw HA service or arbitrary command.
6. Submit the operation to ANIMA.
7. Treat the returned ANIMA result as authoritative for household state.
8. Submit the bounded reasoning response/result back to ANIMA.
9. Speak or display the response through SENTRY's own interaction layer.

SENTRY may retain its own assistant/personality continuity according to its own authority, but it must not duplicate ANIMA's household Truth, Graph, event journal or physical-action ledger.

## 11. Operational model for the SenseGuards

The two paired devices are a concrete example of the new division of labor:

```text
SenseGuard event in HA
→ ANIMA HA adapter
→ normalized event + Truth + Journal
→ Attention policy and user-preference evaluation
→ durable SENTRY request when intervention is warranted
→ SENTRY decides how to communicate
→ ANIMA verifies any requested follow-up action
```

For an overnight preference such as “notify me immediately for either guard between 12:00 AM and 5:00 AM Eastern,” the authoritative implementation must use:

- the event's recorded timestamp and configured household timezone;
- the canonical SenseGuard resource/role;
- the current user preference record;
- current identity and notification policy;
- the normalized observed HA state;
- a durable audit trail of the decision and delivery attempt.

SENTRY should then communicate a factual statement such as “SenseGuard Basement detected an event at 1:03 AM,” including uncertainty if the provider state is unavailable or the event is ambiguous. A follow-up question such as “is it still tripped?” must cause SENTRY to request a fresh ANIMA read, not reuse the previous alert payload as current state.

The alerting example is the target behavior. It is not yet a live acceptance result.

## 12. Explicit boundary around Codex CLI

SENTRY may use its existing Codex/PC capabilities for software work, office tasks and other capabilities already owned by the SENTRY project. The ANIMA household path should not grant a general raw shell or arbitrary code-execution tool merely because the user says “do anything.”

For household operations, the correct mechanism is capability completeness through ANIMA's registered semantic catalogue. If a requested HA capability does not yet have a safe semantic tool, that is a commissioning/implementation gap to be handled explicitly; it should not be solved by bypassing the household authority boundary.

This keeps the user experience broad while preserving:

- exact provenance;
- current policy;
- confirmation and stronger-auth semantics;
- provider isolation;
- action idempotency;
- observation-first verification;
- restart and recovery behavior;
- auditable results.

## 13. Revised roadmap

### Phase 13 — SENTRY-ready intelligence platform

The active phase builds and validates the replaceable intelligence-provider contract, durable request/result bridge, Attention delivery, ANIMA Core service boundary, SENTRY MCP/plugin package, identity/provenance translation, provider-routed UI and deployment compatibility. The R1 increment publishes the credential-isolated client/service split, replay fencing, request-bound catalogues, direct-interaction binding, current HA registry metadata, and a typed SenseGuard policy. Real SENTRY host execution, physical SenseGuard triggering, and live household action remain qualification gates.

The current ANIMA implementation is in this phase. It is not self-accepted.

### Phase 14 — integrated resilience

After the SENTRY-ready boundary is accepted, the next phase should qualify the combined system under restart, crash, ambiguous model work, duplicate claims, concurrency, SENTRY/provider/HA outages, restricted content, backup/restore and ARM64/Pi-class operation where practical.

### Phase 15 — SENTRY-operated demonstration and goal completion

The final demonstration phase should run representative integrated sample-household scenarios with SENTRY as the only active production intelligence provider, including real or explicitly qualified Codex/Luna turns, SenseGuard-driven alerting, follow-up state queries, governed home actions and deterministic replay. Only then should the project consider the broader `ANIMA_HA_PROTOTYPE_GOAL_COMPLETE` marker.

No Phase 14 or Phase 15 behavior is authorized by this report.

## 14. Decisions requested from the AI Architect

The Architect should explicitly confirm:

1. The platform pivot is the governing direction: SENTRY is the sole production intelligence/voice layer and ANIMA is the household authority/control plane.
2. The embedded ANIMA AgentRuntime remains reference/test-only after SENTRY production commissioning; there is no dual production brain.
3. SENTRY may request the full registered ANIMA household capability catalogue, including HA configuration operations as they are semantically commissioned, while ANIMA remains the final authority.
4. The current ANIMA checkpoint and durable boundary are sufficient to continue Phase 13 compatibility/host commissioning work.
5. Live SENTRY host claiming, SenseGuard alert delivery, voice interaction and representative physical-action evidence are the next qualification gates.
6. Phase 14 and Phase 15 remain blocked until Phase 13 is independently accepted.
7. The prior standalone ANIMA voice directive is superseded before implementation and should not be restarted as a competing intelligence path.

## 15. Current repository and external-project boundary

### ANIMA

- Branch: `main`
- Current HEAD: `57779449a90375e1fb3853019ee380506690a6cb`
- Remote: `origin/main` at the same SHA
- Latest hosted CI: `33910453977` — success on the exact current SHA
- Initial SENTRY checkpoint: `0ab99ce682596b89babb1d8eb6fff7bfba2ef9e2`
- Initial SENTRY checkpoint CI: `33909922639` — success

### SENTRY

- Qualified public baseline: `970d1cf5f4df749d5d0844a19d5d392012ced910`
- Qualified baseline CI: `33700343412`
- Current local feature branch: `feature/v0.4-personal-continuity`
- Current local SENTRY state is dirty and unpublished.
- ANIMA has not modified, reset, cleaned, rebased, merged or published that dirty SENTRY state.
- Compatibility work must continue against a temporary clean checkout of the qualified baseline until the SENTRY owner publishes the feature branch.

No SENTRY credentials, HA tokens, private keys, household secrets or private runtime artifacts are included in this report.

## 16. Evidence classification

| Claim | Classification | Meaning |
|---|---|---|
| ANIMA owns the household authority boundary | IMPLEMENTED / DOCUMENTED | Code and current authority records define the boundary. |
| Durable SENTRY request/result contract exists | IMPLEMENTED / TESTED | PostgreSQL lifecycle and focused tests pass locally. |
| SENTRY MCP boundary exists | IMPLEMENTED / TESTED | The checked-in package exposes bounded Core operations. |
| SENTRY mode composes in ANIMA | OBSERVED / DETERMINISTIC | Local composition selected the SENTRY pipeline and exposed the catalogue. |
| ANIMA receives HA events including SenseGuards | IMPLEMENTED / EXISTING HA EVIDENCE | The existing HA adapter owns normalization; live SENTRY delivery is separate. |
| SENTRY can operate the whole home | TARGET / PARTIALLY IMPLEMENTED | Capability path exists; full host-level capability coverage is not demonstrated. |
| SenseGuard alerts can interrupt SENTRY voice | TARGET / UNKNOWN | Preference and event architecture support the scenario, but live voice evidence is absent. |
| SENTRY can ask ANIMA whether a guard is still tripped | TARGET / ARCHITECTURALLY SUPPORTED | It must use a fresh ANIMA read; live follow-up evidence is absent. |
| Physical HA control through SENTRY is complete | UNKNOWN / NOT YET PROVEN | Requires representative host and isolated/physical HA evidence. |
| Phase 13 is accepted | NO | R1 implementation is published; live SENTRY/physical evidence and Architect review remain pending. |
| Phase 14/15 are authorized | NO | They remain future blocked scopes. |

## Final statement

The project has moved from “build an assistant inside ANIMA” to “make ANIMA the trusted household operating substrate for SENTRY.” The pivot is intentional, bounded and consistent with the existing implementation: SENTRY supplies intelligence and interaction; ANIMA supplies household truth, policy, execution and verification; Home Assistant remains the provider system.

The shortest defensible next step is not another assistant architecture. It is to validate the existing ANIMA/SENTRY boundary on the real SENTRY host with the commissioned HA installation, beginning with durable request claiming, a SenseGuard event, a representative SENTRY reasoning turn, a factual notification/follow-up, and one low-risk governed action. Until that evidence exists, the correct status is **SENTRY-ready platform implemented in ANIMA; live integrated operation pending qualification**.

## R4 runtime compatibility certification — 2026-09-05

The R4 bounded increment qualifies the client-only `anima-household` package
through the installed MCP runtime. MCP 2.1.1/Python 3.12.3 evidence passes
initialize, `tools/list`, schemas, direct and queued request paths,
provider-start ordering, semantic read, governed mutation, result submission,
and terminal status. Codex CLI `0.153.1` also loaded the package and completed
an `anima_health` call in a disposable shadow profile without ANIMA
credentials.

The phase remains `CONTINUE`: the protected SENTRY V0.4 `sentry-office`
launcher exits before initialization because it resolves
`SENTRY/integrations/tools/sentry_mcp_server.py` while the server is at
`SENTRY/tools/sentry_mcp_server.py`. The protected SENTRY tree was not changed;
fixing this sibling-runtime defect requires an Architect-authorized SENTRY-side
change. Phase 14/15 and ANIMA voice remain unauthorized.
