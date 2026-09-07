# Memory: managed knowledge in the existing vault

## Operator wiring

**DEPLOYED on atlas-desktop after owner-authorized consolidation.** The accepted
vault is `/home/sketch/Documents/MEMORY` on native ext4, retaining vault ID
`541cc65b16b387fb`. Core now runs on the same PC and mounts only the `ANIMA`
subtree, mode2770 owner/group1000:1000. Its native filesystem and UID/GID
validation passed. No actual household notes were seeded. Obsidian registration
and the vault's existing settings are preserved. The laptop copy is recovery-only.
See `PC-LOCAL-CONSOLIDATION-026A.md` for deployment and current evidence limits.

The portable contract below is configuration guidance only. The owner-selected
vault is the only vault. Do not mount or scan private notes or `.obsidian`.
Only the confirmed dedicated ANIMA subtree is mounted into Core:

```yaml
# Merge into the existing service; do not replace its other mounts or groups.
environment:
  ANIMA_KNOWLEDGE_ROOT: /var/lib/anima/knowledge
  ANIMA_KNOWLEDGE_OWNER_UID: "1000"
  ANIMA_KNOWLEDGE_GROUP_ID: "1000"
volumes:
  - /home/sketch/Documents/MEMORY/ANIMA:/var/lib/anima/knowledge
group_add:
  - "1000"
```

Core runs as UID 10001. The explicit shared mode accepts an inode owned by the
runtime UID **or** configured owner UID 1000, with exact GID 1000. Directories
must be `2770`; notes and lock files must be `0660`, regular and single-linked.
The confirmed owner-owned local `2770 1000:1000` managed child satisfies this
explicit shared configuration's ownership/mode contract. The local deployment
has now also passed Core's native-access validation; remote mounts remain rejected.
Preserve any existing shared parent; do not chmod or chown it.

Both owner/group variables are required together. Omitting both retains private
`0700` directories and `0600` files. That private mode is not appropriate for the
current separate-UID Obsidian owner. Half configuration, world access, an
unconfigured owner/group, symlinks, hardlinks and remote/FUSE mounts fail closed.
Runtime storage must be native Linux. A remote SSHFS/FUSE Core mount is rejected.
If Core remains on Atlas while the accepted vault is PC-local, a native host-local
placement or separately authorized storage topology is still required; do not
silently substitute the rejected remote vault or weaken filesystem validation.

`KnowledgeConfig.from_environment()` is used by the existing runtime registration
hook. With no `ANIMA_KNOWLEDGE_ROOT`, the plugin is not registered and the UI
reports unavailable, not an empty vault. Registration validates the existing
managed root; it does not create a new vault. Core creates only trusted household
UUID directories and opaque UUID note files beneath this root.

## Owner workflow

Open **Preferences → Memory · Knowledge base**. Refresh/search and **More notes**
read household-scoped pages of at most 50. **New note** requires a title, bounded
note text and an attributed source ID plus what that source supports. There are
no seeded personal profiles or schedules. **Read** shows prose, source references,
classification and expiry; **Edit note** corrects the current version or disables
it. **Retract note** asks for confirmation and removes current prose only after
Core confirms success. Failed/denied writes retain the draft and are never
automatically replayed. Session failure clears protected dashboard state.

This is a configuration/editor form, not typed SENTRY chat. SENTRY remains
voice-only. Notes are attributed observations or SENTRY inferences, never an
explicit owner assertion, permission, proof of presence or automation. Source
references are not automatically resolved or independently verified. Do not
store secrets, restricted material or raw transcripts.

Obsidian can read these Markdown files and their JSON frontmatter in the existing
vault. ANIMA's editor is the currently verified correction workflow. Manual
Obsidian changes are **not imported automatically**: a changed digest is an
unreconciled conflict, the file is preserved and the UI explains the conflict.
Malformed metadata or permissions likewise fail closed. There is no automatic
conflict-merging or arbitrary-note import feature. Preserve an external edit
outside the managed subtree before restoring a known valid managed version;
do not claim its content has been accepted merely because Obsidian displays it.
The configured owner/group is trusted for filesystem access, not policy authority.

## API / plugin map

Every HTTP call uses the existing authenticated household identity. POSTs retain
existing Origin/CSRF and Core policy checks. No path, principal, household or
authority field can be supplied in note arguments.

