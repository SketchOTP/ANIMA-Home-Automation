# Goal increment — bounded automation management

This increment gives the owner a small, usable automation surface in ANIMA
without requiring the Home Assistant frontend. It deliberately supports one
safe, typed pattern first:

```text
canonical resource state becomes ON/OFF
→ ANIMA matches an enabled household automation
→ existing semantic set_power action
→ PluginManager → OPA → ActionExecutionCoordinator
→ fresh Home Assistant observation and Phase 9 verification
```

## Owner-facing behavior

The Automations view and `/api/v1/automations` API support household-scoped,
versioned rules with:

- a bounded name;
- a commissioned ANIMA resource as the trigger;
- an `on` or `off` trigger state;
- a commissioned ANIMA power resource as the action;
- a requested `desired_on` state;
- enabled/disabled state;
- optimistic version checks for edits.

The server owns household identity, creator provenance, canonical resource
validation, and the event-to-action idempotency identity. Browser and model
input cannot provide a Home Assistant host, entity ID, service, credential, or
arbitrary automation payload.

## Authority and failure behavior

Normalized Home Assistant observations are the only trigger input. A matching
event is journaled as `automation.fired` and creates an autonomous action
request with a stable identity derived from the automation and source event.
The action then uses the existing policy, locking, latest-state precondition,
provider dispatch, refresh, and verification machinery. Connector acceptance
is not treated as physical success; verification failures and unknown results
remain authoritative.

This is not a general scheduler, YAML editor, arbitrary service-call surface,
scene replacement, or policy editor. It currently expresses one canonical
power action per rule. Rich conditions, multi-step actions, scenes, and
advanced Home Assistant automation configuration remain future bounded work.

## Evidence

Focused tests cover household isolation, commissioned-resource enforcement,
optimistic version conflicts, UTC response timestamps, autonomous provenance,
and stable event-to-action idempotency. The full repository and hosted
validation results for the implementation publication are recorded in the
active goal packet. Phase 15 remains unauthorized.
