# CODEX RESULT — 026A Ring and evidence-guided SENTRY initiative

## Live commissioning and owner notification policy — 2026-09-07

Home Assistant now has an accepted Ring account setup and ANIMA has commissioned
the live Front Door `Doorbell Wired` resource into the owner's `Home` household
and `Foyer` space. Current HA inventory contains the Ring doorbell and motion
event entities, including `event.front_door_ding` and
`event.front_door_motion`. Canonical provider references and Truth bindings are
active for both event capabilities.

The active owner initiative configuration is versioned in governed Memory and
sets:

```text
always_notify = [household.ring.doorbell]
proactive_enabled = false
```

This makes a fresh, qualified Ring doorbell press a required SENTRY notification
event even during the learning period and while general proactive initiative is
off. Ring motion remains available as contextual evidence and may be reasoned
about, but is not an unconditional notification type. The Ring router emits a
guaranteed canonical Attention event, the auto-wake boundary explicitly accepts
that exact source/type, and the resident SENTRY delivery path rechecks the
server-owned initiative disposition before TTS or a notification tool.

The owner chose not to perform a physical Ring press at this checkpoint. Live
Ring cloud event receipt, SENTRY model output, and speaker delivery are therefore
`NOT RUN`; setup/readiness is not presented as delivery proof. Focused ANIMA
Ring/initiative/auto-wake tests passed (with environment-gated cases skipped),
and 126 focused SENTRY autonomous-event/voice tests passed. SENTRY was observed
active in `LISTENING` with wake and VAD healthy and no pending event (`EMPTY`).

## Follow-on live product wiring — 2026-09-07

The Linux-PC resident path now has the owner-authorized unattended SENTRY
event consumer enabled for the real `Home` household. `sentry-voice.service`
is active and reports `LISTENING`, wake enabled, healthy VAD, and a reachable
ANIMA event source. No fresh eligible autonomous event was present during the
verification window, so no physical event-to-TTS delivery is claimed here.

SENTRY's voice-only onboarding guidance now executes the existing typed ANIMA
workflow for a new Zigbee presence device: bounded pairing window, spoken
operator pairing step, spoken follow-up, inventory refresh, semantic inspection,
room commissioning, and typed alert-policy creation. ANIMA remains the source
of truth and execution authority; the pairing acknowledgement is not treated
as proof of a joined device. The listener's diagnostics now preserve recorded
result and delivery status without storing response content.

Focused validation for this follow-on passed: ANIMA Ruff and HA/SenseGuard/
initiative/event-routing tests; SENTRY unittest coverage for the resident event,
always-on voice, Codex prompt, and ANIMA bridge. No hosted CI or commit is
claimed for this local dirty-tree increment.

2026-09-07. **CONTINUE — bounded UI/Core increment deployed; live Ring and
unattended SENTRY delivery remain unqualified.** Retrieval confidence ADEQUATE.
This extends the existing owner packet, not the accepted resilience phase.

## Meaningful owner capability now available

Refresh ANIMA on port 18090. Integrations contains an owner-only Ring account
setup/verification flow through Home Assistant. Preferences contains SENTRY
initiative controls: always-notify event types, a 3–14-day learning period,
optional proactive notifications, daily review and a 2–14-day routine-review
interval. Saved configuration uses existing versioned Memory and durable tasks.
No configuration or example family routine was silently seeded for the owner.

The suggestion view distinguishes inferred patterns/workflows/lessons from
owner-declared routines. Acknowledging a suggestion neither installs executable
code nor authorizes an action. Autonomous creation/installation of new tools is
not completed by this increment. Existing tools, OPA and verified execution
remain authoritative. Tapo and Wansview development remains paused.

## Ring and correlation

The adapter wraps HA 2026.9.0 Ring setup and event entities; no new cloud client,
video access, raw HA admin tool or credential transfer to SENTRY was added.
HA retains Ring account credentials. Browser setup inputs are bounded,
owner/session/CSRF scoped and cleared after submission; ambiguous setup is not
automatically retried. Exact upstream contracts and limitations are in
`RING-INTEGRATION.md`.

Canonical, source-qualified Ring motion/doorbell observations can enter the
Journal/Attention/SENTRY path. Initial snapshots, restored/pre-ready/stale events
and duplicate observations do not manufacture new arrivals. HA event receipt
time is not claimed as camera-proven physical occurrence time. Intercom unlock
can be normalized but is not in the new automatic Ring notification allowlist.

Sparse recent evidence now combines supported SenseGuard, phone connection and
Ring observations with existing preferences, routines and memory. SENTRY must
weigh freshness, contradictory signals and alternative explanations. Missing
doorbell events do not prove nobody rang; a connected phone is not authenticated
human presence; multiple dependent signals are not independent corroboration.
The Jaden/Logan examples supplied by the owner remain examples, not facts.
Attributed Tapo unlocks and future room-motion sensors are not fabricated.

## Learning and notification semantics

Optional initiative requires both sufficient source-local observation days and
receipt-local elapsed history, plus an enabled owner setting. Importing old
events today cannot unlock the gate. Defaults are a three-day observation period,
daily review, review of routines every three days, and optional initiative OFF.
Defaults are not automatically persisted or scheduled before owner save.

