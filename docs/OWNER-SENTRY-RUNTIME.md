# SENTRY household worker: owner startup and resource state

This is SENTRY's bounded household worker, using the existing installed Codex
CLI with `gpt-5.6-luna` and medium reasoning. It is not an additional persona,
an embedded ANIMA agent, or a replacement for the protected SENTRY resident
process. The resident SENTRY source and configuration are not modified.

ANIMA UI queues the user's request. The worker claims through the existing
authenticated Core client, loads the sparse context and exact request catalogue,
marks provider start, asks Codex for bounded plans, invokes only catalogue
operations through ANIMA, and feeds each round's exact results into the next
planning round before final synthesis. Setup
and troubleshooting work only for capabilities already registered in that
request. The worker cannot install arbitrary packages, edit code, configure
arbitrary devices, operate a browser, or execute model-generated shell commands.

The Codex adapter supports an explicit optional `plan_round` interface:
discovery → read result → reason → choose the next semantic operation, with
**at most three planning rounds and eight cumulative tool calls**. Each round
may select at most three independent calls; the last round is reduced to the
remaining cumulative budget. Dependent calls belong in a later round, after
the canonical IDs and observations they need have actually been returned.
An empty plan requests final synthesis. Existing models implementing only
`plan`/`final` retain their one-plan behavior.

**Identity/qualification limitation:** this ephemeral Codex CLI helper is
**NOT resident SENTRY voice or persistent persona completion**. The worker process is
persistent, but each model call is a separate ephemeral session receiving only
its supplied context/results; it has no resident SENTRY conversation memory or
persona continuity. Integration into the protected persistent SENTRY host is
not claimed and that architecture remains unchanged.

The existing client/provider wire contract carries bounded iterative work:
multiple `/invoke` calls share the same request binding and catalogue, with
monotonically increasing ordinals. There is no wire-schema change needed for
host-side replanning. The worker carries prior arguments, results and host-owned
ordinals in volatile context. It freezes the catalogue once, passes defensive
copies to each model call, validates every round before its first invocation,
and never resets or accepts model-selected ordinals. A turn object cannot run
twice. Budget stops are reported as `PARTIAL`, not full completion.

The worker sets a **270-second deadline starting before claim**, reserves the
last 100 seconds for final synthesis/delivery, and gives final model output a
cutoff 15 seconds before that deadline. Model subprocess deadlines are clamped
to the remaining phase time regardless of `--model-timeout`. A planning phase
deadline terminates that process and switches to final without retrying the
plan. Short client timeouts and the remaining margin preserve the binding
boundary. The current binding expires after **five minutes**, independently of
the **120-second renewable lease**. The Core SENTRY boundary does not currently
expose an iterative model loop or enforce the AgentRuntime's restricted-content
episode latch. This host stops immediately after a catalogue operation marked
`EPHEMERAL_RESTRICTED` and permits only final synthesis. Do not import or activate
embedded AgentRuntime as an implicit replacement for SENTRY.

## Current resource state: 2026-09-06

- Workstation: `/usr/lib/chatgpt/resources/codex`, CLI `0.153.4`.
- `codex login status`: `Logged in using ChatGPT`. Token files were not read.
- Real, synthetic, no-tools `gpt-5.6-luna` auth smoke: **PASSED** through this
  worker's final parser, reporting `MODEL_AUTH_OBSERVED`. This establishes model
  access for that invocation, not permanent account health or household operation.
- Laptop: `codex` is not available on the inspected noninteractive SSH PATH.
  Use the authenticated workstation for the worker; do not move/copy Codex tokens.
- Core service/client commissioning and the first owner UI request were run by
  the main agent. Request `086b964a-a023-56df-bf8a-736ce45e6a04` reached durable
  `COMPLETED / RESPONSE`; initial browser reply delivery **FAILED**. This is not
  a UI acceptance pass for that request; its negative evidence is retained.
- Main subsequently reports real UI → Codex → Core read → browser **PASSED**
  for `b9c5b3ec-0fef-56c7-9b33-9bd40a454f6a`: `COMPLETED`, provider started,
  correct four-room result and SenseGuards manufacturer, and correct distinction
  between an HA Bedroom area and a missing ANIMA Bedroom room. This is the main
  agent's operational read proof, not physical-action or resident-persona proof.
