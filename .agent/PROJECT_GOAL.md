# Project Goal — ANIMA HA (Home Automation)

## Lifecycle

* Status: `ADOPTED`
* Last verified: `2026-08-28`
* Completion marker: `ANIMA_HA_PROTOTYPE_GOAL_COMPLETE`

## Goal

Build and evidence a complete working prototype of **ANIMA HA**, whose user-facing household intelligence is **Anima**: a modular, event-driven, whole-home AI operating layer that uses Home Assistant as the household substrate, Luna 5.6 with medium reasoning as the primary cloud cognition model, and a local-first / external-by-intent architecture.

At goal complete, Anima must behave as one coherent household intelligence rather than a collection of scripted automations. Meaningful local events and natural-language requests wake the agent; a context broker supplies only relevant household state, memory, permissions, and available capabilities; Anima independently decides what the situation means, whether more information is needed, which tools to use, whether to act, speak, notify, research, schedule work, or do nothing; and all consequential actions are constrained by deterministic policy and verified against current truth where applicable.

The prototype must integrate the complete software architecture required for this behavior: Home Assistant integration, event attention and journaling, canonical truth/state, household graph, provenance-aware memory, identity/authority context, agent runtime, tool/capability registry, deterministic policy enforcement, modular plugins/MCP capabilities, durable tasks, external research and everyday-assistance tools, custom local interface, voice software path, observability/audit, failure recovery, and deterministic simulation/replay testing.

The project is complete only when these capabilities operate together as one demonstrable system and the required evidence shows that the architecture remains correct under normal operation, stale or unknown state, duplicate events, concurrency, partial failure, restart, cloud loss, unsafe requests, malicious external content, and plugin failure.

This goal is a **working prototype boundary**, not a production release, public deployment, or completed commercial installation platform.

## Observable success measures

* A documented ANIMA HA stack can be installed and started from a clean supported development/target environment without undocumented manual reconstruction.
* The software is suitable for a Raspberry Pi 5-class controller and remains portable across ARM64 and x86-64; foundational dependencies have documented license, resource, restart/recovery, maintenance, failure-mode, and replacement-path qualification.
* Home Assistant is integrated through a replaceable adapter that can ingest household entities/events, expose normalized state and actions, and support verification of consequential actions without leaking HA-specific implementation details through the core architecture.
* The local event/attention layer converts raw household activity into durable normalized events, handles deduplication/correlation, preserves guaranteed-delivery classes for important events, and wakes Luna only for selected meaningful events rather than continuously streaming household telemetry to the LLM.
* A canonical Truth/State Service represents direct, inferred, stale, unknown, unavailable, and conflicting state with timestamps, source, confidence/provenance, and version/freshness semantics; Anima does not treat stale or unknown information as current truth.
* A Household Graph represents people, roles, rooms, zones, entrances, devices, sensors, cameras, vehicles, pets, and relevant relationships so cognition operates on household semantics rather than raw entity IDs.
* A provenance-aware Memory Service supports explicit preferences, authoritative facts, observations, inferred patterns, episodic/temporary context, and bounded agent lessons with source, confidence, precedence, correction, and expiration semantics. Memory cannot silently create authority or override explicit user instruction.
* The Context Broker constructs sparse, relevant reasoning packets from event/request, truth, household graph, memory, permissions, task context, and available tools without dumping the complete home state or memory corpus into Luna.
* Luna 5.6 with medium reasoning can conduct multi-step agentic episodes, select tools dynamically, request additional information, reason over results, produce its own responses/reports, and choose no action when appropriate.
* The Tool Gateway and capability registry expose typed, auditable tools through modular plugins/connectors/MCP while isolating credentials, enforcing schemas, timeouts, rate limits, idempotency, risk classes, resource coordination, and replaceability.
* A deterministic policy/permission layer outside the LLM distinguishes preference from authority and reliably allows, denies, or requires confirmation for actions based on principal, identity strength, resource, action risk, context, and household policy. Anima cannot modify this layer or grant itself privileges.
* No runtime tool gives Anima general shell access, unrestricted filesystem access, arbitrary package installation, source-code modification, self-update capability, permission mutation, policy modification, executable tool creation, or access to raw secrets.
* Consequential household actions follow a re-check → authorize → execute → verify flow where applicable, detect partial failure, and report actual resulting state rather than assuming an API acknowledgement proves physical success.
* Concurrent agent episodes and household events cannot silently fight over the same resource; duplicate events/actions are idempotent and recoverable.
* Durable tasks survive process/controller restart and support future work such as reminders, scheduled research, weather follow-up, and multi-step deferred tasks without depending on an in-memory LLM conversation.
* Plugins can be enabled, disabled, replaced, and failed independently without requiring customer-specific forks of ANIMA Core. A customer capability profile determines which plugins/tools are available.
* The prototype includes usable external-by-intent capabilities for current weather, web research, local-business discovery, shopping/product comparison with cart-level action where feasible, recipes/meal research, calendar/reminder operations, notifications, and other selected day-to-day assistant functions defined in the SSOT.
* External web/tool content is treated as untrusted information, cannot grant authority, cannot alter policy, and cannot cause unrelated household data or secrets to be disclosed. Prompt-injection and untrusted-content boundaries are demonstrably enforced.
* A locally hosted custom ANIMA interface presents household status, relevant people/home information, weather, tasks/events, agent conversation, capability surfaces, and configuration/visibility appropriate to the prototype without exposing raw implementation complexity to the household user.
* The voice software path supports the Anima identity/wake-word architecture, room-aware request routing, STT/TTS service boundaries, and natural-language interaction. Final whole-home microphone/speaker hardware deployment is not required for this goal, but the software path must be demonstrable with supported test/dev audio inputs.
* The system retains authoritative audit records sufficient to reconstruct what event/request occurred, what context was used, which tools/actions were proposed, what policy decided, what executed, what verification observed, and the final outcome without persisting unnecessary sensitive raw data.
* Cloud/model outage degrades cleanly: Home Assistant and local household control/state/event recording continue operating; durable work is retained; unavailable agent/external capabilities fail explicitly and recover without corrupting state or duplicating actions when connectivity returns.
* Core services recover from restart with preserved truth provenance, event journal, memory, permissions, tasks, configuration, and audit continuity. Backup/restore for prototype-critical state is demonstrated.
* A simulation/replay harness can execute representative household histories and failure injections, expose Anima's decisions/tool use/policy outcomes, replay prior scenarios after software/model/plugin changes, and detect regressions.
* Integrated acceptance scenarios demonstrate at minimum: ordinary natural-language home control; event-triggered autonomous reasoning; household departure/secure-home reasoning; safe arrival handling; unusual-nighttime-event reasoning and self-written notification; memory-guided behavior; weather use; web research; local-business research; shopping/cart assistance; recipe assistance; durable scheduling; permission denial/confirmation; duplicate/concurrent/partial-failure behavior; restart/cloud-loss recovery; plugin isolation; and replay.
* `ANIMA_HA_PROTOTYPE_GOAL_COMPLETE` is not declared until phase exit gates and final integrated acceptance evidence agree with the SSOT. A passing unit-test suite alone is insufficient.

