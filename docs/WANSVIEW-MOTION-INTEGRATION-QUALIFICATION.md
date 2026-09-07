# Wansview motion-only integration qualification

Checked: 2026-09-06 America/New_York (public-source checks continued into
2026-09-07 UTC). Scope: owner-authorized isolated intake implementation under
026A, PC-native `/home/sketch/Projects/ANIMA Home Automation` only.
**Android app notification intake and headless PC hosting are OWNER SELECTED;
live integration UNQUALIFIED.** Camera setup is incomplete. Exact model,
installed Android app package/version and a captured notification remain unverified. The missing
camera model does not block app-notification intake design or isolated tests.
Retrieval confidence: **ADEQUATE for the route/implementation assessment;
UNCERTAIN for the owner's exact camera and delivery behavior.** Evidence:
E3_TARGET_TESTED for the ANIMA-owned report validator; E1 for source inspection.

## Build freeze and lead-reported runtime preparation

The lead released the earlier build freeze within the owner's integration scope to separate the real
ANIMA-owned schema validator from the fixture entry point. The correction is
implemented and code is frozen again; the lead will rebuild after both this
module and Tesla's coordinated receiver correction are finished. Source SHA-256:
`12cd296a99b3409a5cc6b022751bbe8cb6f42a7318b172cc5b01890084b1fe04`.
Test SHA-256:
`0f10b3d088f16667cebe93170f4cd1ed9b6a5b599505cc6c1fa1971377c63387`.
Final rerun: **83 tests PASSED**, Ruff check/format check PASSED, mypy PASSED
(existing unused-override warning only). Combined Docker build status is
lead-owned and is not reported as passed by this worker.

Latest runtime evidence was **reported by the lead**, not independently rerun
here: official APT Waydroid 1.6.2, Weston 13 and **ADB 34.0.4-debian** (Android
Debug Bridge 1.0.41; correcting the earlier report of 35); verified official GAPPS
system image `20260403` and vendor image `20260428`; Android 13 x86_64 headless
boot with `sys.boot_completed=1`, `dev.bootcomplete=1`, and Play Store package
`com.android.vending` present. This supersedes earlier missing-runtime/tool
snapshots. It establishes Android boot preparation only, not vendor push or
Google certification. **Wansview Cloud is not installed; no vendor sign-in or
certification was granted.** Android/session/compositor and container are now
**stopped**, container autostart disabled; images and packages are retained.
See the lead-owned [runtime runbook](ANDROID-NOTIFICATION-RUNTIME-026A.md).

The private `dbus-run-session` has no notification sink yet, so built-in
forwarding currently skips startup. The dedicated collector remains required;
neither the working Android boot nor this normalizer provides that service.

Lead-reported privacy preparation: audio/microphone route absent with a dummy
regular-file `PULSE_RUNTIME_PATH`; pyclip missing, so no clipboard bridge.
Initial device-permission broadening was detected, stopped and restored to
udev mode 0660. The root container unit now masks `video0`, `video1`, `/dev/v4l`
and `/dev/snd` through `InaccessiblePaths`, and makes `/dev/dri` and
`/dev/dma_heap` read-only. Inside-container camera nodes were reported as
`c--------- 0,0`, with host device modes still 0660. The authoritative exact
override, procedure and evidence are recorded in the lead's runtime runbook;
this summary neither changes those settings nor claims general sandbox
certification or media-free notification transport.

Unattended notifications, Linux logout, cold reboot, vendor-session recovery,
actual Wansview motion parsing and end-to-end SENTRY receipt remain **NOT RUN /
UNQUALIFIED**. The isolated intake is not a complete Wansview integration.

## Current implemented slice and receiver contract

This section supersedes the earlier held proposal and listener-specific field
requirements below. The owner authorized two isolated Python files plus this
document. No shared governance, receiver, runtime hooks, installs or accounts
were changed by this worker. Main live SENTRY work remains lead-owned.

Implemented `src/anima_ha/android_notifications.py` and
`tests/test_android_notifications.py`. **`sanitize_relay_report` is a real
ANIMA-owned protocol validator, not a Wansview raw-notification parser.** It
takes exact `package_name`, lazy `load_fields`, trusted `RelayRegistration` and
aware Core `received_at`. It checks package before fields and can return
`NORMALIZED_REPORT` without a synthetic flag. Its success establishes schema
validity only. Receiver-owned authenticated producer qualification and explicit
wake permission must be enforced separately, defaulting disabled.

The legacy `normalize_notification(..., synthetic=False)` still fails closed
with `LIVE_FORMAT_UNQUALIFIED`; `synthetic=True` selects only the old fixture
format. Production must call the new sanitizer, not toggle that flag. The raw
Wansview Notify → report extractor and private-bus sink remain unimplemented.

`RelayRegistration` binds nonzero household/relay UUIDs, explicit camera alias
→ canonical camera UUID mappings, package allowlist restricted to
`net.ajcloud.wansviewplus`, allowed channels and freshness bound (default 300s).
The receiver validates camera ownership against the household graph; the pure
normalizer cannot. Unmapped camera reports are **rejected**, superseding the
historical unmapped-journaling proposal. No raw Bundle, body/title, media, URI,
OTP, authority or unrelated-app fields are accepted or echoed in rejection.

The **exact ten required report keys** are `format`, `delivery_id`,
`camera_alias`, `channel_id`, `kind`, `android_posted_at`, `source_occurred_at`,
`relay_received_at`, `is_group_summary`, `reported_loss_count`. No extra keys.
`REAL_REPORT_FORMAT` is `anima.android.motion.report.v1`; delivery ID is canonical nonzero
UUID text; aliases/channels are configured ASCII labels, 1–64 characters;
kind is `motion_reported`; times are timezone-aware ISO strings; source time
and loss count may be null. Loss count is an integer 0–1,000,000, not a boolean.
This is an **ANIMA-owned relay protocol**, never a claimed vendor sample format.
The separate fixture entry point requires `anima.android.motion.fixture.v1`;
both entry points reject the other's format.

Two **server-configured** transport profiles share this schema:

- `Transport.ANDROID_LISTENER` (default): requires real-format-shaped post time,
  configured channel and boolean summary; summary reports are ignored.
- `Transport.WAYDROID_PRIVATE_DBUS`: requires post time, channel and summary
  **null** because the inspected forwarding API does not provide them. Empty
  channel configuration is appropriate here; it is not permission to accept
  arbitrary apps or camera aliases. No grouping guarantee can be claimed.

