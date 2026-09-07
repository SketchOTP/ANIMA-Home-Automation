# Tapo DL110 integration qualification

## Current checkpoint — PC-local normalization slice, 2026-09-07 UTC

**IMPLEMENTED / TARGET TESTED; LIVE DL110 INTEGRATION UNCONFIGURED.** This
checkpoint supersedes the earlier documentation-only status below, not its
negative device-support evidence. All work in this continuation is in
`/home/sketch/Projects/ANIMA Home Automation`; neither `/srv/ATLAS` nor GVFS was
edited. Source baseline remains `main` at
`435815855ffda8ff917406daeb063ca498b7b9c7` plus preserved concurrent dirty work.
Public GitHub main matches that baseline, not these uncommitted changes.

Read the local Authority/external-discovery skills, INDEX, entire current-state
kernel, active 026A directive, owner amendment, PC consolidation record and
existing qualification. Canonical Notion was fetched read-only; its current
PC-local consolidation entry agrees with the native paths. The large historical
body was not exhaustively reconciled. Retrieval confidence is ADEQUATE for this
bounded source/test slice; actual DL110 field support remains UNCERTAIN.
Shared governance/Notion edits are intentionally left to the lead.

### Actual provisioning evidence (read-only, no actuation)

The owner explicitly authorized a metadata-only check inside `anima-pc-ui-1`
using Core's existing `configured_connection()`. An authenticated HA WebSocket
read of `config_entries/get` and `config/entity_registry/list` succeeded:

| Flag/count | Observed result |
| --- | --- |
| Core HA connection configured and authenticated | true |
| SmartThings integration entries | 0 |
| TP-Link integration entries | 0 |
| HA lock registry entities, including disabled entries | 0 |
| SmartThings lock registry entities | 0 |

Only these flags/counts were emitted. No entity IDs, names, state, account data,
connection values or tokens were printed. No credential file was dumped, account
linked, provider configuration changed, command called, or lock operated. This
proves that **the inspected HA currently has no lock source to bind**; it does
not say whether the owner's Tapo/Samsung phone accounts already have a link.

### Fresh primary-source qualification

