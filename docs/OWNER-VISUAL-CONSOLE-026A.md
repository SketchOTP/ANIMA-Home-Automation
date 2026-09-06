# Owner connection and visual console — 026A

This increment replaces the disconnected sample presentation with a commissioned
owner connection and a graphical console over the existing management plane.
It is not a claim that every Home Assistant integration or arbitrary code-editing
request is already supported. Phases 0–14 remain accepted; no new phase is opened.

## What the owner can do

| Section | Bounded workflow |
| --- | --- |
| Home | Review real inventory, room state, agenda, health, and verified controls |
| Devices | Discover, pair through ZHA, commission, name, assign, retire, and use supported controls |
| Spaces | Create, rename, move and remove empty canonical rooms/zones |
| Scenes | Compose versioned presets of supported power controls and apply through Phase 9 |
| Automations | Configure observed binary-state triggers to supported power actions |
| Alerts | Configure typed SenseGuard time-window policies and inspect matched events |
| Notifications | Configure supported notification routing; delivery is not proof of human receipt |
| Anima | Submit bounded household requests to the selected external intelligence worker |
| Tasks & Calendar | Create reminders/events, lifecycle operations, edit with version checks |
| Activity | Review journal and action outcomes without turning acknowledgements into success |
| Capabilities | See available, degraded, and unavailable capabilities |
| Integrations | Connection health/reconciliation and supported ZHA setup |
| Backups | Server-owned snapshots, integrity checks, explicit governed restore |
| Preferences | Explicit household notes through governed memory, not policy overrides |
| Settings | Appearance, density, scale, motion, display mode, widget visibility/order |

The redesigned screens use icons, compact status cards, measured values, filters,
switches and buttons. Empty or unavailable telemetry is explicitly marked;
historical charts are not fabricated. Desktop/tablet/phone portfolio screenshots
come from the actual application with synthetic data. Private owner screenshots
and runtime payloads are not published.

## Connection and authority

The explicit owner connection flow exchanges browser-bound OAuth state at the
server, verifies Home Assistant's current user is an owner, then provisions a
dedicated long-lived integration token. The short OAuth refresh grant is revoked.
The token remains in a private mode-0600 file inside ANIMA's connection volume;
it is absent from browser responses, Graph, model context and repository files.
The commissioned owner household is distinct from historical fixture topology.

The deployed HA version must match an explicit supported pin. The existing
2026.8.2 test pin is preserved; 2026.9.0 is an explicit owner-runtime alternative.
Unknown versions still fail closed. No adapter verification or policy bypass is
introduced to make connection health green.

`ANIMA_OWNER_BOUNDARY_DIR` optionally starts the existing SENTRY service with
the same UI Core. It does not start a second agent/runtime. The service owns HA,
PostgreSQL and OPA connections. Only the revocable household-scoped service-client
token and Unix endpoint reach the workstation worker. Revoked/rotated clients
are not silently re-enabled on restart. Group-writable/public boundary directories
and unsafe credential files are rejected.

## Supported Codex assistance, not unrestricted administration

The optional helper uses the installed Codex CLI with Luna/medium and existing
ChatGPT authentication. It marks provider-start before model execution and can
iterate discovery/read/operation decisions within a frozen capability catalogue.
Only registered semantic operations execute, through ANIMA. Confirmation,
stronger authentication, denial, verification failure and unknown outcomes remain
distinct. Restricted product content permits final synthesis only, not another
tool or planning round.

This helper uses ephemeral model calls and is **not** a claim of resident SENTRY
voice, persistent persona, or conversation-memory completion. New feature code,
unsupported integrations, arbitrary HA administration, raw shell and device
firmware work are not exposed as model-controlled household tools. Those remain
explicit engineering/commissioning work rather than being represented as success.

The UI surface is broader than the presently qualified Codex mutation surface.
Room lifecycle, existing task/calendar mutations, device commissioning, scenes,
and supported power/notification execution have their established Core routes.
An audit found additional management writes that the SENTRY boundary currently
rejects for lack of a trusted execution profile: automation configuration,
backup/restore, integration enablement, household preferences, alert and
notification-route configuration, and several HA maintenance operations.
Use their governed UI workflows; do not treat every visible catalogue entry as
proof that agent-assisted execution has been qualified. These gaps do not
authorize a generic administrative bypass.

## Deployment

Follow the existing local Compose/migration instructions. For a real owner, set
the server-side HA instance/base/browser URLs and exact supported version; use
the UI's explicit owner connection rather than importing sample identities.
Keep `ANIMA_HA_CONNECTION_FILE` on its private persistent volume. Never paste a
token into chat, a form, a command argument, or the repository.

Select `ANIMA_INTELLIGENCE_PROVIDER=sentry` for this owner runtime. Configure the
optional private boundary directory/socket group only for the intended operator
account. Provision the scoped client with `scripts/install_owner_worker_client.py`
over the authenticated host connection, then follow the worker runbook. Missing
worker/model access is an explicit cognition outage, not an embedded fallback.

## Evidence and limitations

Starting repository head: `11265fb6a9d84c7b4a0cf1d9dae99a570c32d7ed`.
Its CI `34063086056` failed a stale frontend login-copy assertion; that negative
result is retained. The active 026A packet records this increment's checks and
publication. The initial real Codex request completed at Core but exposed a
pre-existing ingress bug: the journal event ID overwrote the queued intelligence
request ID. The correction preserves both identities and is regression-tested.

The UI/API management support matrix is bounded. No arbitrary integration editor,
raw HA YAML/service console, voice stack, unrestricted model code execution, or
whole-goal completion is claimed. Existing sample history is preserved outside
the actual owner's household.