`NormalizationResult` contains disposition plus optional EventEnvelope and
`DeliveryReceipt(event_id, content_digest)`. Real protocol events are
`external.android.motion_reported`, `schema_qualification=ANIMA_OWNED_SCHEMA`,
`synthetic=False`, `EXTERNAL_UNTRUSTED`, and **`wake_eligible=False`**. The sanitizer
does not set `parser_qualification` or `producer_qualified`; the receiver alone
derives source qualification and wake eligibility from server registration.
Payload cannot assert adapter identity, qualification, authority or wake flags.
Unknown identity/evidence and no authority apply to all report events.

Fixture events remain
`external.android.motion_reported.synthetic`, `EXTERNAL_UNTRUSTED`,
`SYNTHETIC_ONLY_UNQUALIFIED`, `synthetic=True`, `wake_eligible=False`, unknown
identity/evidence, no confidence and no authority. Tesla owns
`vendor_event_ingress.py`; the contract and nullable receipt-only profile were
sent directly to task `01a078d6-6fc2-7960-b735-da1940f0de53`. A constructor-only
test receiver mode is not production enablement; fixtures must never wake SENTRY.
The revised function, constant, disposition and metadata contract were agreed
directly with Tesla before the authorized production correction.

Event occurrence means Android posting, or relay receipt when posting is absent;
`timestamp_basis` explicitly distinguishes them. Camera source time remains
separate/null, as do relay/Core receipt. DBus `report_freshness` remains UNKNOWN
even when `relay_queue_freshness` is RECENT. Stale/source-clock skew is retained,
never clamped into fresh motion. Coverage is always UNKNOWN; zero reported
relay losses does not prove complete camera delivery.

Deterministic household/relay/delivery UUID identity and immutable-facts digest
support `compare_delivery`: DISTINCT / DUPLICATE / CONFLICT. Retry receipt time
does not change the digest; changed camera mapping or transport does. The caller
must persist delivery UUIDs and atomically compare before journal append, and
resume any interrupted append→wake handoff. This pure helper is not a durable
acknowledgement or exactly-once store; it cannot recognize a vendor repost given
a new delivery UUID. No raw prose is hashed or persisted by this module.
Real reports use `android-relay-report:{household}:{relay}` versus the legacy
fixture source `android-notification:{household}:{relay}`, plus distinct format
UUID namespaces. Thus journal `(source, source_event_id)` identity cannot merge
a fixture and real report even if their delivery UUIDs match.

Validation: **55 legacy fixture tests + 21 real-protocol tests using fabricated
data + 7 existing reality-substrate tests PASSED (83 total)**; scoped Ruff and
mypy PASSED. Real-protocol tests exercise production validation but are not
evidence of a real vendor notification. Live push, private-bus service,
HTTP/journal receiver and actual SENTRY delivery are NOT RUN by this worker.

## Preferred next transport: installed Waydroid private-bus sink

Read-only inspection now verifies Debian package `waydroid 1.6.2` and
`/usr/lib/waydroid/tools/services/notification_manager.py`, SHA-256
`f8e4fb9dbc74624b1f63440e580c7887a19108acda0cbe5861b2a95414ddd0ab`.
Its `notify` sets `desktop-entry` to `waydroid.` plus the Binder package name,
then calls `org.freedesktop.Notifications.Notify` on `dbus.SessionBus()`.
The paired installed `tools/interfaces/INotifications.py` was also inspected.
This supersedes the earlier no-Waydroid-installed snapshot. [Y6][Y7]

**REUSE/WRAP this bridge first**, not a new Android APK or stock Companion:
lead-owned dedicated `org.freedesktop.Notifications` sink on a private
`dbus-run-session` bus shared only with the managed Waydroid session. It must
own the notification service before Waydroid starts; source skips forwarding
if it cannot connect. No global desktop/system-bus monitoring. Validate bus
caller/session and exact `waydroid.net.ajcloud.wansviewplus` hint before text
interpretation. The hint is local bridge provenance, not cryptographic app
attestation: another process admitted to that bus can spoof it. Installed app
identity still needs official-source verification. [Y6]

Important privacy limit: Binder decoding already reads text and image bytes,
and D-Bus marshals them before the sink handles Notify. Package-first sink
filtering can prevent application parsing, retention and onward transmission,
**not all transient transport receipt/deserialization**. Ignore image data,
icons, actions, URIs and unrelated messages; never log callback arguments or
exception bodies. No media reaches Core, Journal or SENTRY. If zero transient
media receipt on the PC becomes a requirement, this existing bridge cannot
meet it unchanged. No upstream Waydroid code was modified. [Y7]

Notify exports no Android post time/channel/general group-summary flag. Do not
mislabel its `summary` text argument as Android's group-summary boolean.
Receipt time only is the safe default; extracting source time or camera alias
from text requires actual-format qualification. `replaces_id` denotes a local
replacement, not a globally durable motion identity. Sink IDs need a fresh
session namespace; immutable delivery UUIDs must survive outbound retry. A
changed replacement may be another motion report and must not be blindly
discarded. Suppression/grouping/repost behavior remains sample-gated. [D1]

Cheapest next checks: lead can implement and synthetically exercise a private
sink without reading desktop notifications, then qualify one official-app
motion sample with explicit camera mapping. Test absent/wrong package, same-app
nonmotion and summaries, repeated equal text, changed replacement and bus/sink
restart; verify no images or text reach Core/error logs. Synthetic success
still does not prove Android/headless push. No further install is performed here.

Remaining live resources: owner completes camera/app setup on the requested PC;
lead verifies installed official package/version, usable Android image/ABI,
notification permission and actual push dependencies; provide one minimized,
owner-approved motion example with its local camera alias and observed receipt
time. Qualify versioned parsing and graph mapping, reconnect/retry, sleep,
Linux logout, cold boot, and vendor-session expiry before enabling intake and
testing exact-event SENTRY receipt. No camera model, token request, phone choice
or account change is required for the isolated implementation. An existing
phone remains an optional test device, not a replacement deployment.

## Owner clarification — supersedes the initial model-first prerequisite

The owner clarified: “im not sure i need to setthem up still for now the
integration with the android app is whats needed the camera notifications go
to it”. This confirms the Android app notification path and incomplete camera
setup. It is an owner requirement, not a captured push or proof that an Android
installation currently exists. Earlier wording requiring a printed camera model
or an already receiving phone before intake work is superseded by this section.

| Confirmed requirement | Still unknown / gate |
| --- | --- |
| Capture Wansview Android app motion notifications only, with no video. | Exact installed package/version, notification channel/format and actual push receipt. |
| Design intake now; camera setup is still pending. | Camera model is optional inventory information for this route, not a design or fixture-test gate. |
| Owner selected headless PC; lead reports Android 13 x86_64 headless boot. | Official vendor app compatibility/setup, private-bus collector and real push/recovery qualification remain open. |
| ANIMA owns household events and SENTRY performs reasoning. | Live minimized capture → journal → correctly scoped SENTRY wake remains NOT RUN. |