## Scope

* ANIMA Core and its stable internal contracts: agent runtime, event attention/bus integration, context broker, truth/state, household graph, memory wrapper, identity/authority context, tool/capability registry, policy interface, durable tasks, plugin manager, audit/observability, and core API.
* Home Assistant as the home/device substrate, including normalized entity/state/event ingestion, tool actions, notifications, and physical-action verification contracts.
* Luna 5.6 with medium reasoning through the supported OpenAI agent/tool stack, wrapped so provider/runtime dependencies remain replaceable where practical.
* Local persistent data, event history, provenance, configuration, tasks, and memory using qualified OSS infrastructure where it materially reduces development effort.
* Modular plugins/connectors and MCP-based capabilities for customer-selectable features.
* Weather, web research, shopping/product research and cart actions where feasible, local-business search, recipes, calendars/reminders, notifications, and representative external services required to prove general household-agent usefulness.
* Custom local tablet/web interface for the integrated household experience.
* Voice software architecture and demonstrable wake-word/STT/TTS/request-routing path.
* Deterministic security and policy enforcement, action verification, concurrency/idempotency, external-content isolation, degraded-mode behavior, restart/recovery, backup/restore, observability, simulation, replay, and failure-injection testing.
* Dependency research and qualification using BUILD / ADOPT / WRAP / DEFER decisions. Mature OSS should be reused when it saves meaningful work without weakening ANIMA's architecture, privacy, reliability, or replacement path.
* Prototype deployment targeting a Raspberry Pi 5-class central Anima Server while preserving software portability to stronger ARM64/x86-64 controllers.
* Documentation, tests, evidence, and Authority/Notion/GitHub checkpoints necessary for a cold-start AI Architect or Codex implementation agent to continue and independently verify progress.

## Non-goals

