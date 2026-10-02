# Stage5 owner workflow/result contracts

Source qualification only, same027A/R5F. This is not owner authentication,
deployment, provider billing, physical improvement, or whole-goal acceptance.
The canonical Coder result records exact manifests, commands and limitations.

## Existing connected vertical

| Owner workflow | Core contract and durable result | Qualification |
| --- | --- | --- |
| Tasks: create, pause, resume, cancel | Existing durable-task plugin; TaskView/TaskResult; owner GET page with next_cursor | Actual isolated PG/current OPA; browser save/reload; frozen MCP schemas |
| Calendar: create, edit, cancel | Existing calendar plugin; CalendarView/CalendarResult; expected_version CAS | Actual isolated PG/current OPA; stale edit never success; browser edit/reload/cancel |
| Preferences: shared/personal text, correction, retraction | Existing Memory/preferences plugin; PreferenceView with authority NONE; superseded history retained | Actual isolated PG/current OPA; browser correction/reload/retraction; existing private-scope regressions |
| Household interface settings | Existing presentation-only store and validation; InterfaceSettings response and partial request schema | Actual isolated PG and browser save/reload; existing routine/context/browser regressions |
| Capabilities/integration status and enable/disable | Existing registered-plugin manager; IntegrationView/IntegrationResult | Failed/unavailable enable is not promoted by successful transport; isolated PG/current OPA and browser disable/re-enable |
| Household routines and context | Existing accepted explicit-context/routine workflows retained, not rewritten | Full existing browser/PG regressions; context is not permission or observed Truth |

Owner reads use existing session authentication. Changes still require same-origin
and CSRF checks, current Core policy/household scope and existing input validation.
No direct HA frontend, raw provider access, credential display or administrator
escape was added. UI design and owner profile/personality/voice/orb are unchanged.

`owner_contracts.py` is a shared transport projection, not a second domain store.
The same finite output schemas qualify plugin results and document owner API
results. Local model references are inlined; the plugin `$ref` prohibition remains.
Extension fields are retained and absent optional fields are not fabricated.
Tasks/calendar/preferences list pages retain cursor pagination. Mutations describe
the existing envelope: status, operation, reason/policy, connector_outcome,
dispatch_state and a typed result where applicable. HTTP 200 is not verified
success. Confirmation, stronger authentication, denial, unknown and partial
states remain distinct. Unsupported operations are 404, missing sessions 401,
CSRF/origin rejection 403 and unavailable Core capability 503. Invalid settings
or page parameters retain their existing 400 diagnostics.

The integrations dynamic route also carries existing HA reconnect/ZHA payloads;
its set-enabled result is conditionally typed by exact Core operation, without
falsely imposing that schema on provider results. This is a bounded vertical,
not a replacement for every free-form OpenAPI object. Other dynamic provider
payloads retain their existing contracts and limitations.

## Dispatch, actual outcome and replay

PluginManager records BEFORE_DISPATCH for input/policy/unavailable rejections;
ACKNOWLEDGED requires a valid returned payload. Once runtime entry occurs,
malformed output or a runtime validation exception is POSSIBLY_DISPATCHED,
not proof that nothing happened. Owner/MCP projection reports UNKNOWN_RESULT
for malformed output. The existing Core KnowledgeConflict rejection remains
FAILED, with the truthful post-entry dispatch flag retained. Existing explicit
runtime failures retain FAILED as a failed-call verdict, not a no-effects claim.
For consequential actions, ActionExecutionCoordinator independently resolves
verification, partial effects, unknown outcome and replay state. An ambiguous
read without independent verification cannot fall through to successful result.

Synthetic manager/coordinator tests prove fresh matching verification, fresh
negative verification and unknown verification, followed by duplicate execution
and restart recovery without another runtime invocation. They do not prove
that duplicate physical effects occurred previously or that a device now works.

Frozen MCP binding now checks the result schema as well as the existing
plugin/version/input digest. An output-contract change is incompatible for an
already-frozen request; it is not silently substituted or replayed.

## Actual household helper usage path

The installed worker copies and launches ANIMA's
`integrations/sentry/anima-household/household_worker.py` and `codex_model.py`.
It is distinct from Stage4 SENTRY `accounted_run`; the installer already copies
these modules. This source change has not updated that installed copy.

The actual planner/final launcher emits content-free ATTEMPTED before subprocess
entry, then FINISHED with the same UUID and purpose on success, invalid output,
launch failure, timeout or provider failure. Existing service stdout/journal
is the fallback if termination or transport loss prevents a finish receipt.
An unfinished attempt remains UNKNOWN, never assumed zero or successful.

The worker sends those allowlisted receipts through the existing authenticated,
request-bound renew endpoint. Core validates the fixed metadata shape and
persists it in existing intelligence lifecycle transitions only while the
current worker/generation/lease is PROVIDER_RUNNING. Identical phase retries
are idempotent; conflicting phase metadata is rejected. A finish also requires
the matching prior attempt/purpose/model under the same fence. No new audit file,
table, credential, MCP write tool, authority or learning writer was introduced.
If acknowledgement fails before launch, the helper does not start a subprocess.
Completion metadata also accompanies the existing terminal result/failure
submission. These provider-authored summaries never grant permission or certify
physical results; count transition phases by call UUID, not again from the
terminal summary.

Only numeric, bounded token fields from one CLI turn.completed are retained.
Missing, malformed or ambiguous usage is UNKNOWN, not zero. Reported usage is
provider-reported metadata, not billing proof. Planner/final tests mock the
actual helper and run synthetic CLI-protocol children, not Codex/model turns.
Login/preflight, idle, immediate delivery and no-reasoning paths retain their
existing zero-model behavior and no-replay/provider-start fences.

## Evidence limitations

The PG role is a privileged disposable SUPERUSER/CREATEDB fixture, not production
least-privilege qualification. Browser identities are explicitly isolated test
identities; no real owner cookies/service impersonation/model/physical fixture
was used. Prospective improvement, Android Binder root permission and the
permanent goal remain open. Historical owner clock anomalies cannot be treated
as new work: parent reported four preexisting future-dated completed task runs;
the bounded restart-to-actual-now query returned zero. No historical rows or
definitions are rewritten. The earlier eight synthetic owner audit receipts
and parent append-only classification remain preserved; this Coder does not
repeat that live correction or claim project-wide/billing zero.
