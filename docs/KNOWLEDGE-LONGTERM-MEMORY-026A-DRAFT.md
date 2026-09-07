# ANIMA managed long-term knowledge — backend/UI handoff draft

Scope: owner-authorized extension of the existing managed-note adapter, native
repo `/home/sketch/Projects/ANIMA Home Automation`. Vendor work remains paused.
The actual vault `/home/sketch/Documents/MEMORY/ANIMA` was not opened, written,
seeded or migrated by this worker. All note fixtures use temporary storage.

## Implemented contract

`anima.knowledge` manifest **2.0.0** retains the managed Markdown store, not a
second database or transcript archive. Native source stays
`builtin:anima_ha.knowledge`. Existing six tools remain, plus:

| Tool | Arguments / bound | Classification |
| --- | --- | --- |
| `search_notes` | Optional `query` (120 characters, at most 12 word tokens), `person_id`, `note_type`, `classification`, `limit` (1–20, default 10). Require query, person or type. | READ_ONLY, EXTERNAL_UNTRUSTED |
| `memory_index` | Optional `cursor` (canonical note UUID), `limit` (1–50). | READ_ONLY, EXTERNAL_UNTRUSTED |

Search matches all case-folded words across title/body/source claims, with
title matches ranked above other matches and note UUID as deterministic tie
breaker. It is lexical retrieval, not semantic inference or relevance proof.
Responses contain at most 320-character excerpts and three attributed source
references per hit, with source counts and explicit truncation. Both new tools
bound serialized output to 16 KiB. They scan only the locked household managed
namespace (existing limit 10,000 files, 16 KiB each); this is a bounded linear
scan, not a new persistent search engine. Large namespaces may require later
performance qualification. Search truncation means narrow the query; index
navigation has UUID pagination and derived note-type counts.

`memory_index` is a **derived in-memory navigation projection** of current
active/enabled notes, not an index Markdown file. It exposes note IDs, titles,
Dewey class, note type and profile references—not arbitrary paths. It rebuilds
on every read, so correction, disable, expiry and retraction cannot leave a
stale persistent index. No raw vault access is provided to SENTRY. `get_note`
retrieves one known managed note through the same household-bound Core path.

## Epistemic claims and references

Existing `OBSERVATION` and `SENTRY_INFERENCE` are retained. New `USER_STATED` and
`DISCOVERED` distinguish what someone reportedly said from discovered material
and inferred interpretation. `USER_STATED` requires an attributed `request`
reference; this is **not** verification that the user said it, or that the
statement is true. Source resolution/eligibility remains a Core responsibility.

`source_refs` retains strict `{kind, source_id, meaning}` objects, 1–12 per
note, bounded source IDs and explanations. Kinds now include `request`,
`tool_result`, `test`, and `external` alongside event/truth/graph/memory/note.
Tool/integration lessons can cite exact result and test-run IDs; an asserted
test result never becomes verified evidence merely because it is stored.
Nothing executes source references, fetches URLs, opens paths, or promotes
references into Truth/identity/policy. Read/search results explicitly mark
`ATTRIBUTED_UNVERIFIED`, `EXTERNAL_UNTRUSTED`, and no authority.

Optional `person_refs` holds at most eight unique nonzero canonical UUIDs.
`KnowledgeNativePlugin(..., person_validator=callback)` invokes the lead-owned
`callback(household_id: UUID, person_id: UUID) -> bool`; only exact `True`
accepts a reference. No callback means nonempty references are rejected. The
lead validates live, nonretired same-household Graph people. Person-filtered
search also checks this callback. Stored references in output are labeled
`NOT_REVALIDATED`; a prior membership check is not authentication, authority,
or proof of current profile membership. No names become identity keys.

## Retention, correction, and filesystem behavior

New notes default to `retention_days=null` / `expires_at=null` for durable
retention. Explicit retention supports 1–36,500 days, without a 30-day inference
ceiling. Retention does not raise claim confidence. Legacy finite expiry dates
are honored without migrating or rewriting files on read. Updating a note
without a retention argument preserves its existing expiry; omitted profile
references are preserved and revalidated. Passing null explicitly removes
automatic expiry. UI makes this choice visible; it no longer defaults to 30
days or silently changes retention when claim classification changes.

Existing `update_note` is the correction operation: full content plus exact
note UUID/expected digest; prior digest retained, stale writes conflict.
Retraction remains a body/title/source-free tombstone with no resurrection.
Expiry is projected without returning prose during reads; explicit
`purge_expired` (or an authorized mutation encountering expiry) persists the
tombstone. There is no background purge scheduler. Backups/old transcripts are
not erased; this is not forensic deletion or versioned prose archival.

