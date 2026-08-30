# Phase 8 Codex OAuth agent runtime

Checked: 2026-08-30. This phase adds bounded cloud cognition through the
operator's existing Codex CLI ChatGPT OAuth session. It does not give the model
Codex's coding-agent capabilities and it does not implement the Phase 9 action
engine.

## Boundary and flow

```text
durable Phase 7 reasoning trigger + ContextPacket
        ↓
ANIMA cloud-safe projection + bounded tool catalogue
        ↓
one isolated ephemeral codex exec / Luna turn
        ↓
schema-valid TOOL_REQUEST or FINAL
        ↓
ANIMA argument validation
        ↓
Phase 5 Tool Gateway → Phase 4 OPA policy → plugin (only on ALLOW)
        ↓
bounded, redacted structured result → next fresh Luna turn
```

ANIMA owns the episode, prompt contract, ContextPacket projection, tool
catalogue, schemas, policy call, tool execution, result filtering, budgets,
timeouts, persistence, audit, and final disposition. `CodexCliRuntime` is a
replaceable reasoning adapter. It cannot invoke ANIMA tools itself.

Each Luna turn runs in a newly created empty directory with `codex exec -`,
`--ephemeral`, `--ignore-user-config`, `--ignore-rules`, `--strict-config`, a
read-only sandbox, a supplied output schema, `gpt-5.6-luna`, and medium
reasoning. Agents/multi-agent, shell/unified execution, apps, plugins, image access,
web search, memories, automatic dependency installation, login shells,
history persistence, analytics, and feedback are explicitly disabled. The
child environment is an allowlist and does not forward `OPENAI_API_KEY` or
ANIMA/household secrets. The installed CLI does not accept the documented
`tools.view_image=false` key; qualification established the supported
equivalent `features.view_image=false` under strict configuration.

JSONL is treated as a security boundary. Only lifecycle events and a completed
`agent_message` are accepted. Command, file, MCP, web, computer-use,
image-generation, tool, reasoning-item, unknown-item, or unknown-event output
fails the episode closed. Raw chain-of-thought is neither requested nor
persisted.

## Structured sequential loop

The output schema is deliberately flat because the tested Codex structured
output service rejected a root `oneOf`. All fields are required and `kind`
selects `TOOL_REQUEST` or `FINAL`. Variable tool arguments are canonical JSON
text in `arguments.json`; ANIMA parses that text and validates the resulting
object against the exact Phase 5 tool input schema before any gateway call.
This preserves full per-tool JSON Schema validation without allowing an open
structured-output object.

One tool may be requested per turn. Every continuation is a fresh process that
receives only the cloud-safe packet, the same bounded catalogue, and the prior
structured model/tool transcript. `DENY`, `REQUIRE_CONFIRMATION`, and
`REQUIRE_STRONGER_AUTH` terminate before plugin invocation and remain distinct
runtime outcomes. Plugin failures return structured evidence for a possible
next reasoning turn and can never become fabricated success.

The default episode limits are eight Codex turns, eight tool requests, 300
seconds wall time, 90 seconds per turn, 60,000 observed tokens, 16 KiB per tool
result, and 2 MB per process stream. Process timeout terminates the complete
child process group. Output overflow, invalid JSON/schema, forbidden JSONL,
OAuth/model/service unavailability, refusal, token/turn/tool exhaustion, and
tool failure all have explicit dispositions.

## Privacy and persistence

The persisted Phase 7 ContextPacket is reprojected at episode start. `LOCAL_ONLY`
items and source references are omitted, sensitive keys are recursively
redacted, and `CLOUD_REDACTED` identifiers are replaced. The projection digest,
local packet digest, byte count, omission count, instruction version, Codex
version, model, reasoning effort, bounded decisions, token usage, latency,
sanitized tool requests/results, final outcome, and failure class are durable.
The full cloud prompt and raw reasoning are not persisted.

Tool output is recursively secret-filtered and size-bounded before it enters
the transcript. External trust metadata remains present and cannot become
authority. The live harness confirms that a `LOCAL_ONLY` sentinel never enters
the prompt; tests cover secret-key filtering and external-content distrust.

`anima_agent_episodes.trigger_id` is unique, so duplicate trigger claims return
the existing episode and cannot run a second cognition loop. The tables are a
durable episode record, not a durable future-work scheduler.