- The subsequent conditional room-create request
  `b89d05af-d8ad-57bb-aad4-d2d83fe8381d` stopped `UNKNOWN_RESULT` with
  `ANIMA_TURN_UNAVAILABLE`; worker session `77049` exited `2`. Main verified no
  Bedroom in the graph. Preserve ambiguity: absence of a room does not recover
  the lost exception or prove all intermediate operations. **Never replay or
  automatically retry this request.** Main owns separate UI commissioning and
  any fresh owner-requested attempt after checking current state.
- Backend OAuth and server connection secrets remain in the lead's Core boundary.
  Neither is a worker credential or environment variable. Physical-device and
  unattended-operation qualification are not claimed here.

## Required resources and ownership

1. ANIMA Core service and its Attention/UI queue path must be running on the
   laptop and share the existing household/store. Core owns the database, OPA,
   HA integration and backend OAuth/connection secrets. The existing service CLI
   listens on a Unix socket (`--socket`); this worker does not add an HTTP server.
2. Core must register one enabled household-scoped service principal with
   `provider_id=sentry`, a client ID and credential generation. The registration
   and household are server-owned; the worker cannot select a household or role.
3. Provision only that service's revocable client token to a private regular file
   readable by the workstation worker account (mode `0600`, not a symlink).
   This token authorizes bounded Core client requests. It is not an HA token,
   database connection, OAuth token or Core administrative credential. Deliver it
   through the lead's secret provisioning mechanism, never browser/chat text.
4. Forward the laptop Core Unix socket to the workstation, or use an already
   commissioned compatible loopback HTTP/TLS origin. Plain HTTP off loopback,
   redirects and environment proxy forwarding are rejected by this client.
5. The workstation account needs its existing Codex ChatGPT login, executable on
   PATH, Linux/Python 3.12, and `jsonschema` (the project pins `4.26.0`). The worker
   has no ANIMA package, MCP server, database-driver or HA dependency. The existing
   workstation `python3` has `jsonschema` and was used for the live smoke.
6. Keep the authenticated UI connected while a result is delivered: Core's live
   response channel is intentionally transient. Durable queue state stores status
   and digests, not a transcript. A missed live response must remain unavailable.

The laptop UI and workstation HA reverse tunnel are separate from this path:
the worker talks only to laptop Core. The HA endpoint and connection secret stay
behind Core, even if Core reaches HA through a reverse tunnel.

## Commissioned workstation paths and commands

The main agent deployed Core sharing the UI's Core instance and established an
authenticated household-scoped Unix-socket connection through SSH. The known
workstation endpoint is `/run/user/1000/anima-household-owner.sock` (socket,
mode `0600`). Its client credential is
`/home/sketch/.local/share/anima-household-client/client.token` (regular file,
mode `0600`); only the path and mode were inspected in this audit, never the
token contents. Worker label: `sentry-household-workstation`.

Use the already commissioned SSH tunnel; do not create another forward over
the live socket or infer a laptop/container-side socket path from the local
path. The main agent owns tunnel/service lifecycle. Commands below are operator
references and are not instructions to start a duplicate running worker.

From the mounted ANIMA checkout on the workstation:

```bash
cd '/run/user/1000/gvfs/sftp:host=atlas-laptop/srv/ATLAS/100_ACTIVE/Projects/ANIMA Home Automation'
codex login status
python3 scripts/run_sentry_household_worker.py --auth-smoke
```

The optional smoke sends one synthetic no-tools question to the model, without
reading Core, queuing household work or invoking any device.

Run the following check with an explicitly minimal environment. `HOME` and
`CODEX_HOME` below preserve the inspected workstation login location; no auth
files are copied or inspected. There is no Core secret environment to inherit:

```bash
env -i PATH=/usr/lib/chatgpt/resources:/usr/bin:/bin \
  HOME=/home/sketch CODEX_HOME=/home/sketch/.codex LANG=C.UTF-8 \
  ANIMA_SENTRY_ENDPOINT=/run/user/1000/anima-household-owner.sock \
  ANIMA_SENTRY_CLIENT_TOKEN_FILE=/home/sketch/.local/share/anima-household-client/client.token \
  ANIMA_SENTRY_WORKER_ID=sentry-household-workstation \
  python3 scripts/run_sentry_household_worker.py --check
```

After `READY`, start the persistent foreground worker with the same command and
remove `--check`:

