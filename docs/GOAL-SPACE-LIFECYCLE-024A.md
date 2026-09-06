# Goal increment — room and zone lifecycle management

## Outcome

ANIMA now gives the owner a bounded lifecycle for canonical household rooms
and zones: create, rename, move, and remove. The Home Assistant frontend is
not required. These operations change ANIMA's household topology only; they
do not mutate the Home Assistant registry or provider configuration.

## Owner workflow

The Spaces view lists each place with its canonical parent. Owners can create
a room or zone under a household container, rename it, move it to another
valid container, or remove it when empty. Rename and move are separate
actions, so a failed move cannot be obscured by a successful name update.
Removal requires an explicit browser confirmation and Core still rejects
non-empty or otherwise related places.

## Authority and safety boundary

The browser supplies only the bounded semantic operation and opaque ANIMA
place identifiers. The authenticated UI API routes through the existing Core
UI gateway, PluginManager, PolicyService, and PostgreSQL graph. Core derives
household scope from the session and the graph enforces active membership,
container kinds, cycle prevention, sibling-name uniqueness, empty-place
removal, and history-preserving retirement. No raw SQL, HA identifier,
provider call, or authority field is exposed to the browser.

## Validation boundary

The increment has focused API/plugin/runtime coverage for list, create,
rename, move, and remove, including the bounded manifest and session-scoped
routes. The frontend checks the new move/remove contract and production
build. Exact full-suite and hosted validation are recorded in the completed
task packet and governance reconciliation after publication.

## Explicit limits

This increment does not add arbitrary Home Assistant administration, device
provider-registry mutation, page-builder behavior, a new persistence store,
or Phase 15 behavior. Device commissioning continues to use the existing
typed room assignment path.