**Hosting decision:** retain PC/headless Linux as the requested target. There is
no need to make the owner choose again between a phone and a PC merely to begin
design. An existing Android device is an optional cheaper test fixture if the
owner already has one; it is not the chosen deployment or a prerequisite. Its
existence is unknown. Switching the final deployment to a phone would require an
owner choice. The latest instruction identifies the PC as the target; runtime
and session coordination remain with the lead. No installation, account or
permission action is authorized for this worker.

## Decision and exact support status

The selected route is the **official camera app's Android motion notification →
package-scoped notification listener → minimized local event → ANIMA-owned
replaceable ingress → Journal/Truth/Attention → actual SENTRY desktop**. HA is
an optional transport for this particular app report and remains the household
substrate. Any use of its generic state adapter needs the provenance correction
below. The intake contract is independent of phone versus PC Android hosting.
This is an Android-supported observation mechanism, not a
Wansview-supported third-party event API or a guarantee of every motion event.

Stock HA Companion supplies useful relay machinery, but its current code does
not by itself satisfy strict field minimization or ANIMA's timestamp/trust
contract. A narrow normalization boundary is still required. Waydroid can host
the same Android mechanism; it does not remove these issues or create a vendor
API. Investigating its fit for the requested PC host can proceed alongside
isolated intake design; claiming working camera delivery still requires setup
and real app alerts on that host.

| Route | Support established by current primary evidence | Disposition / smallest next qualification |
| --- | --- | --- |
| Official Wansview app motion push | Owner selected this route; vendor documents app motion alerts. Camera setup is incomplete and no live receipt was observed. | **COMPOSE selected path; runtime UNQUALIFIED.** Design the intake now; qualify package and an actual motion alert after setup. Exact camera model is not a design gate. [W1][W3] |
| Public Wansview webhook/cloud event API or solar-camera email alarm export | No supported contract established in the vendor FAQ/product sources and targeted API/webhook/email search. Search absence is not proof that none exists. Legacy wired-camera manuals are not evidence for this solar model. | **REFERENCE / resource gate.** Exact model-specific documentation or a vendor statement identifying an event interface is needed before calling it supported. No private API probing or credential extraction. |
| RTSP / NVR / Blue Iris | Vendor's A1 battery FAQ explicitly rejects RTSP. This is a streaming limitation; it does not disprove app push, ONVIF Events, or another event interface. | **REJECT for this no-video workflow.** No streams, snapshots, NVR, transcoding, or camera polling. [W2] |
| ONVIF Events → HA | HA implements PullPoint subscriptions and motion topics. No evidence establishes that the owner's solar camera exposes that service. RTSP and event support must be qualified separately. | **REFERENCE conditional.** Only revisit with model-specific affirmative evidence; no generic camera setup here, which could add video entities. [H3] |
| Alexa / Google Home association | Wansview S1 page describes displaying the camera on assistant screens; this does not establish motion triggers, event subscriptions, or third-party export. | **REJECT as present evidence of a motion route.** Do not infer event support from a compatibility badge. [W4] |
| Android HA Companion Last Notification | Official documented sensor and inspected open-source implementation enforce an app allowlist and expose notification post time. | **COMPOSE for bounded qualification; WRAP/EXTEND before strict deployment** if extras cannot be minimized before transmission. [H1][H2] |
| Small Android NotificationListener bridge | Android provides posted/removed callbacks and notification identity/time metadata. A bridge can reject other packages before reading extras and serialize only agreed scalar fields. | **BUILD only if the existing relay cannot meet the measured contract.** It would need implementation and maintenance, not just permission configuration. No bridge implemented here. [A1][A2] |
| Waydroid on unattended Linux | Owner requested PC/headless Android hosting; current launcher requires a Wayland socket and no Wansview push evidence exists on Waydroid. | **REFERENCE candidate for requested hosting.** Lead coordinates host/runtime selection and later app/ABI, push, session, sleep, logout and cold-boot qualification. [Y1–Y4] |

The official Play package is `net.ajcloud.wansviewplus`, publisher AJCLOUD
INTERNATIONAL INC., listing updated 2026-08-28. This is an allowlist candidate,
not evidence that this is the app/model family the owner actually uses. If the
camera uses another vendor app, verify its official package before capture;
do not allowlist a lookalike “guide” app or every app from the publisher. [W3]

The vendor notification instructions include broad notification categories and
a recording/notification bell setting. They are evidence of the vendor path,
not authority to enable marketing, recording, or cloud storage. Observe actual
motion delivery after setup before claiming live integration. Whether the exact model permits push with recording
disabled is **UNKNOWN**. “Motion-only integration” here means no media read,
fetch, storage, forwarding, or inference by the relay/ANIMA/SENTRY; it does not
claim that the vendor camera/cloud will stop processing video once configured.
No existing camera/account settings were changed. [W1]

## Actual client implementation, not just sensor documentation

Inspected HA Android `main` at
`d3af0e4c91484b69f8a175c86d1514ea2ae2c907` (2026-09-03):
`NotificationSensorManager.kt`, `NotificationListenerSensorManager.kt`, and its
settings test file. The current paths are under `app/src/main/kotlin/`, not the
old `java/` path. This is an upstream source snapshot, not a claim about the
version installed on the eventual Android host. [H2]

1. The service forwards Android callbacks to the sensor manager. The allowlist
   defaults empty, the bypass defaults false, and the app excludes its own
   package. Keep a nonempty **Wansview-only** list and bypass disabled.
2. Last Notification exports package, `post_time`, clearable/ongoing flags,
   group, category, channel (Android 8+) and mapped notification extras. Its
   state is text, then title, then package, truncated to 255 characters. The
   manager requests `forceUpdate=true` and a sensor update after each accepted
   callback. Repeated text must not be handled with a text-change-only trigger.
3. It skips `ranker_group`, but does not generally check the Android group
   summary flag in this path. It does not explicitly export `sbn.key`, tag or
   notification ID, nor a vendor event ID. Generic group-summary deduplication
   and stable notification identity are therefore **not established**.
4. `mappedBundle` walks the selected app's extras, including nested bundles and
   arrays. There is no field allowlist here. This is not proof of media-byte
   export, but it is also not proof of text-only collection. Camera names,
   image/URI metadata and non-motion messages from the same app require an
   ingress filter. A downstream HA template cannot undo data already received
   by HA or written to its recorder.
