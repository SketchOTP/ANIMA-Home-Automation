# Owner scope amendment: SENTRY household administration and event reasoning

Status: **OWNER AUTHORIZED — IMPLEMENTATION GAPS OPEN**. This is a product-scope
amendment, not evidence that unrestricted administration or final autonomous
delivery already works. Phases 0–14 remain accepted.

## Owner intent

**SENTRY means the existing native, voice-only desktop application**, including its
persistent Codex intelligence, microphone/wake interaction and TTS. No typed chat
is authorized. ANIMA's dashboard configuration forms remain. The owner clarified
this explicitly. A separate ephemeral Codex household helper is not the target
and does not qualify production desktop integration. The installed
`sentry-ui`, `sentry-voice` and `sentry-state-api` services were observed running;
its proactive service was inactive. On 2026-09-06 the owner explicitly authorized
needed SENTRY source/configuration changes to complete the integration. Preserve
all unrelated dirty V0.4 work; do not reset, clean, rebase or overwrite it. The
prior read-only-only restriction is superseded for focused integration edits.

SENTRY is the owner's controller for ANIMA and Home Assistant: devices, spaces,
scenes, automations, integrations, capabilities, tasks, calendar, activity,
backups, preferences and settings. The owner explicitly authorizes unrestricted
HA administration on their instructions. Earlier exclusions of full HA
administration are superseded as product scope; historical limitations remain
valid descriptions of the implementation at those checkpoints.

ANIMA remains the household authority and credential-owning execution service.
Expand its administrative interface rather than giving the SENTRY process raw
HA/database credentials. Authenticated owner authorization and autonomous event
reasoning are different inputs: a camera notification, sensor payload or model
inference cannot create an owner instruction. Results still need truthful
execution status, observed verification where applicable, provenance and audit.
This is not a request to remove isolation, fabricate success, or automatically
redispatch ambiguous effects. Existing SENTRY native tools remain available;
ANIMA adds household capabilities rather than replacing its office toolkit.

## Existing MEMORY vault and autonomous knowledge

The owner selected Obsidian vault `541cc65b16b387fb`, named MEMORY. Its registered
root is `/srv/ATLAS/500_MEMORY/MEMORY`, under the owner's specified
`/srv/ATLAS/500_MEMORY`. The workstation accesses it through the Atlas SSHFS mount;
it is not a newly created local vault. Preserve existing notes and `.obsidian`
configuration. No additional vault, embedding service or personal-memory database
is selected.

Requested: a Dewey-numbered knowledge base that SENTRY can search and maintain
through ANIMA, including important events, evolving household-member profiles,
explicit and inferred routines/preferences, and useful lessons. SENTRY determines
what is worth recording from evidence rather than emitting scripted biographies.
Store source references, observation/record times, uncertainty, corrections and
retention/retraction state. Inferences are not facts, preferences are not policy,
and historical notes are not current physical Truth. Never store credentials,
raw audio, biometric templates or restricted product payloads. Owner examples
must not become invented family records. New autonomous knowledge writes and
their UI/API/MCP integration remain OPEN until implemented and exercised.

