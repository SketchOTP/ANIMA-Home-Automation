# ANIMA owner UI workflow audit — 026A

Date: 2026-09-07

## Outcome

The owner console is organized by household outcomes rather than by backend
subsystems. Retired duplicate navigation entries are folded into the page where
an owner expects to find them. SENTRY text requests use the existing governed
conversation/provider boundary; the browser does not receive shell, Home
Assistant, database, policy, or provider credentials.

## Page map

| Page | Owner purpose | Consolidated behavior |
| --- | --- | --- |
| Home | See household state and anything needing attention | Truth, presence, weather, agenda, controls, activity, notifications, approvals, and health remain configurable widgets. |
| Devices | Find, commission, place, control, and configure alert behavior | Home Assistant devices plus commissioned Tapo/Wansview event resources share one catalogue. Each commissioned item can inherit the household default, always alert, alert during a local time window, never alert, or let SENTRY decide from the current bounded context. |
| Spaces | Manage rooms and zones | Canonical ANIMA places remain separate from provider identifiers. |
| Routines | Record household-member schedules and expectations | Family routines and presence-source assignments share one household-context page. |
| Scenes | Save and apply bounded groups of supported device states | Phase 9 terminal outcomes remain authoritative. |
| Automations | Create supported event-to-action rules | Does not expose raw Home Assistant services or arbitrary templates. |
| SENTRY | Ask for an outcome in ordinary language | Live in-memory chat queues the real SENTRY provider and its request-bound ANIMA tools. SENTRY either performs supported governed work or explains the manual step still required. |
| Alerts | Review matched events, advanced event rules, and delivery | General per-device behavior moved to Devices; this page retains advanced normalized-event rules and the server-owned notification route. |
| Tasks & Calendar | Create and manage reminders and events | Existing Core/OPA/PostgreSQL paths remain unchanged. |
| Activity | Review recorded observations and outcomes | No provider acknowledgement is promoted to physical success. |
| Users | Manage household identities and bounded SENTRY access | Phone/Wi-Fi hints remain evidence, not authentication or certain presence. |
| Connections | Connect providers and diagnose capability health | Ring, private Android vendor relays, managed integrations, and capability status are presented together. Former Capabilities and Integrations pages were removed as duplicate navigation. |
| Backups | Create and inspect restorable household records | Restore remains explicit and governed. |
| Preferences | Record household/personal guidance, initiative, and knowledge | These are context for SENTRY, not policy or physical Truth. |
| Settings | Configure this display and SENTRY voice settings | Presentation and voice configuration stay ANIMA-owned; they do not change authorization. |

## Device alert decision contract

Per-device rules are versioned inside the existing household initiative config:

```text
ALWAYS      -> a qualified event requires notification
TIME_WINDOW -> requires notification only inside household-local hours
NEVER       -> event remains recorded but does not interrupt
CONTEXTUAL  -> SENTRY may decide after learning readiness using the current
               packet, routines, preferences, presence and memory
DEFAULT     -> inherit the existing household-wide initiative behavior
```

This changes notification disposition only. It does not let SENTRY mint
identity, permission, current state, policy approval, provider success, or
physical success.

## Evidence boundaries

- `E3_TARGET_TESTED`: deterministic rule precedence/time-zone tests, event-only
  catalogue projection, frontend contract tests, and browser workflows.
- `E4_REGRESSION_PROTECTED`: requires the broader repository validation listed
  in the current 026A evidence packet.
- Live Ring/Tapo/Wansview device names come from commissioned owner records.
  Notification delivery is not claimed merely because the UI configuration is
  saved.
- The chat transcript is intentionally browser-memory-only. Reload clears it;
  durable request/result evidence remains bounded by the accepted SENTRY bridge.

## Remaining honest limits

ANIMA supports only typed capabilities already exposed through Core. The chat
does not provide arbitrary Home Assistant administration, raw shell access, or
a way to bypass OPA/Phase 9. New integrations that require account login,
physical pairing, CAPTCHA, or provider consent still require the owner for that
step; SENTRY can guide the owner without opening a raw administration backdoor.