## Authentication and outage behavior

Authentication remains owned by Codex. ANIMA checks only that `codex login
status` reports ChatGPT login; it never reads OAuth files, tokens, or browser
credentials. There is no API-key fallback. Missing login, unavailable Luna,
usage exhaustion, nonzero subprocess failure, malformed output, or timeout
fails the episode explicitly while local journal, Truth, graph, memory,
attention, HA, and plugin services remain independent.

Because this uses a ChatGPT OAuth allowance, repository evidence records
observed token counts and latency but does not apply API dollar pricing. The
operator's ChatGPT/Codex service terms and server-side retention controls remain
an external privacy boundary; no claim is made that model-provider processing
is local or zero-retention.

## Dependency and replacement decisions

| Candidate | Decision | Result |
| --- | --- | --- |
| ANIMA episode/runtime/contracts | BUILD | Required to retain policy, tools, context, privacy, persistence, budgets, and outcomes under ANIMA authority. |
| Installed Codex CLI `0.150.0-alpha.8` + `codex exec` | ADOPT / WRAP | Live ChatGPT OAuth, Luna selection, strict config, JSONL, output schema, ephemeral turns, timeout, and failure behavior were reproduced on x86-64. Exact tested binary is pre-stable and must be requalified on upgrade. |
| Codex SDK | REFERENCE / DEFER | Programmatic Codex control may reduce subprocess plumbing later, but does not improve the current Python replacement boundary enough to replace the qualified CLI path. |
| Codex App Server | REFERENCE / DEFER | Rich long-lived JSON-RPC integration is unnecessary for one bounded isolated turn and exposes a broader lifecycle surface. |
| OpenAI Agents SDK | DEFER / REJECT for this directive | Useful API-key/provider tool runtime, but it cannot consume the operator-required Codex CLI ChatGPT OAuth session as the selected foundation. |
| Responses API | DEFER | Direct API path would require separate API credentials/billing and a changed operator authorization decision. |
| Phase 5 Tool Gateway + Phase 4 OPA | ADOPT / WRAP | Remains the only invocation/authority path. Codex never receives plugin handles. |

Primary sources: [Codex CLI reference](https://developers.openai.com/codex/cli/reference),
[Codex configuration reference](https://developers.openai.com/codex/config-reference),
[Codex non-interactive mode](https://learn.chatgpt.com/codex/non-interactive-mode),
[Codex SDK](https://developers.openai.com/codex/sdk),
[Codex App Server](https://developers.openai.com/codex/app-server),
[Agents SDK](https://openai.github.io/openai-agents-python/), and
[Responses API](https://platform.openai.com/docs/api-reference/responses).
The Codex repository is Apache-2.0. The model/account service remains a hosted
OpenAI dependency rather than a repository package.

## Evidence and limits

Unit evidence covers schema parsing, forbidden JSONL, sanitized environment,
cloud projection, tool validation/gating, duplicate claims, explicit outcomes,
budgets, timeout, refusal, provider outage, prompt injection, and fake
credential-free CI behavior. PostgreSQL evidence covers migration repeat,
durable turns/tool records/audit, duplicate trigger claims, and database restart.

The live x86-64 OAuth matrix runs nine synthetic scenarios against a broad six-
tool catalogue: no action, fresh-state lookup, model-selected two-tool sequence,
confirmation, stronger authentication, plugin failure, hostile external text,
weather lookup, and another no-action case. The final exact-code pass observed
14 Luna turns, 112,592 input tokens, 4,864 cached input tokens, 1,555 output
tokens, 508 reasoning output tokens, 4,468.88 ms median turn latency, and
6,347.26 ms p95. Every
scenario reached the expected ANIMA disposition with no forbidden direct
capability event. One earlier focused weather attempt returned an invalid
structured result and was safely classified `CodexInvalidResult`; the final
full matrix subsequently passed. This is evidence of fail-closed behavior and
also a reminder that model output is not perfectly deterministic.

The live catalogue and household are synthetic. There is no physical-home,
native ARM64/Pi, direct HA action, generalized action concurrency/lease,
durable-task, UI, voice, or production external-service claim. Hosted CI uses
the deterministic scripted adapter and does not require OAuth.