```bash
env -i PATH=/usr/lib/chatgpt/resources:/usr/bin:/bin \
  HOME=/home/sketch CODEX_HOME=/home/sketch/.codex LANG=C.UTF-8 \
  ANIMA_SENTRY_ENDPOINT=/run/user/1000/anima-household-owner.sock \
  ANIMA_SENTRY_CLIENT_TOKEN_FILE=/home/sketch/.local/share/anima-household-client/client.token \
  ANIMA_SENTRY_WORKER_ID=sentry-household-workstation \
  python3 scripts/run_sentry_household_worker.py --poll-seconds 2 --model-timeout 90
```

`--once` consumes at most one queued request and may dispatch
real governed catalogue operations; it is **not** an auth smoke or a dry run.
Default polling is two seconds; default model deadline is 90 seconds per call.
Ctrl-C/SIGTERM stops polling and cancels an active Codex subprocess.

The owner deployment now installs the four client/worker modules into
`/home/sketch/.local/share/anima-household-client/runtime` outside protected
SENTRY. The workstation uses user services `anima-household-worker.service`,
`anima-owner-core-tunnel.service` and `anima-owner-network.service`; the laptop
uses `anima-owner-ha-relay.service`. The helper has `Restart=no`: a failed turn
requires inspecting its safe diagnostic and Core status before manual restart.
The transport-only services may reconnect without replaying model/tool work.
The workstation system Python's inspected jsonschema version is 4.10.3; the
repository validation uses its locked dependency environment. Service startup
qualification and model/operation qualification are separate evidence claims.

Inspect service state without exposing credentials:

```bash
systemctl --user status anima-household-worker.service
systemctl --user status anima-owner-core-tunnel.service anima-owner-network.service
journalctl --user -u anima-household-worker.service -n 20 --no-pager
```

If a supervisor is later commissioned, do not use blind restart-on-failure:
exit `2` requires inspecting the fixed diagnostic and Core request status before
operator restart. `--check` reads auth status and Core health without claims;
it does not prove model access. `--auth-smoke` is the explicit model access check.

## Failure, policy and privacy behavior

- Only Core can claim safe SENTRY work for the registered household. A fresh
  correlation ID is used for each poll; no client queue, resume file or replay
  path is introduced. Auth unavailable before a claim stops the worker.
- Provider start must succeed before any model call. Active Codex calls check
  their lease at most every 20 seconds and terminate on renewal failure or
  shutdown. Core's existing lease is 120 seconds; client HTTP timeout is 10
  seconds. No background thread renews an idle or abandoned request. Tool calls
  are bounded client operations with lease checks between stages.
- A round has at most three independent calls, with at most eight calls and
  three rounds cumulatively, all locally validated against the
  exact request catalogue and Core input schemas before the first invocation.
  No remote schema references are resolved. Core still revalidates identity,
  catalogue, policy, fencing and execution at every invocation.
- Further planning and calls stop at the first non-success or an
  `EPHEMERAL_RESTRICTED` result, allowing only final synthesis. Confirmation, stronger authentication,
  denial, unavailable and unknown outcomes remain distinct; Codex does not
  approve its own proposed action or turn acknowledgement into physical success.
- Timeout, lease loss, malformed output and uncertain delivery stop the worker.
  At most one best-effort terminal failure submission is attempted. If that
  fails, Core lease expiry handles ambiguity. No model/tool/result request is
  automatically replayed by this host. Codex's internal transport behavior
  remains its own implementation; unbounded CLI connection retries are disabled
  and the host enforces the overall call deadline.
- The child receives only an allowlisted login/runtime environment. It receives
  neither the Core client token nor DB, OPA, HA or API-key environment values.
  User config, repository instructions/rules, plugins, apps, shell, browser,
  computer tools, image tools, hooks and memory are disabled. The working
  directory is empty and ephemeral; even the output schema is held in a Linux
  memory file descriptor. CLI session/history persistence is disabled, logging
  is off, stdout/stderr are bounded in memory, and worker stdout contains fixed
  status/error codes only. No request, response, tool result or transcript is
  written by the host adapter. Provider-side retention is outside this local
  persistence claim.
- The parser admits exactly one completed structured model message. Installed
  CLI `0.153.4` emits one known pre-turn warning when Code Mode is deliberately
  disabled; only that exact warning is accepted. Unknown errors/capability
  events remain failures.

## Implementation evidence and handoff