5. The separate Active Notification Count sensor has no app allowlist. When
   enabled, its content-attribute option defaults true and iterates active
   notifications. Keep it, Last Removed Notification, media-session and other
   unrelated sensors disabled. Do not enable all sensors for troubleshooting.
6. Android grants access to the listener service, not a Wansview-only OS
   permission. The stock service obtains the active-notifications array before
   calling its manager. App filtering prevents selected export; it is not OS
   isolation from other apps. A dedicated Android device/profile with no private
   messaging apps reduces exposure; a work profile is not a safe assumed
   alternative because Android ignores listeners running in a work profile.
7. This is latest-sensor-state machinery, not an inspected durable per-camera
   event queue. Forced updates do not prove that rapid notifications, offline
   periods, or a crash preserve every callback. The inspected upstream test
   file covers setting initialization/preservation; it is not Wansview runtime
   qualification. Those tests were read, not run.

For strict minimal collection, the small bridge option must reject a nonmatching
package **before accessing extras**, avoid `getActiveNotifications()` and all
notification-history/log scraping, recognize only qualified motion messages,
and emit fixed scalar fields. No Accessibility service, screenshot/OCR,
notification interaction, `PendingIntent` execution or broad ADB/logcat capture
is needed. If vendor content is generic or ambiguous, keep it unknown rather
than guessing which camera moved. [A1][A2]

HA Android is Apache-2.0 and Waydroid is GPL-3.0 per their repository license
metadata. They remain independently maintained components; using them does not
make Wansview's proprietary app an open client/API. No public Wansview client
source, actual installed APK manifest, FCM configuration or ABI was inspected.
No APK was downloaded. Recheck installed version against the pinned source
before relying on its behavior. [H4][Y5]

## Live repository fit and missing normalization

Repository root was confirmed at the requested GVFS mount. Applicable router:
root `AGENTS.md`; repository search found no nested router. Authority and
external-discovery skills, kernel, active 026A directive and
`docs/OWNER-SENTRY-ADMIN-ROUTINES-EVENTS-2026-09-06.md` were read. The current
Notion owner amendment agrees that motion-only app relay is a candidate and
that vendor text cannot grant authority. [N1]

Observed local branch `main`, HEAD
`435815855ffda8ff917406daeb063ca498b7b9c7`; GitHub's public main commit endpoint
returned the same SHA. The working tree is dirty, including HA, intelligence,
SenseGuard, UI, tests and governance. This assessment includes the live dirty
HA source and must be reconciled by the lead if those functions change. It is
not an exact-head CI or deployed behavior claim. Only this document is writable
by this task. [G1]

Concrete integration gaps found:

- `src/anima_ha/home_assistant.py:_bounded_attributes` keeps only
  `friendly_name`, units, device/state class, icon and supported features. It
  drops Companion `post_time`, package, channel, group and camera fields.
- `normalize_state_event` uses HA `last_updated` as `observed_at`/`occurred_at`,
  records local receipt separately, and labels known HA state DIRECT with
  confidence 1.0. That is evidence of HA's sensor state, not independent proof
  of physical motion, person identity, or camera capture time.
- `context.py:PostgresContextSource._event_item` requires metadata
  `external_content_trust=EXTERNAL_UNTRUSTED` to classify event context as
  external; absent that marker it uses OBSERVED_LOCAL. The generic HA envelope
  above does not attach this marker. Its Truth context path is also marked
  OBSERVED_LOCAL. Do not let raw notification prose reach these defaults.
- `events.py:EventEnvelope` requires an aware `occurred_at`, permits source
  event IDs and metadata, and separates `recorded_at`. `journal.py` already
  deduplicates by event ID or source plus source-event ID. Reuse these contracts.
- No Wansview parser or `last_notification` integration was found in `src/` or
  tests. Existing SenseGuard routing is not evidence of a commissioned Wansview
  camera policy, camera mapping, or SENTRY wake configuration.

Recommended next implementation seam, for the lead to authorize separately:
a typed, household-bound notification ingress behind the replaceable adapter,
with a strict field schema and canonical camera mapping. If HA transports it,
the selected HA entity/event must carry minimized fields and a stable relay ID;
the ANIMA adapter must explicitly preserve that schema and set untrusted event
metadata. Do not globally broaden `_bounded_attributes` or journal the raw
Companion text state. A normalized observation can state “camera app reported
motion”; it must not state “person present” or “intruder detected.” Keep raw text
out of Truth projection; reference the untrusted journal evidence from any
derived motion-report fact. Reuse existing Journal/Attention/SENTRY request
deduplication after ingestion. No production plumbing was changed here.

## Historical development proposal — superseded by current implemented contract

Retained research rationale, not the current API or acceptance status. The
implemented contract above now requires camera mapping, uses the official
package for synthetic fixtures, and supports receipt-only Waydroid transport.
The proposed unmapped journaling and future-tense file status below are not
implemented policy.

Follow-up source inspection after the owner clarification found reusable
boundaries and one additional mismatch:

- `plugins.py:PluginManager.emit_event` validates declared event type but creates
  a fresh UUID, sets occurrence time to current time and attaches only plugin
  identity/version metadata. It cannot currently preserve a supplied relay
  delivery ID, Android posting time or the external trust marker. Calling it
  once per retry would not establish the required deduplication. Do not route
  notification intake through it unchanged or alter every plugin's behavior.
- `journal.py` returns an `AppendResult` identifying an inserted versus
  deduplicated event and its journal position. Its existing source/event-ID
  uniqueness can anchor notification delivery without another event store.
  A duplicate key does not itself verify equal payloads: the new boundary must
  reject the same delivery ID with changed normalized facts as a conflict.
- `intelligence.py:SentryAttentionBridge.run_once` now accepts a specific
  `source_event_id` with `limit=1`, filters household/source-event matches before
  loading context, validates persisted context scope and reuses durable triggers.
  This is inspected dirty-source behavior, not new live evidence from this task.
- `ui_runtime.py:_dispatch_senseguard_attention` demonstrates priming an isolated
  consumer immediately before a known journal position and selecting that exact
  event. Its source guard is SenseGuard-specific. A camera report must use its
  own typed policy/dispatch boundary; do not impersonate a SenseGuard source,
  remove that guard or reuse its profile to obtain a wake.
- Current normalized HA callbacks route to SenseGuard and automation handlers.
  There is no demonstrated Android notification ingress or camera wake policy.

