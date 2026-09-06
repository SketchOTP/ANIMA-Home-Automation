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
| SENTRY process lifecycle | `62533e8673a25ece7079595bd73bb3a650cb1d8c` | `33998969482` PASS | `9979026256` |
| Consolidated evidence ledger | `d68f8205787d67b2f21ea9a7bba690b3e37f145c` | `34000279143` PASS | `9979391397` (`sha256:1a45b144e9cf001aad7beeef459d5517636769f7b619a68b309cce9880f5073e`) |
| Consolidated ledger governance publication | `76453a3f38e2abfbd52dcad78f6128f97bf4af8c` | `34000794948` PASS | `9979518862` (`sha256:c4b2b2ba6e818b6ae37f7f488eddd0bfb55027007ee9e73a211e48a735d6cb17`) |
| Explicit-status ledger correction | `527810827728fc8242fbc4069b9eecb5c8060f6a` | `34001997325` PASS | `9979858475` (`sha256:c749ca63200ab46f32473e70976e107858796005cbef63153bd37ba76dc948b9`) |
| Current exact-head mapped-family ledger | `4006bcde922eb3c86c827db5700ece2ce46e98a9` | `34002634015` PASS | `9979858475` (`sha256:c749ca63200ab46f32473e70976e107858796005cbef63153bd37ba76dc948b9`) |
| Current exact-head destructive ledger | `a84d318e491e78ce5d7e7d0cdd59d2fbf74a2048` | `34003443720` PASS | `9980299813` |
| Current exact-head governance reconciliation | `2f1c45231355578f33fe737708a4c94f63596887` | `34004155779` PASS | `9980525065` |
| Latest exact-head packet reconciliation | `9c26fdc3f371cd867a925e4b1a081835fc1d1913` | `34004675040` PASS | `9980681769` |

## Clustered status

| Cluster | Status | Verified slices | Remaining required closure |
| --- | --- | --- | --- |
| Provider lifecycle and fencing | VERIFIED | pre-start reclaim; provider-started crash; durable result reuse; stale fence rejection; request catalogue protection; cross-process SENTRY lifecycle matrix | final consolidated replay at the closing head |
| Approval and continuation | PARTIAL | concurrent approval winner; process crash during dispatch; durable post-action result; wrong-principal rejection; policy change before reauthorization; rejection/strong-auth distinction | complete crash-window matrix and final replay at the closing head |
| HA action reality | PARTIAL | PostgreSQL lock race; verified success; possible-dispatch no-retry; manual state change after dispatch; durable action recovery | remaining vanished-resource/policy/manual races and full in-flight state breadth |
| Journal, Truth, Attention, SenseGuard | VERIFIED | duplicate event/source ID; out-of-order Truth; stale ordering; duplicate guaranteed attention/SenseGuard; projection restart | final consolidated replay at the closing head |
| Plugin isolation | VERIFIED | HA, external-read, notification classes; out-of-process child restart/failure isolation | inclusion in complete process-state matrix |
| External content and providers | PARTIAL | timeout, malformed, 5xx, partial/stale, hostile text, fake permission, secret-exfiltration text, restricted sentinel, digest-only audit | complete attack/restricted matrix with all durable-store scans |
| HA/OPA/SENTRY outage behavior | PARTIAL | OPA fail-closed; HA definite no-dispatch outage/reconnect; SENTRY bridge/provider crash, process-state loss, and local continuity | complete ambiguous outage and in-flight restart coverage |
| Backup, restore, history | VERIFIED | actual `pg_dump`/`pg_restore` clean restore; secret scan; stale-until-reobserved physical Truth; no executed-effect replay; 250-task/250-calendar cursor traversal | final restore/replay comparison at closing head |
| Process restart matrix | PARTIAL | PostgreSQL/OPA continuity; service identity changes; plugin process restart; in-flight PostgreSQL recovery; SENTRY child-process lifecycle boundaries | Core/UI, SENTRY, OPA, HA, PostgreSQL, and plugin restarts across every required lifecycle state |
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

## Consolidated ledger checkpoint