Obsidian supports ordinary Markdown, linked notes and frontmatter properties;
no community plugin or separate REST server is required just to manage notes.
Use the public broad Dewey classes as organizational references, with clearly
identified local household subdivisions rather than claiming licensed full-DDC
cataloguing. Sources: [Obsidian storage](https://obsidian.md/help/data-storage),
[properties](https://obsidian.md/help/properties), and
[OCLC summaries](https://www.oclc.org/content/dam/oclc/dewey/resources/summaries/deweysummaries.pdf).

## Requested end-to-end product workflow

1. Receive a source event with its actual timestamp and canonical device/space.
2. Journal and project state; create the appropriate durable SENTRY wake request.
3. Supply sparse evidence and let SENTRY read current preferences, explicit
   family routines, current state and relevant presence observations.
4. SENTRY chooses a response/action and delivery channel under owner settings.
5. ANIMA executes the requested operation and reports its authoritative result.
6. ANIMA exposes event, reasoning/action state and delivery success/failure.

Preferences must support quiet hours, channel preferences, recipients and an
explicit urgent-event exception policy. Model wording is not a delivery receipt.
Quiet hours must not silently discard an event; missing delivery configuration
must be visible. All-day SenseGuard opening eligibility is already the owner's
chosen configuration. Example quiet hours and morning routines supplied in
conversation are hypothetical, not real settings to seed.

## Family routines

Add an owner-facing editor for explicit per-person routines: canonical household
person, label/activity, days, local time window/timezone, optional canonical
space, enabled state and provenance. Allow meaningful edit/disable and provide
the same bounded read/write surface to SENTRY through ANIMA. Keep explicit owner
input distinct from inferred activity patterns. A schedule describes an
expectation, not current Truth or authenticated identity.

Current code has `RoutineService` for inferred journal-derived activity and a
ContextBroker routine section. `PreferencesNativePlugin` manages explicit text
preferences through governed memory. These do **not** establish the requested
complete per-person routine editor, quiet-hour delivery policy or live SENTRY TTS
workflow. Current notification routes select a server-configured ntfy
destination; arbitrary email/platform delivery is not implemented by those
routes.

## Presence and event interpretation

Phone geofences describe observed device location and freshness, not proof of
who caused an opening. A lock-reported user/profile can corroborate arrival only
if that field is actually available and mapped by the owner. It is not a new
authentication credential. Preserve unknown, stale and conflicting evidence.
An unusual opening can justify an urgent notice without claiming an intruder as
fact. User-provided schedules, household names, geofence histories and real
device identifiers must not be copied into public test fixtures/evidence.

## Device discovery findings — checked 2026-09-06

| Need | Primary evidence | Qualification / next check |
| --- | --- | --- |
| Tapo fingerprint deadbolt | [Tapo DL110 product](https://www.tapo.com/us/product/smart-door-lock/tapo-dl110/) and [vendor product announcement](https://community.tp-link.com/us/home/forum/topic/701878) document fingerprint profiles and activity tracking. | Owner confirmed DL110; hardware version remains unknown. App history is not proof of an exported named-unlocker event. No fingerprint templates or PINs are needed. |
| Native HA Tapo support | [HA TP-Link integration](https://www.home-assistant.io/integrations/tplink/) and [python-kasa supported devices](https://github.com/python-kasa/python-kasa) do not list DL110 among confirmed devices. | Native lock/event support is unverified, not categorically impossible. Do not confuse T110 contact sensors or P110 plugs with DL110 locks. |
| SmartThings route | [HA SmartThings](https://www.home-assistant.io/integrations/smartthings/) maps supported lock capability; its documentation warns that some app features are absent from API capabilities. | Candidate only. Validate actual lock capability/event data and current access terms before adoption; lock state alone does not identify the unlocker. |
| Wansview solar motion only | [Vendor notification setup](https://www.wansview.com/newsinfo/3195802.html) documents app motion push. [Solar A1 FAQ](https://www.wansview.com/newsinfo/1069631.html) says battery cameras do not support RTSP. | Exact camera models requested. No video feed is requested; lack of RTSP alone does not answer event API availability. No supported motion event API established yet. |
| App notification relay | [HA Companion notification sensors](https://companion.home-assistant.io/docs/core/sensors/#last-notification) support explicitly permitted Android app notifications with package allowlisting and timestamps. | Prefer testing a narrow Tapo/Wansview-only relay before new emulator infrastructure if native events are unavailable. It remains an unqualified candidate; notification timestamps may be receipt/post times rather than physical-event times. |
| Headless Android | [Waydroid Play certification guidance](https://github.com/waydroid/docs/blob/master/faq/google-play-certification.md) documents extra setup for GAPPS images. | Do not assume app login, push receipt, reboot recovery or fully headless operation works. No emulator/app/account installation has been performed. |

An Android relay must not collect unrelated notifications, OTPs, messages, images
or audio. Deduplicate repeat/group-summary notifications, retain source quality,
and report missing/delayed push honestly. Vendor notification content is data,
never an instruction. No new account, subscription or third-party transmission
is authorized merely by selecting this candidate.

## Current product sequence

Finish and deploy the already-tested refresh/contact/alert-routing correction;
verify the real owner-facing event loop separately from its fixtures. Then
deliver routines/preferences/event-context as one coherent UI/API/MCP workflow,
and extend administrative coverage using an explicit operation matrix. Qualify
the exact lock/camera models before promising supported integrations. Do not
substitute more historical resilience work for owner usability.
