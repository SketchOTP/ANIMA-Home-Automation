# CODEX DIRECTIVE — ANIMA-HA-P12-BROWSER-ACCEPTANCE-EVIDENCE-CLOSURE-014H5T

## Directive contract

- **Parent/result:** H5S `ANIMA-HA-P12-BROWSER-ACCEPTANCE-EVIDENCE-CLOSURE-014H5S`, result `PARTIAL / CONTINUE`.
- **Exact baseline:** repository `SketchOTP/ANIMA-Home-Automation`, branch `main`, SHA `09f1402bdff34a79b0b08b882752c491f89c0959`; local and remote matched at issuance.
- **Verified current state:** H5R product surfaces pass targeted browser readback; H5 Core and isolated-HA API targets pass; prior API-level session reconstruction exists, but same-browser continuity across a real process restart and SSE/refetch recovery is unproven. Phase 12 is unaccepted.
- **Goal relationship:** proving durable browser-session continuity across restart directly closes the canonical goal's persistence, restart/recovery, and integrated-interface requirements.
- **Primary closure objective:** prove the same browser session survives stopping and restarting the actual UI process, preserves PostgreSQL-backed state, and recovers UI/SSE/refetch without duplicate mutation; otherwise record exact evidence limits.
- **Bottleneck rationale:** this is the highest-value remaining feasible integration gap after H5S because current evidence proves reconstruction only at API/Core level, not the user-visible session boundary.

## Authorized scope

- Inspect and reuse the existing UI server, session store, SSE/event broadcaster, H4/H5 harnesses, browser tests, and PostgreSQL state.
- Start a bounded isolated candidate runtime from the exact baseline; use the same browser tab/session across process stop and restart.
- Exercise only safe, idempotent read/settings or test-scoped task mutation needed to prove continuity and duplicate protection; record exact session/refetch/SSE observations.
- Make the smallest test/harness correction needed to observe the existing contract, without changing product semantics unless a demonstrated correctness defect requires it.
- Commit/push evidence or governance changes only after independent review.

## Prohibited scope

- No new session/authority store, browser cookie/storage inspection, Phase 8 confirmation redesign, decorative approval, Phase 13 voice, new provider/framework/database/broker, production mutation, credential change, destructive database cleanup, or fixture reseed.
- Do not claim API/Core reconstruction as same-browser evidence; do not claim a server restart when only a new process/session was created.
- Do not discard shared dirty data, hide timeouts, weaken tests, or promote a partial/blocked observation to pass.
- Stop project-changing work immediately on lock ownership/fencing loss.

## Required investigation

1. Reconcile H5S records, Notion, exact GitHub baseline/CI, current server/runtime, and session/SSE implementation.
2. Determine how to stop/restart the actual candidate process while preserving the browser tab and PostgreSQL-backed session; confirm the server identity changed.
3. Observe pre-restart authenticated UI state, stop/restart boundary, post-restart authenticated UI state, settings continuity, SSE/refetch recovery, and mutation count/outcome.
4. Classify unsupported browser-cookie/storage details as `NOT INSPECTED` while using visible behavior and server evidence only.
5. State retrieval confidence before shared-behavior edits as `ADEQUATE`, `UNCERTAIN`, or `INSUFFICIENT`.

## Acceptance criteria

- Exact baseline, lock owner, and current runtime are reconciled before execution.
- The same browser tab/session reaches authenticated UI state before and after a real application-process restart.
- PostgreSQL-backed session/configuration continuity and visible UI refetch/SSE recovery are observed without a new login or new browser context.
- At least one bounded read or test-scoped mutation demonstrates no duplicate operation across recovery.
- Any failure, timeout, unavailable SSE observation, or uninspected browser-storage claim remains explicitly negative/unsupported.
- Existing H5R surfaces and Phase 0–11 behavior remain unchanged and regression-protected.
- Final result classifies whether this target reaches E3/E4/E5 evidence and whether Phase 12 can be accepted; this directive does not self-accept Phase 12.

## Validation/evidence requirements

Run the focused browser/restart target and relevant Core/API regression, frontend type/build or existing test checks if files change, plus `git diff --check`. Record exact process identities, URLs, visible assertions, mutation result, logs, artifacts, and final SHA/remote alignment.

## Durable updates required

Update this packet's `PLAN.md`, `EVIDENCE.md`, and `HANDOFF.md`; append `.agent/DIRECTIVES.md` and `.agent/OUTCOMES.md`; update `.agent/CURRENT.md`; synchronize/refetch the canonical ANIMA HA and Authority Notion record; verify GitHub; then ownership-check and release/transition the lock.

## Stop conditions

- Lock ownership/fencing mismatch.
- Safe same-session proof is impossible in the available environment; preserve the exact blocker as `BLOCKED`/`NOT RUN`.
- Any material session/security/policy assumption is disproven.
- Evidence is sufficient to classify this single restart/SSE target; do not expand into other H5 gaps.

## Handoff/result fields

Return the canonical `CODEX RESULT` contract with verdict, retrieval confidence, technical state, work performed, changed areas, validation, evidence level, acceptance results, blockers, deviations, durable records, exact GitHub SHA/push state, and recommendation to the Architect.