- Native TP-Link still has no lock platform in the inspected
  [current HA source](https://github.com/home-assistant/core/blob/d8840c5879458bd2dd504587f4d57cb6b1dfe4f9/homeassistant/components/tplink/const.py).
  [python-kasa's current supported list](https://github.com/python-kasa/python-kasa/blob/a29d0610bacd084a2197a7025cf083d4d2a51b02/README.md#supported-devices)
  still lists T110/P110, not DL110, and its device-type enum has no door lock.
  Native DL110 events are NOT QUALIFIED.
- TP-Link's [DL110 guide](https://www.tp-link.com/us/document/107408/) and
  [partner-linking instructions](https://www.tp-link.com/us/support/faq/3158/)
  establish SmartThings as a supported connection family. They do not establish
  an exported fingerprint-to-member event. Current US product/support pages
  distinguish hardware variants; exact owner revision/region/firmware remains
  required. Searches of official DL110 documentation did not locate a public
  event-export/webhook schema. No private API reverse engineering was attempted.
- HA's [2026.9.0 SmartThings lock implementation](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/smartthings/lock.py)
  exposes `lock_state` and optional `code_name`/`method` from generic capability
  data. The 2026.9.1 file is byte-identical (SHA-256
  `97c75bca5b030227a37a7c5264bc4fca3289bb9df2f4fd3f6c6e347b6c8e2a99`),
  and current dev has the same relevant behavior. This permits a narrow parser,
  not a DL110 support claim. Other source states must not be interpreted through
  its boolean `is_locked` as successful unlocks.
- The [entity implementation](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/smartthings/entity.py)
  rewrites HA state on both capability and availability updates. Optional
  attribution can therefore be a cached report, not the cause of the current
  update. HA does not project original SmartThings operation ID/time into these
  attributes. The [pinned client model](https://github.com/pySmartThings/pysmartthings/blob/26bf668896605f86459ebe49431c693ab914a4da/src/pysmartthings/models.py)
  distinguishes DeviceEvent identity and outer Event time; this module does not
  invent either. Named fingerprint attribution remains NOT QUALIFIED; the
  [vendor-hosted missing-attribution report](https://community.tp-link.com/en/smart-home/threads/topic/859494)
  remains contrary field evidence, not proof about this owner's hardware.
- Cost/approval gate remains material: [HA's current warning](https://www.home-assistant.io/integrations/smartthings/)
  identifies the October 2026 paid API transition. Samsung's
  [announcement](https://blog.smartthings.com/smartthings-updates/a-new-enhanced-smartthings-api-experience/)
  describes a $4.99/month personal plan and separate commercial tiers. Stock HA
  [OAuth scopes](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/smartthings/const.py)
  include write/execute access, not only lock reads. No entitlement, free ongoing
  service, paid plan approval, or account-link approval is assumed here.
- Android notification forwarding remains a separate fallback. Current
  [Companion source](https://github.com/home-assistant/android/blob/master/app/src/main/kotlin/io/homeassistant/companion/android/sensors/NotificationListenerSensorManager.kt)
  still forwards notification extras and Android post time under package
  allowlisting; that is not a lock-only/private-content filter. This module
  accepts no notification entity or prose. IFTTT remains rejected under the
  [vendor termination notice](https://www.tp-link.com/us/support/faq/5154/).

External-discovery disposition: WRAP only the documented SmartThings HA state
projection; REFERENCE the vendor history; leave Android filtering to its assigned
worker. No dependency, provider SDK, framework, network client or execution path
was added. The skill influenced the strict timestamp and cached-identity limits.

### Implemented contract and integration handoff

`src/anima_ha/tapo_events.py` exposes a pure, typed function:

```python
normalize_smartthings_ha_lock(
    state, *, binding, household_id, ha_instance_id, received_at, snapshot
) -> EventEnvelope
```

`TapoLockBinding` holds server-owned household/resource/capability/HA-instance
UUIDs, an exact private HA lock entity reference, and positive mapping version.
The receiver must validate active graph membership, capability ownership, exact
DL110 association and actual SmartThings registry ownership before building it.
Payload/model-supplied IDs, model names or `qualified_source` claims cannot
commission a binding. This pure module verifies exact context/source matching;
it cannot independently inspect a database or prove those commissioning facts.

| Normalized field/boundary | Implemented meaning |
| --- | --- |
| Envelope type/subject | `tapo.lock_observed`; canonical `resource/{UUID}`, never `truth.observation` or a SenseGuard/contact opening |
| Reported state | `locked`/`unlocked` only when HA state agrees with `attributes.lock_state`; otherwise explicit unknown/unavailable and quality reason |
| Source/receipt times | `source_occurred_at=null`; timezone-aware HA update time retained separately from required Core receipt time; missing/invalid HA time remains explicitly missing/invalid |
| Envelope times | `occurred_at` describes HA update, or receipt fallback with explicit `time_basis`; `recorded_at` is the actual supplied receipt; future HA clocks flagged, not silently repaired |
| Optional attribution | Bounded `code_name` to reported label (120 characters), `method` (64); invalid/control-containing/oversized values dropped, never truncated into another identity |
| Identity uncertainty | Always unauthenticated, canonical person null; cached report explicitly not verified as belonging to an operation; snapshots and non-unlocked observations omit label/method |
| Privacy | Only allowlisted normalized fields; no raw entity ID, context, notification text/extras, PIN, `used_code`, `code_id`, biometric template, video or arbitrary metadata in output/errors |
| Trust | Envelope `EXTERNAL_UNTRUSTED`; DIRECT describes observation of HA only; confidence unset; ContextBroker preserves external trust |
| Delivery | BEST_EFFORT observation, no policy grant, no automatic SENTRY wake, no arrival or current physical-state claim |

Stable event identity uses canonical household/instance/resource/capability,
mapping version and UTC-normalized HA `last_updated`. It excludes names, code
slots and raw payload hashes. With a HA timestamp, `source_event_id` is explicitly
a **HA cache revision**, not a vendor event ID. Retries at later receipts and
snapshot replay use the same ID; snapshot/live collisions retain first-ingested
provenance rather than creating a fresh alert. A remap version deliberately
creates a new observation scope, never an automatic new operation.

Without a usable HA timestamp, identity is receipt-only: retain the original
Core receipt on retry. Fresh receipt of the same undated state cannot be
deduplicated as the same physical operation. Two different upstream operations
collapsed to one HA revision cannot be recovered; attribution-only changes with
the same HA timestamp do not create a second event. This is not exactly-once
device delivery, burst completeness, cross-phone deduplication or a new durable
queue. The existing Journal owns actual persistence/deduplication.

The contract and zero-source provisioning evidence were sent to Tesla's
`vendor_event_ingress.py` worker. Agreement: keep SmartThings HA cache observations
distinct from Android relay events, validate bindings server-side, no automatic
wake/Truth/authentication, and default UNCONFIGURED. The lead owns shared HA/UI
hooks. In particular, the existing generic HA normalizer drops `lock_state`,
`code_name` and `method`; a future approved hook must call this parser before
that lossy projection. Do not widen the generic attribute allowlist or feed a
notification sensor into generic state persistence as a shortcut.

### Concrete next provisioning gate

The lowest-cost check remains a passive, redacted existing app history/push
comparison and non-secret model revision/region/firmware information. No lock
operation or new fingerprint/profile is needed. SmartThings production enablement
additionally needs an owner-approved existing/new partner connection and stock
HA OAuth grant with explicit API cost acceptance, an actual HA lock registry
entity, and privately checked/redacted field examples from ordinary use showing
`state`, `lock_state`, update timestamp and which optional fields actually exist.
No token is requested. If attribution does not export, state-only observation
can be qualified separately; do not promise named unlocker or infer a person.

Until those gates and receiver graph validation are satisfied, leave the route
UNCONFIGURED. A pure parser or authenticated HTTP success is not provisioning,
DL110 operational qualification, a notification receipt, or SENTRY voice delivery.
No shared hook or configuration was changed by this worker.

### Validation — current slice

- PASSED: 95 synthetic/adjacent tests across `test_tapo_events.py`,
  `test_home_assistant.py`, `test_reality_substrate.py`, `test_senseguard_alerts.py`.
  Covers mismatches, malformed inputs, ambiguous states, privacy, untrusted
  ContextBroker projection, timestamps/skew/delay, replay/remap and attribution.
- PASSED: targeted Ruff formatting/lint and strict mypy (two files). The first
  typing run caught an unannotated test-helper kwargs dictionary; it was fixed
  and rerun, without weakening source types or assertions.
- PASSED: current primary-source inspection and explicitly authorized live HA
  integration/entity count read. That read proves absence, not device support.
- NOT RUN: real DL110 event delivery, actual profile availability, new module's
  PostgreSQL/HTTP integration, live SENTRY/voice delivery, deployment, hosted CI.
- Scope: only this document, new `tapo_events.py`, and new `test_tapo_events.py`.
  No commits/push, source credentials, account/device mutations, or shared edits.
  Evidence is E3_TARGET_TESTED for the normalizer; not E5 device qualification.

## Historical checkpoint — documentation-only qualification, 2026-09-06

Checked: 2026-09-06 (America/New_York). Scope: passive lock/unlock event
notifications and device-reported member/profile attribution. Owner confirmed
**Tapo DL110**; hardware revision, firmware, region and installed app versions
remain unknown. This is not T110 (contact sensor), P110 (plug), or DL130.

**Research complete; household integration NOT QUALIFIED.** Retrieval confidence:
`ADEQUATE` for the inspected implementation and documented routes;
`UNCERTAIN` for this lock's actual payloads. Evidence: `E1_OBSERVED`.

The strongest structured candidate is **Tapo cloud → SmartThings → HA
SmartThings lock → ANIMA**. The cheapest next qualification is **passive comparison
of an existing Tapo Android notification with its corresponding app Event Log
entry**, before enabling any forwarding. HA Companion's Tapo-only notification
sensor is a concrete fallback transport, but its stock implementation does not
satisfy the complete privacy/provenance contract below without additional work.
Neither route currently proves named fingerprint-unlocker delivery.

## Authority and inspected local state

Read root `AGENTS.md`, Authority/external-discovery skills and their relevant
references, `.agent/INDEX.md`, the mandatory goal/profile/current kernel, active
026A directive, and
`docs/OWNER-SENTRY-ADMIN-ROUTINES-EVENTS-2026-09-06.md`. No applicable ancestor or
`docs/AGENTS.md` was found. The owner's independent lock assignment governs this
document; the primary lead owns actual desktop SENTRY integration and shared
records. Older phase pointers in CURRENT are historical, not new authority.
The owner amendment changed during parallel work and was re-read before handoff;
its voice-only native SENTRY direction remains with the primary lead. This
document proposes no typed chat, memory-vault writes or SENTRY source changes.

The mounted repository root was verified. At inspection, branch `main` and the
public GitHub `main` both resolved to
`435815855ffda8ff917406daeb063ca498b7b9c7`; the working tree had pre-existing
source, test, UI, workflow, deployment and governance changes. Those are not this
agent's work. Canonical Notion was fetched read-only; its large response was
truncated, so no exhaustive Notion reconciliation or new acceptance is claimed.
No credential files or device/account endpoints were inspected.

Relevant implementation observations:

- `src/anima_ha/home_assistant.py` subscribes to `state_changed` and three
  registry-update types, not arbitrary notification/custom lock events.
  `normalize_state_event()` journals the raw entity state. Its
  `_bounded_attributes()` retains only `friendly_name`, `unit_of_measurement`,
  `device_class`, `state_class`, `icon`, and `supported_features`. It drops
  SmartThings `code_name`/`method` and Companion `post_time`/`package`.
- That normalizer uses HA `last_updated` as observation/event time, takes a new
  ANIMA receipt time, and marks known provider state as DIRECT with confidence
  1.0. This describes the provider observation; it cannot qualify the physical
  event time, unlocker, or delivery completeness. Applying it unchanged to
  `last_notification` would persist private notification text as state while
  losing its transport provenance.
- `src/anima_ha/events.py` already separates mandatory timezone-aware
  `occurred_at`/`recorded_at`, optional source identity/sequence, and observation
  `observed_at`/`received_at`. Reuse this Journal/Truth boundary.
  `src/anima_ha/context.py::_event_item()` requires envelope metadata
  `external_content_trust=EXTERNAL_UNTRUSTED`; otherwise it labels event context
  `OBSERVED_LOCAL`. Merely mentioning untrusted content in prose is insufficient.
- Existing HA tests cover normalization, snapshot idempotency and buffered
  updates. They are not DL110 qualification. `senseguard_alerts.py` contains
  contact-opening-specific checks; a bolt unlock must not masquerade as
  `senseguard.opened`. Future lock events need an explicit attention mapping to
  the existing durable SENTRY request flow, owned by the primary lead.

## Route assessment and evidence

| Route | Lock/unlock information | Named fingerprint/profile | Disposition |
| --- | --- | --- | --- |
| Tapo app Event Log | Vendor documents timestamped lock/unlock records | Named members/fingerprints exist in the app; exported association unproven | REFERENCE; source sample comparison |
| Native HA `tplink` / python-kasa | No implemented/confirmed DL110 lock route found in inspected versions | No confirmed route | REJECT for immediate adoption; revisit explicit upstream support |
| SmartThings cloud through HA | Vendor-supported connection family and implemented HA lock capability | Optional identity fields exist in HA code; DL110 population unproven, with contrary field evidence | WRAP candidate, account/cost and device-evidence gates |
| Android Tapo notification through HA Companion | Actual app-notification forwarding implemented | Only possible when the actual notification contains it | COMPOSE candidate; passive sample first, privacy work before activation |
| Official Tapo export/webhook/API | No documented DL110 event export endpoint/schema located | Not established | REFERENCE only; no private API reverse engineering |
| IFTTT | Vendor service terminated | Not available as a current fallback | REJECT |

### Native HA and python-kasa

The [HA TP-Link supported-device list](https://www.home-assistant.io/integrations/tplink/)
does not confirm DL110. More decisively, the
[HA 2026.9.0 platform list](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/tplink/const.py)
has neither LOCK nor EVENT, and its current
[development platform list](https://github.com/home-assistant/core/blob/d8840c5879458bd2dd504587f4d57cb6b1dfe4f9/homeassistant/components/tplink/const.py)
also has no lock platform. The inspected integration directory has no `lock.py`.
This is stronger than a missing product name, but is not a claim that future
native support is impossible.

At python-kasa master `a29d0610bacd084a2197a7025cf083d4d2a51b02`, its
[supported-device list](https://github.com/python-kasa/python-kasa/blob/a29d0610bacd084a2197a7025cf083d4d2a51b02/README.md#supported-devices)
and fixture tree have no DL110 entry; its
[device types](https://github.com/python-kasa/python-kasa/blob/a29d0610bacd084a2197a7025cf083d4d2a51b02/kasa/device_type.py)
have no door-lock type. `childlock.py` is not evidence for a deadbolt.
Disposition: do not probe credentials, reset devices, toggle compatibility
settings or install speculative Tapo plug/camera packages for this task.

### SmartThings: viable structured candidate, not named-unlocker support

TP-Link's [DL110 installation/user guide](https://www.tp-link.com/us/document/107408/)
identifies SmartThings compatibility, and its
[current linking instructions](https://www.tp-link.com/us/support/faq/3158/)
include door locks and TP-Link account authorization. This is the partner
cloud route, not evidence of local Matter support. The linked SmartThings Tapo
partner page did not expose a DL110-specific record in its retrieved text;
exact regional hardware compatibility still needs the owner's device evidence.

[HA SmartThings `lock.py` at 2026.9.0](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/smartthings/lock.py)
creates an entity when `main` exposes `Capability.LOCK`. It maps optional
`lock` attribute data as `codeId → code_id`, `codeName → code_name`,
`method → method`, plus `lockName`, `timeout`, and `usedCode`. Those are generic
capability mappings, not evidence that Tapo supplies any of them. Exclude
`usedCode` entirely from ANIMA; its semantics are unnecessary here. A code slot
is not necessarily a fingerprint/member identifier.

Also inspect `lock_state`, not just the HA boolean: this implementation's
`is_locked` compares the source value only with `locked`. A non-locked value
does not by itself prove a successful unlock. Accept only qualified source
states; preserve jammed/unknown/intermediate states and separate bolt state
from door-open/closed evidence.

The [HA entity update handler](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/smartthings/entity.py)
copies event value/data into state and writes the HA entity. It does not expose
the original event ID/time as lock attributes. The
[pysmartthings 4.0.1 models](https://github.com/pySmartThings/pysmartthings/blob/26bf668896605f86459ebe49431c693ab914a4da/src/pysmartthings/models.py)
have `DeviceEvent.event_id`, optional `data`, and outer `Event.event_time`;
its [SSE dispatcher](https://github.com/pySmartThings/pysmartthings/blob/26bf668896605f86459ebe49431c693ab914a4da/src/pysmartthings/smartthings.py)
passes the inner DeviceEvent to listeners, dropping the outer time at that
boundary. Therefore ordinary HA `last_updated` is not the lock's occurrence
time, and repeated identical source events need not survive as distinct HA
state changes. A future source-event seam would be additional implementation.
The inspected [HA lock tests](https://github.com/home-assistant/core/blob/2026.9.0/tests/components/smartthings/test_lock.py)
exercise a Yale fixture, not DL110 identity.

There is relevant negative evidence: in the
[DL110 SmartThings identity thread](https://community.tp-link.com/en/smart-home/threads/topic/859494),
a user reported missing PIN/biometric attribution. TP-Link staff did not confirm
a working solution and moved it to Feature Requests on April 17, 2026. This is
a vendor-hosted field report plus staff response, not a test of this owner's
lock or proof of impossibility. Samsung's
[August 28 lock capability announcement](https://community.smartthings.com/t/update-for-the-new-smart-lock-code-management-experience-and-beta-opportunity/310803)
introduces `lockUsers`/`lockCredentials` migration for supported hub locks;
it does not establish DL110 cloud fingerprint events. Do not enroll a beta,
retrieve credentials or migrate profiles to explore that possibility.

**Cost and authorization:** Samsung's
[June 23, 2026 API announcement](https://blog.smartthings.com/smartthings-updates/a-new-enhanced-smartthings-api-experience/)
says existing free API access continues through Q3, with a $4.99/month personal
plan and separate commercial tiers targeted for October 2026. The
[current HA warning](https://www.home-assistant.io/integrations/smartthings/)
explicitly says this affects its integration. Native SmartThings app usage is
distinguished from API access in Samsung's announcement. Do not present this
as a permanently free ANIMA backend. Commercial ANIMA distribution would need
separate terms/pricing qualification; no personal entitlement is assumed.

HA's [requested OAuth scopes](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/smartthings/const.py)
include device read/write/execute and wider location/rules/scenes scopes.
The [configuration flow](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/smartthings/config_flow.py)
requires its scope set; stock onboarding is not a lock-only read grant.
No signup, account linking, subscription or OAuth approval was performed.
If already connected, the cheapest structured check is an operator-produced,
sanitized readback of this lock's capability names and same-event optional
attribution fields. Do not request or publish broad HA diagnostics: they may
contain private names and unrelated device data.

### Tapo app history and official export

The DL110 guide documents Event Log/timeline, named members/fingerprints,
notification settings and optional cloud Log Backup. These are distinct features;
Log Backup is not a documented CSV/JSON export or event subscription API.
The reviewed guide, DL110 support/download index, Tapo notification guidance and
targeted official-site searches did not establish a public DL110 webhook,
history-export API or guaranteed named notification schema. This is a bounded
search result, not a claim about private partner APIs. No log backup was enabled,
cleared or downloaded. [DL110 guide](https://www.tp-link.com/us/document/107408/),
[support index](https://www.tp-link.com/us/support/download/tapo-dl110/v1/).

IFTTT is explicitly unsuitable: TP-Link announced full termination for Tapo and
Kasa on **August 1, 2026**. Older product material listing IFTTT is stale for
this decision. [Vendor termination notice](https://www.tp-link.com/us/support/faq/5154/).

### Android HA Companion fallback: what actually works in source

[Companion notification documentation](https://companion.home-assistant.io/docs/core/sensors/#last-notification)
provides Android `last_notification`, notification-listener permission and an
app allow list. Keep `Disable Allow List Requirement` OFF; only the observed
installed Tapo package may be allowed. It is not an iOS relay. An allowed new
notification may be necessary before the entity first appears.

The inspected Android source at `d3af0e4c91484b69f8a175c86d1514ea2ae2c907`,
[NotificationListenerSensorManager](https://github.com/home-assistant/android/blob/d3af0e4c91484b69f8a175c86d1514ea2ae2c907/app/src/main/kotlin/io/homeassistant/companion/android/sensors/NotificationListenerSensorManager.kt),
provides the actual transport: it forces an update on an accepted notification,
sets the state from text/title/package (truncated to 255 characters), and adds
notification extras plus `package`, `post_time`, `is_clearable`, `is_ongoing`,
`group_id`, `category`, and Android 8+ `channel_id`. `post_time` comes from Android
`StatusBarNotification.postTime`: the time Android posted the notification, not
the time a person operated the lock.
[Android timestamp definition](https://developer.android.com/reference/android/service/notification/StatusBarNotification#getPostTime()).

The inspected code does not explicitly emit the notification key, numeric ID,
tag, `when`, visibility or group-summary flag. It skips `ranker_group`, not all
app group summaries. Do not invent these fields in a Companion payload or claim
exactly-once transport. A latest-value sensor is not a durable event queue;
burst loss, app suspension, offline delivery and replay remain untested.

**Privacy gap:** package allowlisting does not filter notification types within
Tapo. The implementation maps all extras, including arrays/nested bundles; it
does not implement a lock-field allowlist or a private-notification visibility
gate. The separate `active_notification_count` sensor can attach contents of
all active notifications and has no app allowlist. Keep it, removed-notification
and media-session sensors disabled. Lock-screen hiding alone is not proof that
listener forwarding is private.

Tapo's [notification controls](https://www.tp-link.com/us/support/faq/3742/)
separate system/promotional/device notifications and quiet hours, but do not
constitute a promised content schema. A Tapo-only relay must still reject
account notices, OTPs, other devices and media. A generic downstream HA parser
cannot undo sensitive collection that already happened on the phone or HA.
Under this task's strict boundary, stock Companion is a **candidate transport,
not an approved unattended relay**. If source-side restriction cannot exclude
those payloads, a narrowly filtered client change is required and is outside
this documentation-only assignment. No emulator, Tasker purchase, Android
installation, notification-permission change or HA configuration was performed.

## Proposed event contract — not implemented

Preserve the replaceable HA adapter, canonical Journal/Truth and actual desktop
SENTRY. Parse deterministically at the boundary; raw vendor prose is data and
cannot issue commands. The following names describe a proposed lock payload,
not fields already delivered by DL110 or an existing ANIMA API.

| Field / boundary | Required meaning |
| --- | --- |
| `schema_version`, canonical household/resource | Versioned contract; Core-owned mapping to this lock and entrance. Never infer identity from similar device names. |
| `event_kind` | `locked`, `unlocked`, or explicit unknown/unclassified. A notification arrival is not itself a physical unlock. |
| `source_route`, provider/relay reference | Distinguish `smartthings_ha_state` and `tapo_android_notification`; keep opaque internal references and exact app/parser versions. |
| `source_event_id` | Genuine vendor ID if available; otherwise explicitly relay-derived. Never substitute HA context ID for a TP-Link event ID. |
| `source_occurred_at` | Nullable, timezone-aware source timestamp, with its actual provenance/precision. Do not invent a year, zone or seconds from a localized display. |
| `notification_posted_at`, `ha_updated_at`, `anima_received_at` | Separate timestamps. Missing ones remain null. HA update time and Android post time are delivery observations. |
| envelope `occurred_at` / `recorded_at` | For unknown physical time, emit a notification-observed event at its observation time; preserve null physical time and explicit `time_basis`. Do not mislabel receipt time as physical operation time. |
| `reported_method`, `reported_profile_ref`, `canonical_person_id` | Optional; populate only from the same event. Owner mapping is household-scoped and versioned. Unmapped/ambiguous/absent remains unknown. No previous user's name carried into the next event. |
| `identity_basis`, `identity_status` | Device-reported profile, mapped/unmapped/unknown/conflicting. Neither fingerprint-method text, phone location nor routines creates authenticated owner authority. |
| trust / quality | Envelope `external_content_trust=EXTERNAL_UNTRUSTED`; explicit parser result, source delay/unknown delay, snapshot/replay flags, and uncertainty. No automatic confidence 1.0 for inferred physical facts. |
| `dedup_key`, `correlation_id`, `causation_id` | Persist transport identity and link derived interpretation to the immutable original normalized receipt. Keep correlation distinct from proof of equivalence. |

Deduplication must survive consumer restart. Prefer scoped genuine vendor event
identity; retries with the same ID must append/dispatch once. For stock Companion,
derive a transport key from relay instance, package, post_time, observed
channel/group and an HMAC of allowed normalized content. This is a heuristic:
post times may change on repost, fields may be absent, and two phones have
different receipt times. Keep ambiguity explicit; do not claim physical-event
deduplication or cross-phone equality from it. Avoid bare hashes of private names.

Group summaries and ambiguous updates must not produce a new unlock. Use only
validated individual-event templates; quarantine unknown formats as minimal
diagnostic status, without storing the raw text. Identical real operations at
different times must remain distinct. Snapshot/reconnect/replay should rebuild
observations without announcing a fresh arrival. Delayed notifications must not
overwrite newer direct state or establish current occupancy. Absence of push
means unknown delivery, not a locked or safe door.

Before any future enablement, source-side filtering must reject non-lock data
and media. Exclude the raw notification entity from ANIMA's generic state path;
prevent raw text/extras entering HA Recorder/history, logs, traces, backups or
cloud exports. A Recorder exclusion alone does not hide current entity state
from authorized HA clients and does not fix Companion's source-side gap.
Only sanitized normalized fields enter durable ANIMA records. Profile mappings
remain private household data; SENTRY receives minimum relevant evidence under
owner preferences, with no fingerprint images/templates, PINs, `usedCode`,
credential payloads, unrelated notifications, video, audio or public fixtures.

Once journaled, a qualified event may reuse durable Attention/SENTRY dispatch
and existing configured delivery policy. Internal guaranteed delivery is not a
guarantee of upstream Tapo push. Quiet hours affect configured response delivery,
not whether an event happened; an absent notification and an absent delivery
receipt are separate failures. No lock/unlock capability is added by this plan.

## Cheapest safe next qualification and exact missing resources

1. **No integration change:** operator inspects the existing DL110 Device Info
   for region/hardware/firmware and records Android OS, Tapo version and locale.
   Do not publish MAC, serial, address, account ID or household names.
2. **Passive source sample:** from already-existing history/notifications or the
   next ordinary household use, compare a named fingerprint unlock notification
   with its Event Log entry. Record only redacted field presence, whether the
   method/name occurs in push or only in history, and actual available timestamps
   with timezone/precision. Include a lock notification and an anonymous/manual
   event when available. Do not operate the lock, create profiles or obtain
   biometric material for a test. If there is no corresponding push or no name,
   record that negative result; stop promising named-unlocker relay.
3. **If SmartThings is already linked:** obtain an operator-sanitized read-only
   field sketch of this DL110's `main.lock.lock` value and same-event optional
   `data` fields, plus the resulting HA attributes. No command calls, broad
   diagnostics or tokens. If no link exists, account/cost/OAuth review is a
   future operator decision, not a reason to create an account now.
4. **After suitable evidence and separate implementation authority:** qualify
   the narrow filter and normalization offline using synthetic/redacted cases:
   named/unnamed operations, missing/invalid time, same-state events, repeat,
   grouped summary, burst, delayed/reordered receipt, unknown locale, reconnect,
   privacy rejection and hostile text. Then passively compare delivery through
   HA → ANIMA Journal/Truth → one SENTRY wake against ordinary observed use.
   Failures and unobserved cases retain explicit status. No production test or
   alteration is authorized by this document.

**Missing operator resource:** an existing owner-controlled Android endpoint
already receiving DL110 Tapo notifications, its non-secret version/locale/device
revision information, and a privately reviewed/redacted matched
notification/Event Log example demonstrating whether unlock method and member
identity actually leave the app history. Its existence and suitable push content
are not established in this assignment. For SmartThings, additionally missing
are an existing linked DL110 capability/event readback and an owner decision on
the impending API subscription and broad OAuth grant. No API token is requested.

## Validation and handoff

| Check | Result |
| --- | --- |
| Local scope, kernel, live adapter/context contracts, existing tests inspected | PASSED — static evidence only |
| HA 2026.9.0/current native platforms and python-kasa device/fixture support inspected | PASSED — DL110 support not established |
| SmartThings lock mapping, entity handler, pinned client and OAuth scopes inspected | PASSED — candidate mechanics, not device qualification |
| Current vendor export/notification paths and API price transition checked | PASSED — bounded research; no official export found |
| Android notification client fields/privacy limitations inspected | PASSED — stock transport does not meet complete relay contract |
| Document scope and whitespace review | PASSED |
| Real DL110 lock/unlock and named fingerprint/profile delivery | NOT RUN — operator payload/resource gate |
| Companion phone/HA delivery, privacy exclusion, loss/restart qualification | NOT RUN |
| ANIMA/SENTRY target tests and runtime qualification for this lock | NOT RUN — no integration implementation |
| Commits, push, shared governance/Notion updates, production/account changes | NOT APPLICABLE — expressly excluded |

External-discovery disposition: WRAP SmartThings conditionally; COMPOSE a
restricted Android transport conditionally; REFERENCE Tapo app history;
REJECT immediate native/IFTTT adoption. The skills drove implementation-level
inspection and explicit negative evidence, not new runtime authority.
Only this document was authored. Primary lead may use these findings in its
authorized records; no stage/goal acceptance, deployment or operational-support
claim is made. Recheck when actual hardware/firmware/app evidence arrives,
upstream support changes, or SmartThings publishes final October terms.
