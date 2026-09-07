# Household context and SENTRY initiative

Owner extension, 2026-09-07 UTC. This is an in-progress, PC-local implementation
record, not a hosted-CI or whole-product completion claim. Vendor work is paused.

## Owner workflows

- Preferences: shared defaults and individual free-text exceptions, categories,
  filtering, stable pagination, correction/version checks and retraction.
- Routines: existing member profiles and expected schedules remain owner-entered
  expectations, not presence facts or scripts.
- Memory: native Markdown under the PC-local MEMORY vault's managed `ANIMA`
  namespace, source references, person links, bounded search and digest-checked
  corrections. New notes default to long-term retention; existing expiry is
  preserved unless explicitly changed. No transcript archive or synthetic owner
  profiles are seeded.
- Presence: assign a qualified, commissioned HA phone source to a member; read
  coarse, timestamped evidence. Owner UI uses canonical names/opaque handles;
  SENTRY does not receive MAC addresses, coordinates or raw HA registry options.
- Presentation: flat black, white text, purple accents; existing light/system,
  density, text scale, motion and layout preferences remain functional.

## Reasoning rather than scripts

Core supplies a bounded, live household-context guide with shared and relevant
personal preferences/routines. SENTRY retrieves additional scoped preferences,
fresh presence and relevant source-linked memory using its frozen ANIMA tools.
It decides whether to investigate, ask, notify or do nothing. A preference is
not an authorization or proof that an email/messaging integration exists.

The narrow `ANIMA_SENTRY_AGENT_MEMORY` Core grant permits only the exact builtin
knowledge mutation tools through existing OPA. It does not mint an authenticated
speaker, give household write authority to note contents, or authorize unrelated
tools. Agent notes remain attributed claims; source IDs are not automatically
proof that a statement is true. Protected product content remains excluded from
persistent SENTRY transport and memory. Raw secrets and full transcripts must
not be stored as notes.

## Presence limitations and setup

HA 2026.9.0 is running on the Linux PC. No phone `device_tracker` sources or
Companion App registrations were found at inspection. The owner must provision
phone app location permissions and/or a supported router integration before
physical arrival/departure behavior can be qualified. Phone OS and router model
are requested; no LAN scan, fabricated MAC or guessed user assignment occurs.

HA registry `options.device_tracker.associated_zone` is checked through a
private exact registry read. An omitted options object in a sparse registry
listing is not proof of a home-zone mapping. Home association is not proof of
who carries the phone. GPS and router signals can conflict, grow stale or be
unavailable. Randomized phone MACs require a stable per-network association.

Wi-Fi edges preserve actual provider timestamps and canonical resource/person
references. Initial snapshots, unknown states, stale/out-of-order data and
reconnection epochs do not manufacture arrivals. Disconnect becomes
`NOT_DETECTED`; a sleeping phone/router outage remains a possible explanation.
The new router journals deterministic events and feeds the accepted Attention
and durable SENTRY request path. Delivery is not speech: SENTRY must still
reason and choose its response. Caller retry after append/dispatch failure is
idempotent; a new background retry guarantee is not claimed.