**Proposed lead-coordinated development slice:** a pure Python notification
contract/normalizer plus focused tests in the existing project, with no listener
installation, external endpoint, account access, service or production wiring.
Candidate file names are `src/anima_ha/android_notifications.py` and
`tests/test_android_notifications.py`; they are suggestions for the lead, and
were not created by this task. This slice can begin without a camera model,
real package installation, phone, Waydroid or a notification sample.

1. Accept a trusted server-side relay registration and a typed, already
   minimized input. Registration binds household, relay and exact permitted
   package; empty allowlists fail closed. A test uses an explicitly synthetic
   package and household. The public Wansview package candidate must not be
   represented as a verified installation. Check package before touching text
   or extras on Android and again at ANIMA ingress. Do not accept an arbitrary
   bundle/JSON payload or raw title/body for persistence.
2. Define strict scalar fields, bounded lengths, aware timestamps, source-time
   nullability, parser version and an explicit timestamp basis using the
   contract below. Missing camera mapping stays null: a recognized report can
   be journaled against the relay with `camera_mapping=UNKNOWN`; it cannot
   become a named-room motion fact, known person or authenticated owner request.
   Actual motion recognition is a separate versioned app-format parser; do not
   invent Wansview wording or channel IDs before a sample exists. Unrecognized
   messages are ignored with content-free reason counters, not forwarded to
   SENTRY for interpretation.
3. Construct a deterministic EventEnvelope, for example proposed event type
   `external.android.motion_reported`, from household/registered relay/preserved
   relay delivery ID. Use server-owned source and trust metadata; keep original
   Android post time and receipt times distinct. Local journal observation
   establishes receipt of a vendor report only. Directly constructed envelopes
   can use the existing journal without changing generic plugin ingress or
   broadening the HA attribute allowlist. HA transport remains an optional
   separately qualified adapter, not a second authority or mandatory detour.
4. Test package rejection before a lazy extras accessor is read; reject same-app
   non-motion/unknown messages and media/URI/OTP-bearing payload fields. Test
   retries versus equal-text distinct delivery IDs, group-summary exclusion,
   changed-payload ID reuse, unknown camera/time, clock skew, ordering and
   cross-household attempts. Synthetic parser examples prove filter mechanics
   only; they must not be called Wansview notification qualification.
5. Specify the journal-to-Attention handoff with a stable policy/version and
   exact journal position/event ID. Receipt retries may resume an unfinished
   handoff under the same identity; they must not merely skip all duplicates
   after a crash between append and enqueue. Reuse durable trigger/request
   deduplication, and test recovery plus no unrelated backlog selection. For
   initial validation use in-memory/test doubles; any real-store or SENTRY
   runtime exercise is coordinated by the lead. An empty generic Attention
   profile must not silently promote every report to a guaranteed wake.
6. Keep production registration/ingress disabled until the lead wires a
   household-bound transport and a scoped notification-only wake policy. An
   unmapped camera requires an explicit report-level eligibility decision; do
   not silently drop the observation or invent resource mapping. The actual
   desktop bridge and current action/delivery policy stay lead-owned.

On Android, a strict listener would first compare package, then examine only
approved scalar fields and summary metadata; it would not enumerate active
notifications or read all extras. Schema/normalizer tests do not prove this
Android behavior. The lead can subsequently choose a narrow Companion change
or minimal listener using the already inspected client limitations. For that
step, compare the actual app format/version before enabling capture. Neither a
camera-specific SDK nor a proprietary camera model is needed for this design.

Acceptance of the proposed slice means **the host-independent intake contract
and isolated tests work**, not that Wansview pushes, headless Android or native
SENTRY delivery work. It is intentionally separate from the live-capture gate.

## Historical listener qualification fields and privacy contract

The following is the earlier listener-specific **qualification proposal**, not
the implemented schema. Use the exact current contract above, especially the
Waydroid unavailable-field rules. Unknown values remain null/unknown.

| Field | Origin / semantics |
| --- | --- |
| `schema_version`, `parser_version`, `relay_version` | Fixed implementation versions, pinned during qualification. |
| `household_id`, `relay_id`, canonical `camera_resource_id` / space | Server-bound relay registration and operator-confirmed camera mapping. Never authority supplied by notification text. Unknown camera stays unassigned. |
| `source_package`, `app_version`, approved `channel_id` | Locally verified package metadata; channel is filter evidence, not identity of a person. |
| `event_kind` | `motion_reported` only after the actual app notification format is qualified; camera model is not required. Other alerts are ignored or counted without retaining contents. |
| `vendor_event_id`, `source_occurred_at`, source timezone/precision | Optional, only when actually present and understood. A displayed relative time or timezone-free string is not a trusted UTC instant. |
| `android_posted_at` | Android `StatusBarNotification.getPostTime()`, epoch milliseconds converted to UTC; Android-host posting time, not camera time or server receipt. [A2] |
| `relay_received_at`, `ha_received_at`, `anima_recorded_at` | Separate receiver clocks; HA timestamp never substitutes silently for camera time. Record clock uncertainty and negative latency rather than clamping it. |
| `occurred_at`, `timestamp_basis` | Envelope describes notification observation. Use qualified source time if available; otherwise Android post time, then relay receipt with explicit fallback. Payload `source_occurred_at` remains null when unknown. |
| `relay_event_id`, optional notification key/tag/id, summary/update flags | Stable captured-delivery identity. Prefer local keyed digests of Android keys; do not expose device IDs or arbitrary vendor tags in model context. Stock Companion does not supply all these fields. |
| `external_content_trust`, `identity_status`, freshness/gap status | EXTERNAL_UNTRUSTED; person identity UNKNOWN; distinguish recent report, delayed report, source-time unknown, disconnected and gap-unknown. |

Deduplication must distinguish transport retries from physical events. Persist
one relay delivery ID before enqueueing; retries keep it and the same ANIMA
source-event ID. Prefer a real vendor event ID for cross-device deduplication
only if qualified. Android notification key alone can be reused for later
updates, so it is not a physical-event key. Compare qualified revision/post-time
and content digest for reposts; preserve distinct motion reports with identical
text. Keep summary/repost suppression reason and counts, without waking SENTRY
again. Do not collapse all events inside an arbitrary cooldown interval.

With stock Companion, package + post time + canonical camera + minimized
content digest can only be a provisional heuristic: missing keys, same-ms posts,
app updates and distinct post times for one event leave ambiguity. If camera or
event identity is absent, report that limitation. A removed notification is not
motion cleared. Silence is not “no motion.” Reconnection snapshots must not
replay old sensor states as fresh motion or create a burst of SENTRY requests.