Review tasks use the accepted TaskDispatcher, Journal, exact Attention handling
and durable SENTRY request boundary. Their interval is anchored to configuration,
not a claimed calendar-midnight review. Only server-tagged, current-config tasks
are claimed by this runner. A dispatcher COMPLETED record means the review was
dispatched, not that a model finished reviewing. No model execution is inferred
from scheduling or eligibility. Fresh task events can be claimed once by the
opt-in auto-wake boundary; stale/backlogged work is not swept into new speech.

SENTRY can submit bounded learned suggestions through the actual frozen Core
catalogue, real OPA, request-scoped source evidence and existing Memory. Source
references are revalidated; inference cannot mint identity, permissions or
explicit owner preference. Reviews stay silent. Explicit always-notify policies
remain distinct from optional initiative. Core rechecks current delivery
permission before a notification tool and again at result submission. Withheld
speech does not rewrite an action result. Required notification with a silent
NO_ACTION result becomes PARTIAL/REQUIRED_NOTIFICATION_NOT_PRODUCED, without
forced scripted speech or automatic replay.

The SENTRY host source consumes the recorded Core result/disposition before TTS,
not its own desired result. Host tests pass, but the resident voice process was
not restarted and automatic polling was not enabled in this increment.

## Final local validation — overlapping suites are not additive

| Target | Evidence |
| --- | --- |
| Full Python | 1,094 passed; 72 explicitly opt-in skipped; zero failures |
| Ring/learning/review/initiative/autowake with real PG/OPA | 154 passed, zero skipped |
| Frozen Core → native suggestion → real OPA → PostgreSQL | passed, including authority denial and no extra write |
| Fresh review → actual PG auto-wake claim | passed once; wrong source/outcome and stale timestamp reject |
| Browser component fixtures | 42 passed, desktop/tablet/phone; synthetic Ring forms, not live login |
| Browser real PG/OPA settings | 3 passed, save/reload without invented observations |
| SENTRY host focused suite | 229 passed; not resident-model/TTS evidence |
| Ruff / strict mypy / whitespace | passed; mypy 132 source/test files |
| OPA / frontend | 9 OPA and 5 frontend unit tests; TypeScript/Vite passed |
| Container/package | Docker UI build and pip package build/install passed; live startup healthy |
| Standalone sdist/wheel command | not run successfully: local Python lacks `build`; no new dependency installed |
| Public-source safety | tracked and focused new source scans found no configured credential signatures; no exhaustive secret-discovery claim |

Final XML files are local `/tmp/anima-ring-learning-final.xml` and
`/tmp/anima-ring-learning-pg-final.xml`. Browser artifacts are under
`/tmp/anima-initiative-ring-browser-results` and
`/tmp/anima-initiative-real-core-results`. They contain isolated synthetic data,
not owner account credentials or live household events.

Negative construction findings retained: PostgreSQL ANY required array/list
parameters rather than tuple record values; runner assertions initially confused
dispatch completion with model completion and were corrected; the new full
Core test needed explicit claim-owner narrowing for strict mypy. No policy or
verification semantics were relaxed to make these tests pass.

## Deployment / source state

- Linux PC only. ANIMA base HEAD `435815855ffda8ff917406daeb063ca498b7b9c7`;
  SENTRY base HEAD `5441cf35f9a08aaa8f1d2926c17672b4f105d0f7`.
- Dirty prior owner work preserved. No commit, push, exact-head CI or hosted
  artifact was produced for this increment; this is local source/runtime evidence.
- New healthy UI image:
  `sha256:edd377d00075a45e1d43c6e30770c522f34c5b5675a58534253bd393a77c1758`.
- Previous image retained:
  `sha256:161b4feb1b3dd90835fbd73623d65be45b80fa9fbf692702ada5f0be6018e120`.
- Running Core module hashes match final local source. Root responds 200;
  anonymous initiative and Ring status routes respond 401. No active provider
  work was found before the UI-only restart.
- Household timezone America/New_York. Auto-wake flag remains absent/OFF.
- Live inventory has zero Ring entities; account setup and a real event remain
  required. Phone/router tracker commissioning is also still outstanding.
- Existing SENTRY voice service, owner credentials, actual family records and
  the PC-local MEMORY vault contents were not replaced with test data.

## Remaining owner-visible gaps

ANIMA, ANIMA↔SENTRY and SENTRY Notion records were updated and fetched again;
the new image, exact local test counts and automatic-delivery-OFF limitation
were present on all three. Authority/source reconciliation remains local; this
is not GitHub publication. Isolated browser/PG fixtures were stopped after use;
their disposable database storage was retained, not deleted.

Ring account setup and a real motion/doorbell event; actual member phone/router
assignments; Tapo/Wansview when resumed; multi-day observed learning; resident
SENTRY automatic review/event consumption and verified delivery; supported
workflow/tool installation rather than suggestions alone. No whole-goal
completion, physical arrival inference or unattended greeting is claimed.
