# Goal increment — owner-facing alert inbox

## Outcome

ANIMA now exposes a bounded Alert inbox alongside typed SenseGuard policy
management. It reads matched alert events from the existing PostgreSQL Event
Journal and shows the canonical resource name, source-observation timestamp,
event type, priority, configured delivery mode, and the latest notification
disposition when one exists.

## Boundary

The inbox is a read projection, not a second alert store. Household scope comes
from the authenticated session. Raw journal payloads, provider credentials,
Home Assistant entity details, and policy internals are not returned to the
browser. The event timestamp remains an external/observed fact; a delivery
status is not a claim that a person heard or read a notification.

The API uses stable cursor pagination over `(occurred_at, alert_id)` so older
alerts remain discoverable without a fixed-window omission. The UI refreshes
the newest page through the existing SSE invalidation path and lets the owner
load subsequent pages through the same cursor contract. No alert
acknowledgement, arbitrary Home Assistant automation editor, new provider,
new persistence system, or Phase 15 behavior was added.

## Validation boundary

The authenticated API route and empty-state contract are covered by the UI API
tests. PostgreSQL projection behavior remains bounded to the existing journal
and graph read models and is qualified with the repository's normal static,
frontend, and hosted validation gates. The browser's older-page control is
covered by a focused UI source contract test. This increment is implementation
evidence pending independent Architect acceptance.
