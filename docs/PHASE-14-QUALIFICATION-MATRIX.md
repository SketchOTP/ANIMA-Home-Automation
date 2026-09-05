# Phase 14 qualification matrix

This is the current evidence map for `ANIMA-HA-P14-RESILIENCE-REPLAY-BACKUP-RECOVERY-016A`.
It is a consolidation record, not an acceptance declaration. `VERIFIED` means the
named software-controlled slice ran in hosted CI at the cited exact head;
`PARTIAL` means important slices passed but the family still has open required
coverage; `OPEN` means the required evidence is not yet complete. Phase 15 is
not authorized.

## Current exact evidence

| Checkpoint | Exact head | Hosted CI | Artifact |
| --- | --- | --- | --- |
| HA ambiguity/manual reality | `10830755f2f449b5c2a64b1f095f52a1fafb04d4` | `33996868220` PASS | `9978452041` |
| Policy reauthorization | `cc8b0107ca9615750a580a41fc95dcbdc3722f74` | `33998136623` PASS | `9978800620` |

## Clustered status

| Cluster | Status | Verified slices | Remaining required closure |
| --- | --- | --- | --- |
| Provider lifecycle and fencing | VERIFIED | pre-start reclaim; provider-started crash; durable result reuse; stale fence rejection; request catalogue protection | final cross-process aggregation at the closing head |
| Approval and continuation | PARTIAL | concurrent approval winner; process crash during dispatch; durable post-action result; wrong-principal rejection; policy change before reauthorization; rejection/strong-auth distinction | complete crash-window matrix and final replay at the closing head |
| HA action reality | PARTIAL | PostgreSQL lock race; verified success; possible-dispatch no-retry; manual state change after dispatch; durable action recovery | remaining vanished-resource/policy/manual races and full in-flight state breadth |
| Journal, Truth, Attention, SenseGuard | VERIFIED | duplicate event/source ID; out-of-order Truth; stale ordering; duplicate guaranteed attention/SenseGuard; projection restart | final consolidated replay at the closing head |
| Plugin isolation | VERIFIED | HA, external-read, notification classes; out-of-process child restart/failure isolation | inclusion in complete process-state matrix |
| External content and providers | PARTIAL | timeout, malformed, 5xx, partial/stale, hostile text, fake permission, secret-exfiltration text, restricted sentinel, digest-only audit | complete attack/restricted matrix with all durable-store scans |
| HA/OPA/SENTRY outage behavior | PARTIAL | OPA fail-closed; HA definite no-dispatch outage/reconnect; SENTRY bridge/provider crash and local continuity | complete ambiguous outage and in-flight restart coverage |
| Backup, restore, history | VERIFIED | actual `pg_dump`/`pg_restore` clean restore; secret scan; stale-until-reobserved physical Truth; no executed-effect replay; 250-task/250-calendar cursor traversal | final restore/replay comparison at closing head |
| Process restart matrix | PARTIAL | PostgreSQL/OPA continuity; service identity changes; plugin process restart; in-flight PostgreSQL recovery | Core/UI, SENTRY, OPA, HA, PostgreSQL, and plugin restarts across every required lifecycle state |
| ARM64 portability | PARTIAL | `linux/arm64` image build, runtime import, deterministic replay contract | deeper runtime/replay qualification; native Pi 5 remains an external gate |

## Next coherent batches

1. Finish approval/continuation and action-reality crash windows together, using
   the existing PostgreSQL stores, OPA, Phase 9 coordinator, and isolated HA.
2. Finish the in-flight process/outage matrix together, capturing process
   identities and proving local ANIMA operation while SENTRY is unavailable.
3. Run the final external/restricted-content store scan and consolidated replay,
   then rerun all required Phase 14 targets at the same closing head.

No item in this matrix authorizes a new provider, unrestricted HA administration,
embedded intelligence fallback, or Phase 15 behavior.
