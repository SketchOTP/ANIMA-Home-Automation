# PC-local consolidation — owner operation, 2026-09-06/07

## Result and authority

The owner authorized consolidating the operational ANIMA/SENTRY installation on
`atlas-desktop`, not the laptop-backed `/srv/ATLAS` share. Source and runtime data
were copied without cleaning, resetting or overwriting either original tree.
This is an operational migration within 026A, not a new phase or goal acceptance.

## Active placement

| Component | PC-local location |
| --- | --- |
| ANIMA checkout | `/home/sketch/Projects/ANIMA Home Automation` |
| SENTRY checkout | `/home/sketch/Projects/SENTRY` |
| ANIMA UI/Core | Compose project `anima-pc`, loopback `18090` |
| PostgreSQL | `anima-pc_anima_ha_postgres_data`, loopback `55434` |
| OPA / private search | `anima-pc` containers, loopback `18181` / `18888` |
| Existing Home Assistant | unchanged local container; `/home/sketch/homeassistant-config` |
| Obsidian MEMORY | `/home/sketch/Documents/MEMORY`, existing vault ID `541cc65b16b387fb` |
| Managed notes | only `MEMORY/ANIMA` mounted into Core |
| SENTRY data/auth/session | existing PC-local home-directory state retained |
| SENTRY Core connector | local authenticated Unix socket, no SSH tunnel |

Linux host networking is used for Core only, with its HTTP listener explicitly
bound to `127.0.0.1`. Database, OPA, search and HA are reached on loopback. The
initial Docker-bridge-to-host route timed out; no firewall rule or public port
was added to work around it. HA authentication and discovery subsequently passed.

`anima-pc.service` is enabled in the desktop user service manager. Container
restart policies remain `unless-stopped`. SENTRY voice/UI/state services use the
local checkout; their old shared-storage startup dependency is removed. Existing
inactive perception/proactive services were not enabled by this migration.

## Preservation and cutover

- ANIMA source baseline: `435815855ffda8ff917406daeb063ca498b7b9c7` plus the full
  dirty/untracked 026A tree. SENTRY baseline: `5441cf35f9a08aaa8f1d2926c17672b4f105d0f7`
  plus its existing dirty work. No source commits or force pushes were made.
- Both the previous desktop database and active laptop database were backed up.
  Final laptop dump was taken after stopping its Core, then restored in one
  transaction into the separate new PC database. The former desktop database
  was not overwritten; it had zero other client connections before being stopped.
- Private migration bundle: `/home/sketch/.local/share/anima-pc-migration.8Fhbe0`.
  Contains database dumps, private connection archive and startup/config backups;
  do not publish or copy into the repository.
- Final source DB dump SHA-256:
  `64fdec5f736e8ae675a478963975fe6156a4ad4110a8e5dfdd800d92de6a0bd2`.
- Former desktop DB dump SHA-256:
  `fddfe10866c9ab0e8c51da2fc18dbf66847a2faf290f128544b5a38de4859ce5`.
- Existing five session records and canonical graph survived restore. Credentials
  were transferred privately without printing values or giving Core credentials
  to SENTRY. Only the HA connection URL changed; the token and household remained.
- Laptop ANIMA Core/database/OPA/search and old Phase14 test DB/OPA are stopped.
  SSH UI/Core tunnels and the laptop HA relay are disabled. Shared folders,
  original source trees and volume data remain intact for recovery. Other laptop
  services, including its separate Home Assistant instance, were not removed.

## Target evidence

- Local image `anima-pc-ui:owner-local` built successfully; TypeScript/Vite and
  Python package installation passed. Memory and Routines are included in that UI.
  Image manifest: `sha256:558e92d502246d816d93b9530ec397b7fb4c4b8b199088a77918e5c7cdf44a07`.
- Core health is OK, HA setup state ONLINE, authenticated HA API read HTTP200.
- Knowledge plugin native filesystem/UID/GID validation passes without writing
  a note. No household facts or schedules were seeded.
- OPA tests: 9/9. Final whole Python suite: 580 passed, six optional fixtures
  skipped; strict mypy passes across 50 source files. Catalogue-limit regression
  and prebound MCP suite: 62 passed. Local SENTRY relocation/resident suite:
  151 passed. The earlier stale launcher-string assertion failed, was corrected
  to the tested script-relative contract, and remains recorded as negative evidence.
  SENTRY reinstall now renders the active checkout path rather than restoring
  the old laptop path. Aggregate ANIMA results are in the private local test XML.
- Actual installed MCP initializes; frozen catalogue returns 64 available tools;
  request `b00c84ce-a712-519d-9835-79b142de3e1a` completes a read through local HA.
- Actual persistent SENTRY Codex/Luna turn `df62da5f-7029-4b93-ae8b-ebb2eecaca97`
  uses local source/profile/client and returns the Kitchen last-reported contact
  state honestly. ANIMA request `67ceaa11-aa70-5b66-8930-47198e3a3fce` is
  `COMPLETED / RESPONSE`, provider-start recorded. One model invocation, resumed
  existing SENTRY thread; no embedded fallback or household mutation.
- Expanded frozen schema catalogue exceeded the previous 64KiB client limit.
  Only canonical request-catalogue responses now allow 128KiB; requests and
  household context/tool-result responses retain 64KiB bounds. Oversize and
  wrong-route tests pass. Earlier failed diagnostic requests remain recorded.

## Run and rollback

```sh
cd '/home/sketch/Projects/ANIMA Home Automation'
docker compose -p anima-pc -f compose.yaml -f compose.pc.yaml config --quiet
systemctl --user start anima-pc.service
```

The private `.env` is retained with mode0600. Do not print `compose config` without
`--quiet`, because expanded configuration includes secrets. For development use
the PC-local `.venv`, linked to `/home/sketch/.venvs/anima-pc`.

Rollback must first stop all active consumers and back up any **new** PC state.
The preserved laptop database is a cutover snapshot, not a continuously updated
replica; blindly restarting it could discard newer work or create dual authority.
Restore/reconcile the selected current database before re-enabling old services.
Never run both production Cores against divergent copies.

## Remaining product limits

This proves local runtime placement and a real read, not full voice/household
completion. No microphone/TTS or physical sensor test was performed during the
migration. Browser cookie contents were not extracted; same-session browser
review is still an owner-facing check. Automatic event wake delivery, full
SENTRY write authorization, autonomous knowledge curation and Tapo/Wansview
device/app qualification remain separate open work. No new exact-head hosted CI
  or clean/pushed-tree claim applies to this uncommitted operational checkpoint.
  ANIMA, integration and SENTRY Notion roots were updated and read back with the
  PC-local deployment and the outstanding product limits.