All four read tools are now actually non-mutating: no namespace or lock
creation, pending-file deletion, or expiry writes. Existing namespaces use
shared nonblocking flock. Writes retain exclusive flock, safe native-root and
UID/GID/mode checks, no symlinks/hardlinks/special files, atomic replace/fsync,
size/count bounds and request-key/digest idempotency. Interrupted pending-file
cleanup remains on authorized writes. Same-UID arbitrary editors are outside
flock cooperation; digest mismatch fails closed, preserving their edits.

## Core and UI coordination

Lead owns Core/API registration, exact native-source checks, authenticated
request context, scoped model-write service grant and policy. Mutations remain
`SECURITY_SECURE_ACTION` / `capabilities.configure`; no fake owner principal,
role minting or blanket autonomous permission is added here. No secret or
restricted content may enter these tools. The gateway must classify inputs
**before** journaling and return note/search content ephemerally without raw
notes, query text, draft bodies or source explanations in durable tool results.
The adapter is not a semantic secret detector; metadata-only mutation receipts
do not protect arguments already logged upstream.

Lead API: `/api/v1/knowledge-search` (query/person/type/limit),
`/api/v1/knowledge-index`, `/api/v1/knowledge-status`; existing get/list/mutation
routes retained. Person options come from `/api/v1/family-routines` members.
KnowledgePanel alone was extended: relevant query/member/type filters,
null-retention editing, claim classes, optional people and multiple attributed
sources. No `main.tsx`, deployment, or owner note edits by this worker.

Status uses `agent_memory_enabled` strictly as **configuration eligibility**,
`available` as storage availability, and `writer_status=NOT_QUALIFIED` honestly.
Unknown/missing status never becomes “automatic capture enabled.” The owner
must not mistake an accessible note editor for a qualified resident writer.
Automatic selection of safe model memories remains a separately tested Core/
SENTRY integration; no bulk transcript extraction is implemented or authorized.

## Discovery and validation

EXTEND existing adapter and REFERENCE Obsidian formats; no new dependencies.
Official [properties guidance](https://obsidian.md/help/properties) supports
JSON frontmatter but notes that editing can save it as YAML; nested properties
are source-mode data. Existing JSON-only reader intentionally rejects an
externally reformatted file rather than silently importing it. Native Obsidian
editing/reconciliation remains a limitation, not a completed interoperability
claim. Official [Search](https://obsidian.md/help/plugins/search) and
[internal links](https://obsidian.md/help/links) informed bounded navigation;
SENTRY is not given Obsidian's full-vault search/path operators.

- PASSED: 113 adapter tests using temporary native storage.
- PASSED: adapter + current knowledge API tests, 119 total.
- PASSED: scoped Ruff, mypy and UI TypeScript/build.
- PASSED: final 30 browser checks across desktop/tablet/phone against the
  explicitly disposable Core/PG/OPA fixture at 18293; real note journeys plus
  declared mocked denial/status/member-option cases. Retention corrections do
  not reset expiry. Phone render inspected; no horizontal overflow in tested views.
- FAILED earlier browser attempts retained: unavailable fixture initially;
  then two new exact-label selectors failed before selection. Corrected tests
  to use the actual accessible combobox role; 27 passed, then final 30 passed
  after the retention-preservation UI fix. No acceptance assertion weakened.
- NOT RUN: owner vault writes, deployment, real resident writer, external
  source verification, production policy or whole-system acceptance by this worker.

Final shared build: `index-BjoXMKXl.js`, SHA-256
`cfc58bc67788d9a62bb2ec452138e22e640099d4ef57bb95987334465bd95d3e`, CSS
`index-BA2sqZ06.css`. Coordinated slot with Einstein; preserved its presence
mount and all main-file work. Slot released after tests; no more build planned
by this worker. Backend source SHA-256:
`f8219c1023fb0580bd815956357accd0b360f4d829c3de76114857d7f3b4fde9`.

## CODEX RESULT — scoped knowledge extension (handoff draft)

- Verdict: COMPLETE for assigned backend/UI extension and focused validation;
  no automatic production writer/deployment acceptance claimed.
- Retrieval confidence: ADEQUATE; code/legacy callers and tests inspected.
- Evidence: E4_REGRESSION_PROTECTED for scoped adapter/UI (target and existing
  regressions); no live resident memory-capture claim.
- Files: knowledge.py, test_knowledge.py, this draft, KnowledgePanel.tsx/css,
  focused knowledge.spec.ts only. Shared Core changes are lead-owned.
- State records/Notion: no edits, per explicit ownership boundary.
- Git: existing dirty/untracked work preserved; no commit/push/staging.
- Recommendation: lead completes exact Core privacy/policy and resident-writer
  qualification before deployment/enablement. This worker's source is frozen.
