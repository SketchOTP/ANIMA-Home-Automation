# Phase 5 — Plugin Runtime and Capability/Tool Registry

Status: implementation complete, pending Architect review. This document describes the Phase 5 boundary only; it does not authorize Home Assistant, Luna, physical actions, or runtime software installation.

## Architecture

`PluginManifest` is the ANIMA-owned registration contract. Stable `anima.*` plugin IDs are independent of display names, Python distributions, MCP server names, and tool names. Manifest version, core compatibility, runtime kind, trust class, capabilities, event declarations, JSON Schemas, secret references, network declarations, risk metadata, timeouts, and restart limits are validated before registration.

The registry separates discovery from enablement. Native entry points are discovered with the standard `anima_ha.plugins` group but are not automatically enabled. A plugin moves through explicit registered, starting, healthy, disabled, incompatible, degraded/failed, and stopping states. Enablement validates configuration, supplies only declared secret references through a sanitized child environment, starts/connects the runtime, health-checks and lists tools, validates schemas, and publishes canonical descriptors. Disablement removes tools first, stops the runtime, clears future secret exposure, and persists the disabled state.

Canonical `ToolDescriptor` values normalize native and MCP tools. The descriptor owns namespaced identity, capability and plugin provenance, ANIMA risk class, semantic action, read-only/idempotency metadata, timeout, verification placeholder, output trust, and availability. MCP descriptions, annotations, names, and risk hints are never authoritative; manifest risk metadata wins, and unknown consequential classification fails closed through Phase 4 policy.

Every invocation validates arguments, constructs an ANIMA `ActionIntent`, evaluates Phase 4 policy, and invokes only on `ALLOW`. Missing policy service, deny, confirmation, or stronger-auth results never reach a plugin. Results are normalized into success, unavailable, timeout, plugin error, invalid argument/result, or structured policy outcomes. No physical action is implemented.

## Runtime boundary

- Trusted native plugins execute in-process and are explicitly classified trusted.
- MCP stdio plugins execute out-of-process through the official MCP Python SDK v2 client. Each operation uses a bounded connection and timeout, so process exit and transport failure become a normalized plugin failure.
- Streamable HTTP is represented by the same adapter using the SDK URL client; no permanent remote service is required by this phase and no external endpoint was used for acceptance evidence.
- A subprocess is a failure-isolation boundary, not a malicious-code sandbox. Arbitrary third-party code is not authorized merely because it runs in a subprocess. Container/sandbox hardening remains a later decision.

## Persistence and audit

Migration `0006_plugin_runtime.sql` persists manifests, compatibility, enablement, scoped configuration, runtime state, and the normalized tool catalog. Material registration, health, failure, disablement, and plugin-originated event ingress use the Phase 1 Event Journal. Plugin events are validated against the manifest declaration and become ordinary normalized event envelopes with plugin provenance; MCP tool output is not treated as an event stream.

The persistence store never writes raw secrets. Configuration is validated and stored per plugin. A new manager can restore persisted manifests/configuration only when a maintenance-provided runtime is supplied; failed startup remains unavailable rather than falsely healthy.

## Decisions

| Candidate | Decision | Rationale |
| --- | --- | --- |
| Official MCP Python SDK v2 `2.1.1` | ADOPT / WRAP | MIT, current v2 stable line; provides stdio and Streamable HTTP client/server boundaries. ANIMA wraps it and owns identity, policy, lifecycle, and trust. |
| `jsonschema` `4.26.0` | ADOPT / WRAP | MIT, stable JSON Schema 2020-12 validation; bounded schemas and no `$ref` dereferencing are enforced by ANIMA. |
| `importlib.metadata.entry_points()` | ADOPT / BUILD around | Standard PyPA discovery mechanism; discovery is separated from enablement. |
| Direct ANIMA manifest/registry | BUILD | Required to preserve domain identity, lifecycle, configuration, secrets, risk, policy, and audit ownership. |
| FastMCP | REFERENCE / DEFER | Broader server framework is unnecessary for the reference server; official SDK `MCPServer` is sufficient. |
| Pluggy | REFERENCE / DEFER | Useful in-process hook registry, but it is not an external process/failure or secrets boundary. |
| Container-per-plugin | DEFER | Stronger isolation may be needed later, but it would add operational complexity not required by the bounded reference plugins. |
| Subprocess MCP | ADOPT for optional plugins | Limits crash/transport failure impact while documenting that it is not a security sandbox. |
| Runtime package installation/marketplace | PROHIBITED / DEFER | Deployment remains maintenance-controlled; no package manager or arbitrary executable API exists in ANIMA runtime. |

## Evidence limits

Evidence is unit and synthetic x86-64 runtime/PostgreSQL/OPA/MCP evidence. The reference MCP server is local and synthetic. No Home Assistant, Luna, physical action, real external service, malicious-code sandbox, or native Raspberry Pi execution claim is made. ARM64 remains dependency/package metadata evidence only.