| HTTP | Native tool (`anima.knowledge.*`) | Result |
| --- | --- | --- |
| `GET /api/v1/knowledge` | `list_notes` | Metadata items, stable UUID cursor |
| `GET /api/v1/knowledge/{note_id}` | `get_note` | Bounded selected content, external-untrusted |
| `POST /api/v1/knowledge/create` | `create_note` | Metadata/digest receipt |
| `POST /api/v1/knowledge/update` | `update_note` | Metadata/digest receipt; expected digest required |
| `POST /api/v1/knowledge/retract` | `retract_note` | Prose-free tombstone receipt; expected digest required |
| `POST /api/v1/knowledge/purge-expired` | `purge_expired` | Counts only |

POST body is `{ "payload": { ...tool fields... } }`. Create/update fields are
`title`, `body`, `note_type`, `classifier`, `classification`, `confidence`,
`source_refs`, optional `observed_at`, `enabled`, `retention_days`. Update adds
`note_id` and `expected_digest`; retract accepts only those two fields. Types and
bounds are in `KNOWLEDGE_MANIFEST`. Create is idempotent by server-issued
InvocationContext tool-request UUID. Browser POSTs are never retried; a fresh
explicit create is a new intent. Update/retract use digest compare-and-swap.

Note types: event/profile/preference/routine/lesson. Title: 120 characters; body:
4 KiB UTF-8. Classification: `OBSERVATION` (aware observation timestamp required)
or `SENTRY_INFERENCE`. Retention is 1–365 days, default 90 for observations;
inferences default to and are capped at 30 days. Dewey organization uses only a
small public subset with bounded local decimals, not a licensed full schedule.
The namespace is bounded to 10,000 notes including tombstones; it is not an
unbounded vault-wide index. Search checks the entire bounded household namespace,
not just its first page.

## Audit and authority boundary

The native adapter does not use MemoryService (which journals full memory
payloads). Mutation receipts contain metadata/digests, never note text/title or
source explanations. Existing PluginManager and policy intent projection avoid
raw note arguments in durable policy documents. Exact trusted native tool/source
mapping uses `POLICY_GATED_INTERNAL`, preserving—not bypassing—policy.

The embedded development AgentRuntime currently excludes the six exact knowledge
tool IDs from its advertised/allowed catalogue. Guessed knowledge invocations
follow its unknown-tool rejection path with digest-only argument projection before
turn persistence. Other tools are unaffected. This is an explicit temporary
embedded-development limitation, **not a production SENTRY tool gate**.

Production SENTRY retains these tools and receives selected reads as
`EXTERNAL_UNTRUSTED`, not retailer `EPHEMERAL_RESTRICTED` data. Existing policy
still applies: knowledge writes use `SECURITY_SECURE_ACTION`. A real owner UI
session needs an authorized authenticated role; autonomous SENTRY curation needs
the appropriate existing explicit authorization. Synthetic allow-policy tests
do not prove production grants. The current direct-SENTRY identity translation
uses `RECOGNIZED`, so commissioning must verify that route rather than silently
upgrade identity or loosen policy. No sensor event becomes admin authority.

## Retention and filesystem limitations

Expiry is applied on reads/list and explicit purge; no timed purge job is supplied.
Retraction/expiry atomically replace current files with digest tombstones, removing
body/title/source explanations. Tombstones remain for bounded receipts/idempotency.
Disabled notes stay readable as disabled and do not become permissions.

This does not erase old filesystem blocks, snapshots, backups, earlier SENTRY
transcripts or previously exported copies. No forensic erasure or blanket
forgetting claim is made. `flock` plus atomic replacement serializes cooperating
Core writers; arbitrary Obsidian writers do not participate in that lock and are
not a qualified concurrent-edit protocol. Digests detect ordinary external edits,
not malicious forgery by an already trusted filesystem owner.

## Isolated validation

Backend: `pytest tests/test_knowledge.py tests/test_knowledge_api.py tests/test_agent.py
tests/test_ui_api.py tests/test_ui_runtime.py -o addopts='' -q`.

For browser checks, build `ui/dist`, then start
`python tests/serve_knowledge_ui.py /absolute/path/to/ui/dist` on native Linux.
This test-only process clears inherited environment before importing UI code,
uses temporary native files and synthetic login/policy, prints its ephemeral
loopback port, and ends after at most 15 minutes. Set
`ANIMA_KNOWLEDGE_TEST_URL=http://127.0.0.1:<fixture-port>` (or an isolated SSH
forward to that port) and run `playwright test -c ui/playwright.knowledge.config.ts`.
Never point this write-capable synthetic journey at the owner's service.
Default H4 and specialized routine/knowledge suites use different fixtures.

The temporary-filesystem owner-replacement tests exercise actual replacement
inodes with injected runtime UID classification; they do not claim cross-UID
container/Obsidian operational proof. Final bind-mount and owner-Obsidian visibility
verification belongs to the lead's coordinated deployment.
