# Household presence — bounded Core contract

Qualification date: 2026-09-06. Owner-approved presence sidecar; Tapo/Wansview development remains paused. Native checkout only. No account, phone, router, production, or shared runtime changes by this worker.

## Status and live gate

Implemented and locally regression-tested; not operationally qualified on a real phone/router. The module is frozen for lead integration. Lead owns runtime/API/PresencePanel, registration, policy routing, Journal/Attention callback wiring, owner-private presentation, and deployment. A separate worker owns real disposable-PostgreSQL/API integration tests.

Existing Core-configured HA metadata was inspected read-only, inside `anima-pc-ui-1`; only aggregate flags/counts were emitted. No token, entity ID, MAC, coordinates, person name, or raw state dump was printed. Observation: authenticated connection; **0 registered/enabled device_trackers; 0 mobile_app integrations; 1 registered/enabled person, unknown/unavailable**. This does not establish a usable source. No active LAN/ARP scan occurred. Router make/model remains unknown; the owner's router question is pending.

Cheapest next qualification: obtain router make/model through the owner, check its exact official HA integration and read-only client-detection behavior, then have the owner enable a supported source. Do not install a guessed router integration or create a fake phone from a known person's name. A real enabled tracker must first be commissioned to a household resource and capability with a trusted HA reference. Core then exposes an opaque source handle and the owner explicitly associates it with a canonical person.

## Official support and privacy findings