Sources: [HA person aggregation](https://www.home-assistant.io/integrations/person/),
[Companion App location](https://companion.home-assistant.io/docs/core/location/),
[HA 2026.9 tracker implementation](https://github.com/home-assistant/core/blob/2026.9.0/homeassistant/components/device_tracker/entity.py).

## Evidence so far — not summed across overlapping suites

- Preference API: 8 pass with dedicated PostgreSQL and real OPA denial/zero effect.
- Memory agent grant: 7 pass with actual OPA and durable policy records; temporary
  Markdown create/correct succeeds without authenticated identity; disabled and
  denied grants produce no write. No resident model invocation is implied.
- Presence PostgreSQL/API: 3 pass with real Graph/Journal/Truth and OPA; HA source
  classification and login are explicitly synthetic fixtures, not phone evidence.
- Memory browser: 30 pass across desktop/tablet/phone, including source search,
  profile links, retention preservation and honest unavailable/denied outcomes.
- Preference/theme browser: 39 pass; consolidated preferences/presence: 15 pass,
  of which 9 presence checks use explicit component response fixtures.
- TypeScript, frontend unit tests (5), Vite production build and OPA (9) pass.

## PC-local foundation deployment

The household-context foundation is deployed at `http://localhost:18090/`.
The healthy UI container runs image
`sha256:161b4feb1b3dd90835fbd73623d65be45b80fa9fbf692702ada5f0be6018e120`
with `index-BjoXMKXl.js` / `index-BA2sqZ06.css`. Default appearance is night
and default accent is purple; saved alternatives remain honored. HA API access
was rechecked successfully: zero `device_tracker` entities and one HA person.
No owner profiles, schedules, preferences or notes were manufactured.

The Core memory grant is enabled and remains OPA-controlled. Automatic event
consumption and speech are **not enabled** at this checkpoint. Final integration
review found that the standalone provider server received the new auto-wake
configuration but the UI-owned Unix service constructor did not. That production
wiring is now corrected, deployed and covered through the actual OwnerBoundary
constructor, private Unix HTTP service and PostgreSQL store. Missing/blank epochs
remain disabled; enabled qualification uses only synthetic isolated Core events.

Local regression at this foundation checkpoint: 993 Python tests pass, with 47
opt-in skips; separately, 46 real PostgreSQL/OPA context/auto-wake tests pass
without skips. The presence target also passes 71 including its dedicated
PostgreSQL case. Ruff check/format, strict mypy (119 files), OPA (9), TypeScript,
frontend unit tests (5), Vite and Docker build/startup pass. Adjacent redesigned
UI regression passes 84 response-fixture cases across three viewports; it is
not physical-device evidence. Source/wheel build succeeds in a disposable
container after correcting the temporary output-directory UID mismatch.
Tracked-file credential/path scans and `git diff --check` pass.

These are uncommitted local changes on ANIMA `435815855ffda8ff917406daeb063ca498b7b9c7`,
not a new exact-head hosted-CI claim. The larger SENTRY initiative task remains
in progress until its real resident consumer is qualified and deployed.

## Where the owner can use it

1. **Routines:** add a household member and their expected schedule. Expectations
   can inform reasoning but never authenticate a person or prove their location.
2. **Preferences:** save shared text or choose a member for a personal exception;
   edit, filter and remove entries with retained provenance.
3. **Memory:** inspect/search notes, source and person links; correct with digest
   checks or retract. The vault is PC-local and the agent grant does not imply a
   note has already been written by the resident model.
4. **Routines → phone presence:** bind an available HA phone source to a member.
   This deployment currently shows setup required because no phone tracker exists.

Enter delivery wishes as context, but do not expect an email from an address
that has not been configured. A preference and a working delivery route are
separate requirements. No example addresses, quiet hours or schedules are seeded.

## Real resident SENTRY read qualification

One new, explicitly read-only host diagnostic resumed the existing SENTRY
persistent thread (no microphone or TTS). Query
`9e073555-2b99-444a-9d57-9bc9c4ea5916` mapped to ANIMA request
`18275e6c-5d2d-5a55-9fa1-dec65a7e6c11`. Durable transitions were CLAIMED,
DELIVERED_TO_PROVIDER, PROVIDER_RUNNING (04:05:25.295 UTC), then COMPLETED
(04:05:56.152 UTC), with attempt/fence 1 and result RESPONSE. One model invocation
and four observed tools were reported; the matching interval contains a real
OPA ALLOW / READ_ONLY_POLICY / capabilities.read decision. The final response
digest matches Core: `0f11d7ff77b716d1447ef6e0a34eb887f47b6226f8161dec19f1ba1b31f12b17`.
No final response prose or SENTRY transcript is copied into this evidence.

The legacy lowercase `expired` pending-authority record was left byte-for-byte
unchanged. An earlier separate diagnostic request
`314115cc-bce2-50e3-a010-f7c9b2dcd3ce` remains FAILED/PARTIAL with
provider_ambiguous=false; it was not replayed or relabeled successful. Its
underlying diagnostic limitation was not recovered from SENTRY transcripts.
The later read is separate evidence, not proof that every earlier failure is fixed.

This qualifies the real resident read/context path. It does not prove physical
phone presence, unattended memory selection, event consumption or audible delivery.

## Guided real resident memory write

The owner-authorized, no-TTS memory check resumed the same persistent SENTRY
thread and let the model choose whether a genuine tool-use lesson was worth
saving. Query `6cd7a353-b131-4599-b608-9b34e39717a6` mapped to ANIMA request
`ee7b1eb0-c73a-5ec0-8178-7e35a2e7f265`, COMPLETED/RESPONSE after provider-start,
one model invocation and five observed MCP calls. OPA recorded READ_ONLY_POLICY
for the lookup and EXPLICIT_ANIMA_SECURE_AUTONOMY for the bounded note write.
No authenticated principal was manufactured; the previous pending record stayed
unchanged. Response digest:
`9afc3a8dd3e54bd402b64ce6cd57166f35220168234a2d9d97a02f144ddd12e9`.

The actual managed vault now contains one source-linked lesson, “ANIMA knowledge
integration workflow”, note `a671490c-c452-59d2-aee3-8ae8fda9ec42`, with the
current Core request as its tool-result source and no personal references or
automatic expiry. Its observed permission is 0660, writer UID10001/sharedGID1000,
so Obsidian's local owner can read/edit it through the shared group. The lesson
concerns reading context/catalogue and searching before writing—not an invented
household fact. Note digest:
`5980a07f17d9fffd8f914a1d8ace74ba5a3066d9f0b522e2017e11755e49a459`.

This proves a **guided** real SENTRY→Core→OPA→Obsidian write. It is not evidence
that unattended event memory capture, phone arrivals, email or TTS has run.