The implementation reuses `SentryHouseholdTurn` and `AnimaHouseholdClient` and
adapts the existing `CodexCliRuntime` isolation/JSONL/process-bound pattern
without importing ANIMA Core. Protected SENTRY's ephemeral bridge was inspected
read-only; its resident agent persists a thread and exposes broader host tools,
so it is not loaded into this bounded worker. Official
[noninteractive CLI guidance](https://learn.chatgpt.com/docs/non-interactive-mode)
and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
were checked against the installed CLI. No model/provider substitution is made.

The first synthetic attempt failed because CLI `0.153.4` disallows overriding
the built-in OpenAI provider retry configuration; those overrides were removed.
Subsequent diagnostics exposed the disabled-capability startup warnings. After
explicit handling, the exact worker auth smoke passed. These earlier failures
are retained here rather than claimed as passes.

Run focused host tests without Core credentials:

```bash
python3 integrations/sentry/anima-household/test_household_worker.py
```

The host tests cover idle polling, auth-before-claim, provider-start ordering,
whole-plan validation, confirmation stop, non-retry, lease renewal/loss, actual
child-process timeout/cancellation/output limits, strict JSONL and client
transport validation. Household UI acceptance and physical behavior remain
separate, unrun qualifications. The lead owns `.agent`/Notion reconciliation,
Core/secret-volume commissioning and any subsequent deployment approval.

Initial single-plan handoff: **40 tests and 10 subtests PASSED** across the new
host tests and existing SENTRY boundary/hardening regressions; Ruff and scoped
diff checks **PASSED**. The existing MCP runtime certification **PASSED** on
Python 3.12.3/MCP 2.1.1 using its deterministic service fixture (18 transport
paths, no real household). Synthetic live plan and final calls **PASSED** with
zero tool invocations. The earlier bundled-Python `memfd_create` test failure
was corrected by using an anonymous shared-memory file and rerunning the tests.
Overall host evidence is **E4_REGRESSION_PROTECTED**; real model access is
separately observed, and full household agent workflow acceptance is **PARTIAL**.

### Bounded iterative helper extension

The user-authorized extension now implements the discovery/read → plan → invoke
→ reason loop with an optional `IterativeSentryTurnModel.plan_round` capability.
It does not change the Core wire schemas or the protected resident SENTRY host.
The exact catalogue, cumulative 8-call/3-round budgets, strictly increasing
ordinals, restricted-content final-only transition and deadlines are enforced
by host code, not merely by prompting.

Current targeted/regression validation: **53 tests and 17 subtests PASSED**;
Ruff and scoped diff checks **PASSED**. New evidence covers a discovered canonical
ID used by a subsequent semantic operation, ordinals 1–8 across three rounds,
over-budget rejection before dispatch, no fourth round, no second run of a turn,
defensive catalogue copies, all tested gate/failure dispositions, restricted
content blocking both another plan and tool, and real subprocess deadline
termination. A planning deadline uses the reserved final slot without replay.

Evidence remains **E4_REGRESSION_PROTECTED**. The earlier live auth smoke is
retained as prior evidence; no new live model or household/device/UI operation
was executed for this extension. The main agent owns service-boundary
commissioning and the subsequent real read-only UI proof. No commits or
deployment were performed. This is completion of the bounded helper increment,
not resident SENTRY voice/persona or whole-product acceptance.

### Live health-contract correction

Core health exposes `state`, not `status`. The worker's `--check` now accepts
`{"detail":null,"provider_id":"anima-core","state":"available","version":"1"}`
and rejects missing/unavailable `state` even when an unrelated `status` says
available. CLI-level regressions also prove the check neither claims queued work
nor invokes the model.

The live read-only check against the commissioned workstation socket
`/run/user/1000/anima-household-owner.sock` returned **READY** with exit code 0.
The supplied private client-token file was consumed only by the client and never
displayed. No worker loop or claim was started. The main agent owns the subsequent
worker startup and actual read-only UI proof. Validation: **55 tests and 21
subtests PASSED**, Ruff **PASSED**.

### First owner request: model completed, browser delivery failed

For request `086b964a-a023-56df-bf8a-736ce45e6a04`, a fresh **read-only** audit
of Core's existing durable store confirmed:

- Origin `DIRECT_UI_USER`; lifecycle `COMPLETED`; result status `RESPONSE`.
- Provider started `true`; claim attempt `1`; fencing generation `1`.
- Response digest and completion timestamp present; provider ambiguity `false`.
- Lifecycle sequence `CLAIMED → DELIVERED_TO_PROVIDER → PROVIDER_RUNNING → COMPLETED`.
- Context packet `17d79f82-28d9-5426-8705-5bbe75262d7b`, trigger
  `2013d0e7-0828-5730-b113-46e7d60d2aa2`.

The main agent reported worker stdout `RECORDED` and loss of the browser reply
because `JournalConversationIngress` substituted the journal event ID for the
intelligence request ID. The current source preserves the pipeline request ID;
that fix, its deployment and final browser proof remain the main agent's work.
**Initial reply delivery FAILED; final UI acceptance is not claimed here.** No
request replay, additional model call, tool invocation or physical-device call
was performed by this audit. SQL used read-only transactions and emitted only
identifiers, structure, booleans, lifecycle labels and counts, never contents.

#### Actual context shape and user text

For queued UI work, `CoreSentryBoundary.request_context()` calls the configured
`ContextBroker.load(trigger_id)` and returns the persisted ContextPacket. Its
top-level fields are `assembled_at`, `budgets`, `context_packet_id`, `digest`,
`omissions`, `schema_version`, `sections`, `selection_profile_version`,
`serialized_bytes`, `status`, and `trigger_id`. Sections are `graph`, `identity`,
`memories`, `recent_events`, `routines`, `source_events`, `tools`, `trigger`, and
`truth`. Each section has `items` containing `data` plus provenance/egress fields.

The audited request has one source event. The owner text is at
`sections.source_events.items[0].data.payload.text`; its sibling is `origin`.
There is no required top-level `user_text` on this UI path. A database equality
check returned true for packet text versus the source journal event's text,
and confirmed that event is the request's causation event, without selecting
the text itself. The worker serializes the supplied context into both planning
and final prompts; a synthetic sectioned-packet check confirmed inclusion in
both with zero model calls. The separate direct-SENTRY intake uses a different
`direct_context` envelope containing top-level `user_text`; do not conflate them.

Cloud-boundary audit note for the lead: the current SENTRY loader returns
`to_payload()` data, not `cloud_safe_projection()`. This request contained zero
`LOCAL_ONLY` items, six `CLOUD_REDACTED` items and eight `CLOUD_ALLOWED` items.
The helper currently forwards the received packet; it does not apply egress
projection itself. This sample is not proof of general egress enforcement.
Review the Core-owned projection contract before making that broader claim;
no Core/source changes were made by this audit.

#### What existing durable metadata can and cannot prove

`attempt_count=1` counts claims, not model calls. `provider_invocation_started`
and the `PROVIDER_RUNNING` transition establish the provider boundary, not how
many planning/final calls ran. The result's only metadata keys are
`action_references`, `detail`, and `provider_ambiguous`; action references are
empty. The worker does not submit its volatile `host_iteration` counters.
Moreover, the current Core HTTP result handler does not copy an incoming
`metadata` field into `IntelligenceResult.metadata`, even though the durable
store already has a `result_metadata` JSONB column. Adding a client field alone
would therefore not establish durable counters.

There are **zero request-linked coordinated action rows** using the exact
request idempotency prefix `:action:<ordinal>`. This does not prove zero read
calls: ordinary PluginManager reads have no generic request/ordinal-linked
durable invocation ledger in this path. Policy decisions use separate intent
IDs; counting unrelated same-household/time-window decisions cannot establish
this request's exact tool count. **Exact model-round and read-tool counts for
this completed request remain UNKNOWN**, not zero. Do not reconstruct them
from the configured 8-call/3-round maximum or from a response digest.

For subsequent evidence, the lead can use the existing result-metadata column
with an explicitly allowlisted, bounded numeric summary such as planning
rounds, model calls, tool attempts/completions and consumed ordinals, tied to
request ID and fencing generation. Core must validate/persist those fields;
label provider-supplied model counts as provider-reported. Independent tool
counts require Core to record accepted `/invoke` operations with ordinal and
outcome metadata. No prompts, arguments, tool results or response text are
needed. This is a proposal to the Core owner, not a change implemented here.

### Content-free failure diagnostics and mutation conversion regression

The worker now emits `TURN_DIAGNOSTIC` with only fixed `stage` and allowlisted
`exception_type` before its one-shot failure submission. It also appends these
fields to Core's existing durable `detail` string. No exception arguments,
messages, causes, traces, prompts, outputs or household values are emitted.
Unknown exception class names collapse to `Exception`; stages come from a fixed
host allowlist. Failed terminal delivery emits a separate `FAILURE_SUBMIT`
type-only diagnostic; it is not retried. Exit `2` and ambiguity are unchanged.

Stages distinguish context/catalogue loading, provider start, model planning,
schema construction, JSON argument conversion, exact schema validation,
CLI runtime/output, tool renewal/invocation/outcome, final synthesis and result
delivery. Existing fixed availability codes remain intact. Historical opaque
failures cannot be diagnosed retroactively from these newly added fields.

The follow-up safe transport classifier preserves numeric `http_status` and
exactly allowlisted `service_code` or `transport_code` in the same diagnostic
and durable detail. HTTP and Unix transports both read at most 64 KiB + 1;
unknown service messages become `UNCLASSIFIED`, never raw text. Timeout, remote
disconnect, refusal, invalid JSON, limits, and rejected redirects are distinct.
No response headers, error payloads, exception messages or causes are logged.

Inspection found no separate mutation plan format: `arguments_json` is decoded
and checked against the exact frozen Core `input_schema` for both reads and
writes. Missing JSON arguments produce `INVALID_PLAN` / `PLAN_CONVERT` /
`KeyError`; missing required create fields produce `INVALID_TOOL_ARGUMENTS` /
`PLAN_VALIDATE` / `ValidationError`, before dispatch. Neither establishes the
cause of the historical generic exception. A synthetic regression uses the
actual `HOUSEHOLD_SPACES_MANIFEST` schemas and exercises list → returned parent
ID → conditional create conversion through the iterative host, with unique
ordinals and no live model, Core call or graph mutation.

The diagnostic implementation is a host-only change. It does not deploy,
restart, resume, claim, or replay any live request. The main agent retains
ownership of the next fresh UI proof and final operational acceptance.

Diagnostic increment validation: **62 tests and 26 subtests PASSED** across
the worker suite and existing SENTRY boundary/hardening regressions; Ruff and
scoped `git diff --check` **PASSED**. These are synthetic/regression checks,
not a live mutation rerun. Historical generic-exception root cause remains
**UNKNOWN** until new content-free evidence is available.

### Household-space execution-boundary correction

Main reported fresh request `ce878704-0d24-5014-8e8d-9cc9b67c811c` failed at
`TOOL_INVOKE` / `AnimaHouseholdError`; its installed systemd worker exited `2`
without automatic restart. No retry or replay was performed here. The discarded
HTTP details of that historical invocation cannot be reconstructed from its
type-only diagnostic.

The suspected Core defect was independently **REPRODUCED** with an actual
`CoreSentryBoundary` → `PluginManager` path and a synthetic graph: after room
discovery, `create_space` raised `TRUSTED_ACTION_SPEC_UNAVAILABLE`. Household
graph writes defaulted to `COORDINATED_CONSEQUENTIAL` but have no provider action
safety spec, so they failed before graph execution or the ordinary policy gate.

With the owner's explicit scope extension, `src/anima_ha/plugins.py` now pairs
only these exact IDs with `builtin:anima_ha.household_spaces`, requiring both
trusted-native runtime and trust class:

- `anima.household-spaces.create_space`
- `anima.household-spaces.rename_space`
- `anima.household-spaces.move_space`
- `anima.household-spaces.remove_space`

Those four operations use the existing `POLICY_GATED_INTERNAL` route, retaining
their risk classes, exact schemas, household context, graph checks and
PluginManager/PolicyService gate. Wrong-source, external-runtime and unknown
mutation variants remain consequential. The older internal allowlist is
unchanged; no HA, power or notification boundary was lowered. Other modules'
classification review belongs to the main agent and is report-only here.

`tests/test_sentry_household_spaces.py` covers all four operations through the
actual SENTRY boundary: ALLOW reaches a synthetic graph and DENY causes zero
graph writes. It also checks exact source pairing and unchanged HA/notification
classification. The initial red test reproduced the missing safety-spec error;
after the fix, the combined plugin, household-space, SENTRY and worker suites
passed **90 tests and 43 subtests**. No live model/physical action, deployment,
service restart, or replay was performed. Main must deploy the Core correction
and update the installed worker files separately before its fresh owner proof;
this is not evidence that a Bedroom has been created.