Transport to HA/ANIMA must use an already authorized local destination and
household-bound identity, authenticated and encrypted where the network
boundary requires it. No public unauthenticated webhook and no new cloud relay.
No credentials, account identifiers, push tokens, private endpoints, links,
images, sounds, video, OTPs or other apps' contents enter evidence or SENTRY.
Do not dereference a notification URI or tap it. Package allowlisting alone is
insufficient because the same camera app may issue non-motion/account messages.

Only minimized event facts and delivery/status metadata belong in the journal.
Reject unknown fields and cap scalar sizes before logging or transmission. Raw
notification bundles/text are not retained. If a bridge needs a durable retry
queue, store only the minimized record, bound its size/age, acknowledge only
after journal acceptance, and expose overflow/expiry as lost-event counts.
Choose operational retention under existing household settings before enabling
it; do not silently invent a household retention policy. SENTRY gets sparse
camera/space, event times, uncertainty and current preferences through ANIMA.
Its generated response and provider acceptance are separate from actual owner
receipt. A durable journal cannot recover pushes never received upstream.

## Waydroid, push and unattended reliability

Waydroid is an Android container environment. Current
`tools/actions/session_manager.py` at
`5a51271131bfca8b7ee75ed067d09b26460f3a7b` checks for a Wayland socket and exits
when it is missing. Starting only `waydroid-container` is not the documented
complete app session. A hidden UI can be feasible while a compositor/session
runs; an unattended no-monitor deployment would need a persistent headless
Wayland compositor, correct runtime directory/session lifecycle and boot
ordering. A normal desktop logout cannot be assumed harmless. This is a
technical design inference from the source, not tested headless support. [Y1][Y4]

Official Waydroid docs describe uncertified GAPPS first boot and owner Google
account registration for Play Protect certification. They also document
`persist.waydroid.suspend`, default true on supported kernels, allowing sleep
when no apps are active. These are material prerequisites to investigate, not
instructions executed in this task. Never query the Google services database,
extract IDs, register a device, add an account or change suspend settings under
this research authorization. Compatibility with x86_64 versus an ARM-only app
build/native dependency remains unqualified; do not assume an ARM translation
layer is present or silently install one. [Y2][Y3]

Wansview's actual push provider, priority, collapse policy, token lifecycle and
direct-boot behavior are **UNKNOWN**. If the installed build uses FCM, Google's
Android prerequisites require supported Android plus Google Play services/API
environment; Android 13+ notification permission and enabled channels also
matter. Installing HA Companion, including a flavor capable of local sensor
updates, does not supply Wansview's missing push dependencies. A vanilla
Waydroid install is not evidence of working Google push. [F1]

FCM can delay delivery, expire messages and collapse queued messages. This is
a reason to test loss/recovery, not proof of Wansview's specific policy. FCM
success means accepted for delivery, not motion observed in ANIMA. Delivery
before the first Android unlock requires app and sender direct-boot support;
neither is established for Wansview. Account logout/session expiry, OS
force-stop, app process death and Linux desktop logout are distinct cases and
must be reported separately. Never claim that a reboot automatically recovers
an expired vendor login. [F2–F4]

Historical execution-host snapshot (superseded by installed 1.6.2 inspection
above): `uname -m` returned x86_64; `command -v`
found no Waydroid, ADB or Weston; targeted package query found no installed
packages for those names; `waydroid-container.service` was `LoadState=not-found`,
`ActiveState=inactive`. This is the **local Codex host**, not atlas-laptop: a
remote-mounted cwd does not make terminal commands run remotely. No remote
host package inventory, Android application data, notifications, configuration
contents, permission state or credentials were inspected. This does not rule
out a manually installed Android environment elsewhere.

Latest owner-supplied PC metadata: X11, kernel `7.0.0-31-generic`, binder_linux
available and `/dev/kvm` present. Initial absence of Waydroid was superseded by
the direct package check above; ADB/Weston/Java/AndroidSDK absence was reported
but not freshly rechecked here. Binder/KVM do not establish app ABI, a working
Wayland session or push receipt. No setup/permissions/configuration were read.

Maintenance cost includes Android/vendor app updates, parser drift, Google
services/Waydroid image changes, compositor/session supervision, clock health,
network reachability and login expiry. Track relay heartbeat independently of
last motion, but do not claim a heartbeat proves camera→vendor→push health.
Requalify after model/firmware/app/relay changes or new notification formats.
An existing supported phone could be an optional lower-complexity probe; the
requested deployment remains PC/headless Linux. A phone probe would not qualify
Waydroid, and both hosts require measured background delivery.

## Live-capture gate and exact operator resource

**No operator resource is needed to design the intake contract and isolated
tests above.** The exact camera model remains optional inventory information.
There is no model-first blocker to the owner's selected Android route.

**For actual capture:** the lead needs a designated Linux host and coordinated
Android session, verified official app package/version and Android version,
operator-completed camera/app setup, then one actual motion notification. No
such live receipt has been observed here. An existing Android phone may supply
an optional sample if available; it is not assumed to exist or substituted for
the requested PC host. A redacted text transcription plus confirmation of
package, camera-distinguishing field and any source timestamp is sufficient
initial parser evidence; no video, serial/QR, credentials or tokens are needed.
Final capture must be observed on the intended host. If a notification contains
no camera identity or source time, preserve that uncertainty. Do not request
camera model as a substitute for the missing app/session/sample evidence.

All steps below are **NOT RUN**. They are a reviewable future plan, not
authorization to install apps, enable permissions, modify accounts, restart
hosts or inject production events now.

1. **One-event check after operator setup:** on the lead-coordinated Android
   target, the operator performs one harmless motion in the camera's view after
   its configured retrigger interval; learning that interval does not require
   knowing the model in advance.
   Record the operator-observed test time separately from camera time. Observe
   only the official app's posted alert without opening it. Outcome must say
   whether package/camera/motion/source-time fields are actually available.
   No alert means diagnose the app delivery path before claiming live relay
   qualification. Isolated intake development may proceed meanwhile.
2. **Privacy/schema gate before forwarding:** on a separately authorized test
   device, verify exact package and nonempty allowlist, disable bypass and all
   broad sensors. Use a minimal listener if stock extras cannot meet the
   contract. Do not send a raw bundle to production HA “to see what happens.”
   Reject images/URIs/non-motion messages before export. Check with synthetic
   unrelated-app notifications that zero unrelated contents are read into
   relay logs, queues, HA, ANIMA or SENTRY. Reject same-app account messages too.
3. **Isolated event transport:** use a test household/ingress with no action
   effects and the approved schema. Run ten separate motion attempts spaced
   beyond the model's retrigger interval; tally attempts, vendor pushes, relay
   deliveries, unique journal rows and selected wakes independently. Trigger
   two distinct cameras if available to validate mapping. Report per-hop
   latency and losses; ten successes establish only the tested baseline.
