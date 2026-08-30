# Phase 6 — Home Assistant Adapter

Status: implementation complete, pending Architect review. This boundary integrates an isolated Home Assistant Core 2026.8.2 instance. It does not implement the Phase 7 Attention Layer/Context Broker, Luna, generalized action concurrency, or physical-home behavior.

## Architecture and ownership

`HomeAssistantAdapter` is an ANIMA-owned provider adapter used by a trusted built-in Phase 5 plugin. HA-specific states, registry records, services, contexts, and IDs terminate at this module. Higher layers receive only canonical Phase 1 events/observations, Phase 2 provider-reference resolutions, Phase 5 tool descriptors/results, and Phase 4 policy outcomes.

The adapter uses a configured UUID as the stable HA provider scope. URL, hostname, HA location name, area/device/entity names, and friendly names never become canonical identity. Areas, devices, and entities are inventory records and Phase 2 provider references. Uncommissioned objects remain explicitly `UNMAPPED`; multiple HA references may map to one canonical resource, while an entity may map separately to a capability.

## Authentication and sensitive data

The runtime manifest declares a token secret reference. The raw token is supplied only when the plugin starts, is passed to the wrapped client in memory, and is cleared from the ANIMA connection object after client construction. It is not stored in the HA instance/inventory tables, plugin configuration, descriptors, journal, audit, or logs. Tests mint an isolated-instance token programmatically and use only synthetic credentials.

State attributes are allowlisted and bounded. Diagnostic/provenance data retains identifiers, state timestamps, context ID, and small semantic attributes; tokens, credentials, signed URLs, camera/media payloads, large blobs, and unrelated attributes are excluded.

## Discovery, normalization, and mapping

The adapter discovers HA version/config, current states, services, and area/device/entity registries. `unknown` becomes a Phase 1 `UNKNOWN` observation, `unavailable` becomes `UNAVAILABLE`, and other values become direct `KNOWN` observations. HA `last_updated` is source observation time; ANIMA receive time remains distinct. Deterministic idempotency combines provider scope, entity ID, source timestamp, state, and bounded attribute digest rather than receive time.

`state_changed` and area/device/entity registry events are subscribed. Registry changes trigger a coalesced inventory reconciliation and never rename or replace canonical graph identity. HA lifecycle and gap records use the existing Event Journal.

## Cold start, reconnect, and health

Cold start establishes subscriptions in buffering mode before retrieving registries and states. It applies the snapshot, then replays buffered events through Phase 1 ordering/deduplication before declaring `ONLINE`. This protects the snapshot/subscription interval without treating insertion order as source truth.

Health is explicit: `STARTING`, `CONNECTING`, `RECONCILING`, `ONLINE`, `DEGRADED`, `OFFLINE`, and `AUTH_FAILED`. Diagnostics include connected version, last successful sync/event, subscription state, inventory counts, mapping counts, bounded retry state, and error category.

Disconnect immediately records an uncertainty gap and stops refreshing Truth. Existing observations age through normal Phase 1 freshness rules. Reconnect is bounded and restores authentication, subscriptions, inventory, and current-state reconciliation before returning `ONLINE`. Current state can be recovered; missed historical transitions remain explicitly unrecoverable from a snapshot. Authentication failure enters `AUTH_FAILED` without an unbounded retry loop.

## Semantic tools and policy

The built-in plugin publishes only bounded semantic tools:

- `home.read_state` reads by canonical resource/capability identity.
- `home.set_power` controls only commissioned low-risk `input_boolean`, `light`, or `switch` mappings.

There is no agent-facing generic HA service-call tool. Every call follows the Phase 5 gateway, constructs the Phase 4 semantic action intent, and reaches HA only after `ALLOW`. `DENY`, `REQUIRE_CONFIRMATION`, and `REQUIRE_STRONGER_AUTH` remain structured non-invocation outcomes. Manifest risk is ANIMA-authoritative.

Control uses HA service calls, never REST `POST /api/states/<entity_id>`. After service acknowledgement, the adapter requests fresh provider state until the expected value is observed or the bounded verification deadline expires. An acknowledgement without observed state yields `VERIFICATION_FAILED`; transport uncertainty yields `UNKNOWN_RESULT` rather than fabricated success.

## Persistence and lifecycle

Forward migration `0007_home_assistant_adapter.sql` stores stable instance configuration/status and bounded provider inventory. It stores a secret reference, never the token. Phase 2 remains canonical identity storage and Phase 1 remains canonical event/truth storage.

Phase 5 enablement starts authentication, subscription, discovery, reconciliation, health checking, and tool publication. Disablement removes tools first, stops subscriptions/client resources, and revokes future secret access without deleting graph, journal, truth, memory, or inventory history. Restart restores maintenance-provided runtime/configuration; startup failure remains unavailable rather than falsely healthy.

## Dependency decisions

| Candidate | Decision | Rationale |
| --- | --- | --- |
| Home Assistant Core `2026.8.2` image | ADOPT for target evidence | Official GHCR image, pinned by multi-platform index digest; real isolated HA supplies the integration target. |
| `hass-client==1.2.3` | ADOPT / WRAP | Apache-2.0, Python 3.12-compatible pure-Python wheel; covers WebSocket auth, states, services, registries, events, and service calls. ANIMA owns lifecycle/reconnect/reconciliation. |
| Direct `aiohttp` HA client | REJECT for runtime | `aiohttp` remains a transitive transport, but duplicating the complete protocol client adds no architectural value. A small raw test helper is confined to fixture onboarding and test-side state injection. |
| `ha-testcontainer==2.7.0` | REFERENCE / DEFER | MIT and useful alpha orchestration prior art, but its base import required an undeclared optional Playwright dependency in qualification. Direct pinned container orchestration is smaller and more reproducible. |
| Direct pinned Docker fixture | ADOPT for tests | Provides exact image/runtime evidence without becoming an ANIMA runtime dependency. |
| Other HA clients | DEFER | No current alternative found with materially stronger coverage and a smaller replacement cost than the wrapped selected client. |

Adopted image: `ghcr.io/home-assistant/home-assistant:2026.8.2@sha256:56690a89c79a0de98035e1719f8324a92d5859c1192ff45adb0230ea81cb42a5`.

Observed manifest children include Linux amd64 and arm64. That is portability metadata, not a native Raspberry Pi run.

## Validation and evidence limits

The target harness starts the exact HA image, performs isolated onboarding/authentication, discovers real registries/state/services, observes real WebSocket state and registry events, maps commissioned references, invokes a real low-risk HA helper service through OPA and the Phase 5 gateway, verifies resulting state, injects a controlled verification fault, and exercises invalid auth, disable/re-enable, HA restart/reconnect/gap, and PostgreSQL restart.

The simulator's `home-assistant` scenario proves provider normalization into the same Phase 1 event contract without network access. Unit fakes test race, idempotency, mapping, policy short-circuit, lifecycle, and failure branches; they are not real-HA evidence.

Evidence is x86-64 container, PostgreSQL, OPA, MCP regression, and synthetic/virtual HA evidence. ARM64 support is image/package metadata only. There is no native Pi, physical device, real household, customer OAuth, high-risk action, Luna, or Phase 7 claim.