The exact-head hosted run `34000279143` published
`PHASE14_EVIDENCE_LEDGER` for `d68f8205787d67b2f21ea9a7bba690b3e37f145c`.
All 22 required real-store evidence files were present and every mapped
destructive slice was observed. The ledger status is `PASS` for evidence
integrity, while its disposition remains `CONTINUE`; it does not convert the
broader partial families in this matrix into Phase 14 acceptance. The five
deterministic-contract scenarios are explicitly listed as excluded from
destructive evidence. Native Pi 5 remains an external gate and Phase 15 is
unauthorized.

## Consolidated ledger governance publication

The documentation/governance publication at `76453a3f38e2abfbd52dcad78f6128f97bf4af8c`
passed exact-head hosted CI `34000794948` and published artifact `9979518862`
with digest `sha256:c4b2b2ba6e818b6ae37f7f488eddd0bfb55027007ee9e73a211e48a735d6cb17`.
This publication reconciles the current repository state with the consolidated
ledger checkpoint. It remains an integrity and coverage record with overall
disposition `CONTINUE`, not Phase 14 acceptance; Phase 15 remains unauthorized.

## Explicit-status ledger correction

The exact-head hosted run `34001997325` on
`527810827728fc8242fbc4069b9eecb5c8060f6a` passed and published artifact
`9979858475` with digest
`sha256:c749ca63200ab46f32473e70976e107858796005cbef63153bd37ba76dc948b9`.
The evidence auditor now requires every mapped scenario to carry an explicit
`PASS` or `PASSED` status. The approval ownership race was corrected to emit
that status; the ledger therefore reports all ten named evidence families as
`VERIFIED` at this head. This closes an evidence-integrity defect only. It does
not promote deterministic-contract fixtures or erase the broader lifecycle,
process-state, and final-replay breadth still tracked as `PARTIAL` above.

## Current exact-head destructive ledger

The current exact-head hosted run `34003443720` passed on
`a84d318e491e78ce5d7e7d0cdd59d2fbf74a2048` and published artifact
`9980299813`. Its evidence metadata confirms that exact tested SHA.
The evidence auditor found all 22 required real-store files, no missing files,
and no non-passing mapped scenarios; all ten mapped evidence families are
`VERIFIED` for their named exercised scenarios at this exact head. The
possible-dispatch/manual-reality and policy-reauthorization evidence is also
present in the exact-head bundle. The overall Phase 14 disposition remains
`CONTINUE`: this is evidence integrity and exercised-slice coverage, not
self-acceptance, and deterministic-contract fixtures remain excluded from
destructive proof. The broader final acceptance boundary remains tracked
below. Phase 15 remains unauthorized.

## Current exact-head governance reconciliation

The governance-only reconciliation head `2f1c45231355578f33fe737708a4c94f63596887`
passed exact-head hosted CI `34004155779` and published artifact `9980525065`.
It updates the public README, `.agent/CURRENT.md`, and this matrix to the
current Phase 14 evidence checkpoint. No runtime behavior changed. The Phase
14 evidence ledger remains `CONTINUE`, not self-acceptance; Phase 15 remains
unauthorized.

## Latest exact-head packet reconciliation

The latest governance-only packet reconciliation head
`9c26fdc3f371cd867a925e4b1a081835fc1d1913` passed exact-head hosted CI
`34004675040` and published artifact `9980681769`. It updates the active
packet/status references to the actual current repository head. No runtime
behavior changed, the Phase 14 disposition remains `CONTINUE`, and Phase 15
remains unauthorized.

## Next consolidated closure bundle

The remaining work is intentionally clustered rather than split into one
scenario per hosted run:

1. approval/continuation, action reality, and in-flight process/outage states;
2. external/restricted-content final scans plus all-scenario replay at one
   closing head;
3. ARM64 runtime/replay depth, with native Pi 5 retained as an external gate.

Each bundle must produce real-store/process evidence and preserve the overall
`CONTINUE` disposition until the Architect gate is satisfied. Phase 15 remains
unauthorized.