4. **Identity/order tests:** repeated equal text, app repost/update, summary
   plus child notifications, simultaneous cameras, unknown camera, ambiguous
   source time and out-of-order arrival. Inject sanitized fixtures at the test
   ingress for cases the real app cannot reproduce; label them simulated.
   Expected: no duplicate wake for retry/summary; no suppressed distinct known
   events; unknown identity/time preserved; no stale state turned current.
5. **Android background checks:** test foreground, app background and screen
   off, then a declared overnight idle period. Record both apps' allowed
   background conditions without broad permission changes. Separately test
   short network/HA outages and rapid alerts; count unrecoverable gaps and
   ensure restored last-sensor state is not treated as a new motion event.
6. **Recovery on a disposable/operator-approved target:** test relay restart,
   app process death, explicit force-stop/manual reopen, reboot before and
   after first device unlock, and account-session expiry handling. Do not log
   out the owner's working account merely to test this; use a future approved
   expendable session or leave that check NOT RUN. Any manual recovery needed
   remains an explicit operator dependency.
7. **Requested PC/headless host qualification:** after lead coordination,
   qualify official app availability, ABI and push prerequisites alongside
   intake development; qualify actual push after camera/app setup. Then test closing its UI,
   idle beyond display timeout, desktop logout, compositor/session restart,
   host reboot with no interactive login and network recovery. Measure idle
   CPU/RAM and sleep behavior. Record each prerequisite and failed scenario;
   container running or app login alone is not unattended qualification.
8. **Lead-owned end-to-end closure:** after typed ingress implementation and
   privacy gates, observe one real motion report through ANIMA Journal/Truth,
   exact-event Attention and the existing native SENTRY desktop. Verify the
   chosen notification/TTS separately under real preferences. Record missing
   route, provider acceptance and actual receipt distinctly; no lock or other
   consequential household actions are part of this test.

Do not label this route guaranteed security sensing. Qualification can establish
observed notification delivery in declared conditions and explicit failure
visibility. It cannot establish all physical motion, camera capture time or
person identity when the source does not expose those facts.

## Primary sources and recheck triggers

All links checked during this task; moving upstream pages should be rechecked
before implementation. Vendor HTML bodies were poorly extracted by direct web
open; indexed vendor text provided the W1/W2 statements. No support claim rests
on third-party forums, affiliate guides or an API HTTP success response.