* Production release, public deployment, app-store release, mass customer rollout, or commercial SLA qualification.
* Final consumer DBA/brand selection, marketing site, sales funnel, billing, subscriptions, licensing platform, installer portal, customer fleet management, remote managed-service infrastructure, or production telemetry fleet.
* Full production cybersecurity certification, formal regulatory/compliance certification, penetration-test program, enterprise IAM, production key-management infrastructure, or production incident-response program beyond what is needed to make the prototype architecture safe and testable.
* Complete whole-home physical hardware installation, final microphone/speaker satellite selection, final enclosure/fabrication, final camera/sensor/lock product catalog, electrical installation procedures, or installer certification. Hardware adapters/interfaces must exist where required, but final deployment hardware is a later program.
* Running the primary Luna-class reasoning model locally. Local processing remains preferred for event attention, household data, state, memory, policy, UI, and other suitable services; cloud cognition is intentional for the prototype.
* Replacing Home Assistant with a custom home-automation platform.
* Building commodity infrastructure from scratch when qualified OSS can solve the problem safely and replaceably.
* Allowing Anima to write/deploy programs, install packages, edit its own source, modify policies/permissions/system instructions, create executable capabilities, self-update, or otherwise self-program.
* Hard-coding the household intelligence as a large collection of `IF event THEN action` automations merely to mimic agency. Deterministic rules remain appropriate for attention filtering, safety, authority, fail-safes, and infrastructure behavior.
* Guaranteeing that every possible retailer, external service, smart-home device, calendar provider, map provider, or customer-specific integration is supported. The prototype must prove the modular architecture using representative integrations.
* Unbounded autonomous purchasing or other irreversible external transactions. High-risk or financially consequential actions must remain policy/confirmation controlled.
* Treating inferred routine, model output, external web content, device acknowledgements, or stale cached data as unquestioned household truth.

## Constraints

* The ANIMA HA Notion SSOT is the normative product/architecture authority. Material deviations require Architect/owner approval and documentation.
* The authorized completion boundary is `ANIMA_HA_PROTOTYPE_GOAL_COMPLETE`; work beyond prototype completion requires a new authorized goal.
* Home Assistant remains the household automation substrate for this goal.
* Primary cognition is Luna 5.6 with medium reasoning effort unless a documented compatibility/availability issue requires an Architect-approved change.
* Core architecture is event-driven cognition: meaningful events wake Anima; event triggers do not hard-code Anima's resulting behavior.
* Continuous raw household telemetry, camera streams, or ambient audio must not be continuously streamed to the cloud LLM.
* Local-first / external-by-intent is mandatory. External calls receive only task-relevant context and must not automatically receive household history, camera data, unrelated memory, credentials, or private state.
* Preference and authority are separate. Memory or inference may influence reasoning but cannot itself grant permission.
* Consequential actions pass deterministic authorization outside the LLM; prohibited capabilities remain technically unavailable rather than merely discouraged by prompting.
* Internet content, browser pages, tool output, MCP responses, and other external content are untrusted data and never sources of authority.
* Anima must not self-program, self-update, alter its own permissions/policies, or obtain unrestricted operating-system access.
* Truth/state freshness, provenance, unknown/stale/conflict semantics, duplicate handling, concurrency, partial failure, verification, crash recovery, and replay are mandatory prototype concerns rather than deferred production hardening.
* Core/customer separation is mandatory: customer variation is expressed through configuration, household data, permissions, and enabled plugins/capabilities rather than private forks of ANIMA Core.
* Significant new infrastructure must be researched before being built. Foundational OSS requires license, ARM64/Pi compatibility, resource-footprint, maintenance, restart/recovery, failure-mode, security-boundary, backup, and replacement-path qualification.
* External dependencies must be wrapped behind ANIMA-owned interfaces when practical so the project is not unnecessarily locked to a library/provider implementation.
* The central software target is a Raspberry Pi 5-class controller using reliable SSD/NVMe-class persistent storage; the architecture must remain portable across ARM64/x86-64.
* Evidence must distinguish implementation success from simulated evidence, dependency availability, and real external/physical validation. No phase or final goal may be promoted on fabricated or mislabeled evidence.
* Final prototype acceptance requires integrated behavior and failure/recovery evidence, not merely successful compilation, isolated unit tests, or a scripted demo.

## Governing external specifications

* **ANIMA HA Notion SSOT:** https://app.notion.com/p/3c9833cb27ff81759597cdc69c59176c
* **Authority 3.0 governance package / `PROJECT_GOAL.md` lifecycle contract** in the connected Notion Authority documentation.
* **Home Assistant public integration/API contracts** for the HA interfaces actually adopted by the prototype.
* **OpenAI API / agent tool contracts** applicable to Luna 5.6 and the adopted agent runtime.
* **Model Context Protocol specification** for MCP capabilities adopted by the plugin/tool architecture.
* Exact third-party OSS versions/licenses become governing dependency contracts only after qualification and explicit adoption in the SSOT/repository.

## Owner or approval authority

* Project owner / final approval authority: **SketchOTP / Ghost Animus LLC**.
* AI Architect controls architectural progression, phase acceptance, drift review, dependency decisions, and Codex directives within the owner-authorized prototype goal.
* Codex is the live-codebase authority for implementation state and must provide evidence sufficient for independent Architect review.

## Adoption guidance

This file is `ADOPTED` as the stable project-end-state contract for the current authorized goal. It defines **what must be true when ANIMA HA is complete**, not the task history or current implementation state. Phase plans, directives, checkpoints, outcomes, and evidence belong in their respective Authority records and the Notion SSOT.

Do not weaken a success measure merely because implementation is difficult. If evidence reveals that a requirement is technically invalid, contradictory, or blocked by an external resource, return to the Architect for an explicit goal/specification decision rather than silently narrowing the goal.
