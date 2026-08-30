# Specification — ANIMA-HA-P8-CODEX-OAUTH-RUNTIME-010R

Implement a replaceable ANIMA-owned `AgentRuntime` around isolated, ephemeral `codex exec` subprocess turns authenticated by Codex-owned ChatGPT OAuth and explicitly selecting `gpt-5.6-luna` with medium reasoning. Each turn returns a schema-constrained `TOOL_REQUEST` or `FINAL`; ANIMA validates and policy-gates any tool request, filters the result for cloud egress, persists bounded episode evidence, and derives authoritative outcomes. Codex receives no direct machine/tool capability. Phase 9 behavior is excluded.