- **W1:** [Wansview motion notification setup](https://www.wansview.com/newsinfo/3195802.html), listed in the vendor FAQ dated 2026-05-27. Recheck against exact app/model menus.
- **W2:** [Wansview A1 battery RTSP FAQ](https://www.wansview.com/newsinfo/1069631.html). Streaming statement only; recheck exact hardware/firmware.
- **W3:** [Official Wansview Cloud Play listing](https://play.google.com/store/apps/details?id=net.ajcloud.wansviewplus&hl=en_US). Package/publisher and app alert feature only; recheck installed identity/version.
- **W4:** [Wansview S1](https://www.wansview.com/S1), [A1](https://wansview.com/A11Pack), [vendor FAQ](https://www.wansview.com/Support_FAQ). Product-family context, not identification of the owner's cameras.
- **H1:** [HA Companion notification sensors](https://companion.home-assistant.io/docs/core/sensors/#notification-sensors).
- **H2:** [Pinned Android listener service](https://github.com/home-assistant/android/blob/d3af0e4c91484b69f8a175c86d1514ea2ae2c907/app/src/main/kotlin/io/homeassistant/companion/android/sensors/NotificationSensorManager.kt), [sensor implementation](https://github.com/home-assistant/android/blob/d3af0e4c91484b69f8a175c86d1514ea2ae2c907/app/src/main/kotlin/io/homeassistant/companion/android/sensors/NotificationListenerSensorManager.kt), [settings tests](https://github.com/home-assistant/android/blob/d3af0e4c91484b69f8a175c86d1514ea2ae2c907/app/src/test/kotlin/io/homeassistant/companion/android/sensors/NotificationListenerSensorManagerTest.kt). Recheck when deployed Companion version changes.
- **H3:** [HA ONVIF supported event sensors](https://www.home-assistant.io/integrations/onvif/#supported-sensors), [HA integration directory](https://www.home-assistant.io/integrations/). Neither establishes this camera's support.
- **H4:** [HA Android license metadata](https://api.github.com/repos/home-assistant/android/license).
- **A1:** [Android NotificationListenerService](https://developer.android.com/reference/android/service/notification/NotificationListenerService). Service lifecycle, permissions and work-profile/low-RAM limitations.
- **A2:** [Android StatusBarNotification](https://developer.android.com/reference/android/service/notification/StatusBarNotification). Posting time and notification identity semantics.
- **Y1:** [Official Waydroid install/session instructions](https://github.com/waydroid/docs/blob/master/usage/install-on-desktops.md).
- **Y2:** [Official GAPPS certification instructions](https://github.com/waydroid/docs/blob/master/faq/google-play-certification.md). Inspected as documentation only; no identifier extraction/registration performed.
- **Y3:** [Waydroid suspend properties](https://github.com/waydroid/docs/blob/master/usage/waydroid-prop-options.md).
- **Y4:** [Pinned Waydroid session implementation](https://github.com/waydroid/waydroid/blob/5a51271131bfca8b7ee75ed067d09b26460f3a7b/tools/actions/session_manager.py). Recheck host/session behavior for any deployed release.
- **Y5:** [Waydroid license metadata](https://api.github.com/repos/waydroid/waydroid/license).
- **Y6:** [Waydroid 1.6.2 notification forwarding](https://github.com/waydroid/waydroid/blob/1.6.2/tools/services/notification_manager.py). Also directly read installed source; exact local hash recorded above.
- **Y7:** [Waydroid 1.6.2 Binder notification interface](https://github.com/waydroid/waydroid/blob/1.6.2/tools/interfaces/INotifications.py). Also directly read installed source, including image-byte decoding before Notify.
- **D1:** [Desktop Notifications D-Bus protocol](https://specifications.freedesktop.org/notification/latest/protocol.html). Notify inputs and replacement/server-ID semantics; no Android posting timestamp.
- **F1:** [FCM Android client prerequisites and notification permission](https://firebase.google.com/docs/cloud-messaging/android/get-started).
- **F2:** [FCM message lifetime/delivery semantics](https://firebase.google.com/docs/cloud-messaging/customize-messages/setting-message-lifespan).
- **F3:** [FCM collapse behavior](https://firebase.google.com/docs/cloud-messaging/customize-messages/collapsible-message-types).
- **F4:** [FCM direct boot prerequisites](https://firebase.google.com/docs/cloud-messaging/customize-messages/android-direct-boot). Conditional references; Wansview's use/configuration of FCM is unverified.
- **N1:** [Current ANIMA Notion authority](https://app.notion.com/p/3c9833cb27ff81759597cdc69c59176c), owner scope amendment at top, retrieved 2026-09-07 UTC. Only that relevant amendment supports this investigation; historical entries do not establish live camera delivery.
- **G1:** [Observed GitHub main commit](https://github.com/SketchOTP/ANIMA-Home-Automation/commit/435815855ffda8ff917406daeb063ca498b7b9c7). Local source findings include concurrent uncommitted work, not just this commit.

## CODEX RESULT — WANSVIEW-MOTION-INTEGRATION-QUALIFICATION

### Verdict

COMPLETE for the isolated ANIMA-owned report validator and qualification document.
Full camera integration remains UNQUALIFIED / WAITING_APP_SETUP.

### Retrieval confidence

ADEQUATE for the scoped implementation; UNCERTAIN for actual app delivery.

### Technical state discovered

Official app motion path documented; no supported solar event API established.
Installed Waydroid 1.6.2 exposes a reusable private-bus notification route with
receipt-only metadata. The real typed protocol validator is implemented; receiver
registration remains the source/wake gate. No vendor raw parser is implemented.

### Work performed

Inspected current primary documentation, actual Android/Waydroid client source,
relevant ANIMA contracts, Notion amendment, Git state and local package metadata.
Prepared privacy/dedup/timestamp contract and bounded operator test plan.
Applied the owner's Android-path selection, removed the model-first design gate
and identified a host-independent normalizer/test slice with exact-event SENTRY
handoff requirements. Implemented strict package-first normalization, explicit
camera mapping, separate real report and fixture entry points, two time-provenance profiles and pure
delivery comparison. Coordinated exact contract directly with Tesla. Retained
PC/headless hosting; no Android listener or D-Bus sink implemented by this worker.

### Files / areas changed

Only `src/anima_ha/android_notifications.py`,
`tests/test_android_notifications.py`, and
`docs/WANSVIEW-MOTION-INTEGRATION-QUALIFICATION.md`, all in the PC-native repo.

### Validation

- Post-approval freeze rerun: PASSED (83 tests; scoped Ruff and mypy); new source/test hashes recorded above. Requires lead rebuild.
- Android 13 x86_64 headless boot: lead-reported operational observation only; NOT RUN by this worker.
- Combined Docker build: NOT RUN by this worker; lead-owned, result not assumed.
- Static source/authority/route inspection: PASSED.
- Document scope and whitespace review: PASSED.
- Upstream Java-path lookup: FAILED (404); current Kotlin source located and read.
- Direct vendor-page body extraction: BLOCKED; indexed vendor text read instead.
- Physical camera, Android relay, Waydroid/reboot and SENTRY delivery: NOT RUN.
- Legacy fixture tests: PASSED (55); real protocol validator tests with fabricated data: PASSED (21).
- Existing reality-substrate regression tests: PASSED (7); combined 83 passed.
- Scoped Ruff check/format and mypy: PASSED. Existing unused mypy override warning only.
- Follow-up plugin/journal/Attention/SENTRY source inspection: PASSED (static only).
- Android listener, private-bus sink, HTTP/journal receiver and live SENTRY: NOT RUN by this worker.

### Evidence level

E3_TARGET_TESTED for the isolated module; E1_OBSERVED for installed/upstream
source. Adjacent tests passed; no whole-system or E5 camera evidence claimed.

### Acceptance results

- Exact status, viable route, client inspection, contract, test plan and missing resource: PASSED.
- Motion-only and three-file PC-native write scope: PASSED.
- Package-first lazy loading, strict fields, camera mapping, time/coverage uncertainty, stable delivery identity and separate real/fixture namespaces: PASSED.
- ANIMA schema validity grants no source qualification, identity, authority or wake permission: PASSED.
- Owner-selected Android route and separation of design/live gates: PASSED.
- Live capture/delivery: BLOCKED by unfinished app/camera setup and absent qualified real alert; PC target is selected, model is not an intake-design blocker.

### External discovery

REUSE/WRAP installed Waydroid forwarding with a lead-owned private-bus sink;
COMPOSE minimal Core ingress; REFERENCE model-conditional ONVIF as an
unselected alternative; REJECT video route. No strategic replacement made.

### Assumptions confirmed

Official app supports motion notifications in documented scope; HA Companion
has package filtering; ANIMA provides separate event/receipt time and dedup hooks.

### Assumptions disproven

Stock Companion plus unmodified generic ANIMA HA normalization is sufficient
for the requested provenance/privacy contract. RTSP absence does not answer
event availability. A Waydroid container alone does not establish an app session.

### New durable learnings

Current Companion maps extras and lacks general summary/stable-key export;
ANIMA filters notification provenance fields and needs explicit untrusted marking.
Installed Notify has package hint but no Android post time/channel/summary flag;
images are already decoded upstream of a private sink. A package hint alone is
not app attestation. Pure digest comparison is not durable exactly-once delivery.

### Risks / blockers

Camera setup incomplete; exact installed Android package/version unknown; no live
alert; capture-time/identity fields unknown; strict collection and loss/recovery
unqualified; headless push untested. Exact camera model is not a design gate.

### Deviations from directive

None. Required shared governance updates from the generic skills are deliberately
not performed because this task explicitly permits only the three owned files.

### Project records updated

- `.agent`: NONE, per single-writer task boundary.
- Notion: NOT UPDATED; read-only authority check.

### GitHub state

- Commit: NONE created; inspected HEAD `435815855ffda8ff917406daeb063ca498b7b9c7`.
- Branch: main, existing dirty work preserved without checkout/staging/reset.
- Push/PR state: NONE performed; owned changes are local and uncommitted.

### Recommendation to Architect

Prioritize main live SENTRY; reuse the tested isolated contract with Tesla's
bounded receiver. Lead may implement the private-bus host sink next, preserving
receipt-only provenance and transient-media caveats. Qualify official app and
actual motion format after owner setup before implementing source extraction or
enabling any producer. Use `sanitize_relay_report` for the real ANIMA protocol,
not the legacy fixture wrapper. Rebuild after both agreed code slices finish.
No phone substitution, install, account action, runtime wiring or shared
governance change was performed by this worker. Full integration remains open.