HA supports integration-provided router and app device trackers; the `device_tracker` building block itself is not a standalone router integration. Connection trackers assume their associated zone, which defaults to home but is customizable. Therefore `source_type=router` alone does not prove household-home semantics. Position trackers may report named zones; this module recognizes only `home`/`not_home` and suppresses other text. [HA device tracker documentation](https://www.home-assistant.io/integrations/device_tracker/)

The HA `person` implementation selects among contributing trackers and can restore state at startup. It is an aggregate, not independent corroboration of its tracker inputs. ANIMA excludes its aggregate signal whenever independent trackers are configured, including when those trackers are stale. [HA person documentation](https://www.home-assistant.io/integrations/person/), [HA 2026.9.0 person implementation](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/person/__init__.py)

The official UniFi implementation illustrates a viable router-backed route only **if the actual router/controller supports it**. Its client tracking uses detection time/last-seen information and can filter locally administered MACs; not every tracker represents a phone. Polling/detection timeouts mean disappearance is not an exact physical departure time. This is not a recommendation to purchase UniFi or evidence the household owns it. [HA UniFi docs](https://www.home-assistant.io/integrations/unifi/), [HA 2026.9.0 UniFi tracker implementation](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/unifi/device_tracker.py)

For geofence evidence, Companion requires owner-approved location permissions and relevant background/zone sensors, plus an approved way for the phone to reach HA when away. Its Zone Name Only option avoids precise coordinate sharing, but zone names remain potentially private. Do not request high-accuracy updates, alter permissions, or require a paid cloud service implicitly. This worker did not configure a phone or remote connectivity. [HA Companion location documentation](https://companion.home-assistant.io/docs/core/location/)

MAC assignment must use the address the phone presents **on the household SSID**, not a guessed factory address, hostname, vendor prefix, or model-inferred owner. Apple offers per-network private-address behavior, including Fixed/Rotating on supported OS versions. A stable per-network private address can preserve privacy without globally disabling private addressing. [Apple private Wi-Fi addresses](https://support.apple.com/en-us/102509)

Android distinguishes persistent randomization from non-persistent behavior; some configurations can change the address on later connections. The owner must confirm stability on the selected SSID and explicitly reconcile a changed address/source. A private/randomized MAC is not authentication and may be spoofed or reassigned. [Android MAC randomization behavior](https://source.android.com/docs/core/connect/wifi-mac-randomization-behavior)

## Frozen native interfaces

```python
HouseholdPresenceService(graph, truth, *, classify_source=None)
HouseholdPresenceNativePlugin(service, ha_instance_id, *, now=None)

service.snapshot(household_id, *, ha_instance_id, now,
                 person_id=None, limit=20, cursor=None)
service.list_sources(household_id, *, ha_instance_id, limit=20, cursor=None)
service.bind_source(context, *, ha_instance_id, person_id,
                    source_handle, freshness_seconds)
service.bindings_for_event(household_id, *, ha_instance_id, event)
```

`truth` is the existing Truth reader/projection, not `RealityStore`. `now` on the plugin is an injected zero-argument aware-datetime callable. The HA instance is server-injected. Native tools are `anima.household-presence.snapshot`, `.list_sources`, `.bind_source`; all require trusted `InvocationContext`. No household/principal/instance/entity/MAC authority is accepted in tool arguments.

`classify_source(ProviderReference) -> SignalKind | None` is Core-injected and defaults to `None`. It must qualify actual enabled HA registry/state evidence privately, verify the source kind and household-home zone semantics, and reject unsupported, retired, missing, or ambiguous sources. Kinds: `GEOFENCE`, `ROUTER_WIFI`, `HA_PERSON`. The classifier must not infer device ownership. Private `adapter.connection.get_state(ref.external_id)` is an appropriate source inspection boundary; its attributes are not tool output. Do not broaden generic durable HA attributes merely to populate this classifier.

Input schemas (unknown properties rejected):

| Tool | Accepted input |
| --- | --- |
| snapshot | optional person_id UUID, limit integer 1..50, cursor string at most 200 |
| list_sources | optional limit integer 1..50, cursor string at most 200 |
| bind_source | required person_id UUID, source_handle UUID, freshness_seconds integer 30..86400 |

Source output: `schema_version`, `items[{source_handle, resource_id, capability_id, signal_kind}]`, `next_cursor`, `source_status`. Status is `QUALIFIED_SOURCES` or `NO_QUALIFIED_COMMISSIONED_SOURCE`. Stable scoped UUID keysets and deduplication by canonical ID prevent duplicate pages. Handles are opaque references, **not** authorization grants.

Snapshot output: `schema_version`, `household_id`, `as_of`, `items`, `next_cursor`, `external_content_trust=EXTERNAL_UNTRUSTED`. Each person item contains canonical `person_id`, `status`, `value`, `binding_status`, bounded `signals`, `is_authentication=false`, `door_actor_verified=false`, `evidence_basis=ASSOCIATED_DEVICE_REPORTS`. Signal fields: binding/resource/capability IDs, binding version, kind, status, coarse value, quality, observed/received/expiry times, time basis, null physical timestamp, and independence flag. No person names or raw provider data are emitted.

Limits: 50 people/sources per page; 256 household members; 8 associated resources and 8 signals per person; 64 capabilities per resource; 16 refs per capability; 4096 resource entries and 4096 inspected capabilities in candidate discovery; 256 candidates; 16 observations per signal. Bounds fail explicitly instead of dropping possible conflicts. These bound processing after existing Graph queries; they do not introduce database-side paginated queries.

## Binding persistence and authority

Binding requires an active canonical person in the invocation household, a resource installed in that household, an exposed capability, and an active `home_assistant`/instance/`entity` provider reference targeting that capability. The direct request must come from an active household person whose existing `semantic_role` is `owner`. Core policy still applies; the plugin cannot grant authority.

Existing Graph commissioning preserves an existing provider reference instead of updating its metadata. Therefore the binding adds a **separate** private reference: provider `anima.household_presence`, household scope, kind `binding`, external ID equal to the canonical capability UUID, target the existing capability. Metadata records schema version, household/person IDs, original HA reference UUID, signal kind, freshness, binding version, verified home semantics, and commissioned owner. The same commissioning document adds `PERSON ASSOCIATED_WITH resource`; original nodes and HA reference are preserved. No new DB schema or parallel mapping store.

Identical binding requests are idempotent. Changing person, freshness, or source qualification is not an implicit overwrite: an explicit future correction workflow is required. Cross-person association is rejected. Readback verifies persistence instead of treating successful commissioning as proof. Existing Graph transaction/constraint behavior remains authoritative; this sidecar does not add a cross-process owner-binding serialization framework. A conflicting concurrent commission fails closed on readback rather than claiming an assignment succeeded.

Owner-private MAC presentation is allowed only through a separately protected UI resolver using the opaque handle. Do not put MACs, entity IDs, labels containing MACs, source names, location text, or raw notification payloads in model tool arguments/results, event payloads, or audit messages. The module does not implement that owner-private UI resolver. Owner labels should be separately bounded/sanitized; never infer ownership from them.

## Evidence semantics

`home` is a device/source report, not authentication or proof a person opened a door. Router `not_home` becomes signal `NOT_DETECTED`; alone it yields person `UNKNOWN`, never certain `AWAY`. Only qualified geofence `not_home` contributes coarse `AWAY`. Fresh independent home/away disagreement yields `CONFLICTING`; stale, unavailable, unknown and invalid clock data remain qualified as such. An HA-person aggregate cannot resolve its own independent-source disagreement.

Source time (`observed_at`, HA `last_updated`) and Core receipt time (`received_at`) stay distinct. Physical measurement time is unknown. Freshness may shorten existing Truth validity but never extend it. A long quiet device state can legitimately become stale; do not refresh its observation timestamp on reads or commissioning. The HA adapter's `seed_commissioned_truth` path is needed when earlier cached states predate canonical commissioning; replay alone may hit event deduplication. `device_tracker` needs the lead's commissioner passthrough and canonical fresh Truth attribution before this service can use it.

The module's outputs never retain raw locations. **Existing generic HA ingestion may already persist a named zone as raw state**; this projection cannot retroactively promise whole-pipeline location minimization. Any future ingress coarsening is lead-owned and needs separate validation.

## Exact event callback contract

```python
bindings = service.bindings_for_event(household_id,
    ha_instance_id=instance_id, event=normalized_ha_event)
events, replacements = normalized_router_connection_events(
    normalized_ha_event, bindings, previous_subset,
    now=now, source_continuous=qualified_continuity, recovery=False)
```

`bindings` are private `PresenceBinding` objects, never serialized. `previous_subset` is `dict[UUID, tuple[int, TruthResolution]]`, keyed by binding UUID and containing `(binding_version, prior_resolution)` for only the matched bindings. Both inputs are bounded to 8. Replace/remove **every matched binding's** prior entry using `replacements`; an empty replacement removes the old baseline. Stored replacement observations omit raw metadata. Keep baselines volatile and bounded overall; loss of a baseline suppresses an edge safely. Do not persist them as an alternative Truth database.

The existing normalized callback runs **after** Truth ingestion and does not receive snapshots/disconnect callbacks. Reading Truth there does not recover prior state. Main must maintain the explicit baseline, compare the adapter's `last_successful_state_sync` epoch on every callback, and clear **all** baselines when that epoch changes. Also clear at startup, transport/router loss, and reconciliation. Unknown/unavailable clears the matching baseline. A subsequent known observation initializes rather than inventing arrival. The helper rejects snapshot/restored/recovery/reconcile/binding-attribution data, missing real `last_updated`, stale evidence, unsupported states, mismatched provider/Truth keys, and out-of-order edges. Duplicate/older valid data cannot roll the baseline backward. Binding versions must agree.

`source_continuous` defaults false. HA connection continuity is not sufficient proof of router-source health. If a whole-router outage silently becomes tracker `not_home` without an unavailable signal, its distinction from ordinary device disappearance is not observable from this payload. **Keep departure-like triggers suppressed unless a qualified router-health/continuity signal exists**, or explicitly present the remaining event only as unqualified/coarse device non-detection under a separately approved policy. No real router has been qualified yet.

Output events: `household.presence.connection_changed`, source `anima.household_presence`, canonical person subject, payload transition `RECONNECTED` or `DISCONNECTED`, value `HOME` or `NOT_DETECTED`, canonical household/person/resource/capability/binding IDs and binding version, source/receipt/previous-source times, null physical time, explicit untrusted/non-authentication/non-door-attribution labels. Metadata includes household ID and `EXTERNAL_UNTRUSTED`. `DeliveryClass.GUARANTEED`, `EventImportance.NORMAL`; guarantee is a delivery contract, not guaranteed sensing. The ID is UUIDv5 of binding UUID plus binding version and canonical source event UUID; `causation_id` records that source event UUID. No raw provider source ID, MAC, name, or location escapes. Journal/Attention dispatch and any speech decision remain Main-owned.

The lower-level `router_connection_transition(binding, previous, current, *, now, previous_binding_version, source_continuous=False, recovery=False)` is pure and returns one event or None. Prefer the normalized-event helper for source-event-based deduplication.

## Validation / handoff

- PASSED: 70 focused synthetic presence tests, including time/provenance, conflict/privacy, opaque candidates, owner checks, Graph commissioning document validation, idempotency, native descriptors/context, initial/gap/recovery/snapshot/late suppression, causal deduplication and baseline clearing.
- PASSED: combined focused plus existing HA/plugin/Graph regressions: **110 passed, 1 skipped**.
- PASSED: Ruff format/check and module mypy.
- NOT RUN: conditional real-PostgreSQL test in this worker's environment; existing disposable `ANIMA_LATE_BINDING_TEST_DATABASE_URL` fixture unavailable. Separate lead-assigned worker owns new PostgreSQL/API test file. Never substitute production DB.
- NOT RUN: real phone/router events, actual owner-private MAC UI, full shared runtime/API integration by this worker, production deployment.
- Evidence: E4_REGRESSION_PROTECTED for this isolated module, not E5 operation. Retrieval confidence ADEQUATE for the bounded sidecar; router-specific qualification remains unresolved.

Owned files only: `src/anima_ha/household_presence.py`, `tests/test_household_presence.py`, this draft. Source freeze SHA-256: `d3cb40ebf45da750f5da2b79042961f4131450bb2888c940b97e18e5e6854f66`. No commit/push, no shared governance/Notion edits; lead owns project records and acceptance.
