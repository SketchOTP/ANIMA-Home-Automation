# 027A evidence

Status: `IN_PROGRESS`

## Retrieval

- Repository/runtime/Notion retrieval confidence: `ADEQUATE`.
- ANIMA repository started clean at `97f0b672c20e556ced27f5c22b6499bb9d870ea7` with `main == origin/main`.
- SENTRY repository started clean at `ed8cbab98be1a34444d2514f38e94dc8b0244272` on its published feature branch.
- Accepted exact-head hosted CI was re-read from the Architect directive and Git history.
- The Notion permanent Goal and current 027A authority were retrieved before implementation.

## Deployed-build reconciliation

- Critical ANIMA Core source hashes in the healthy owner UI container match the accepted ANIMA checkout.
- Installed `anima-household` client/MCP source hashes match the accepted ANIMA checkout.
- `sentry-voice.service`, `anima-household-worker.service`, and the Android relay are active from the accepted clean SENTRY checkout/runtime files.
- The RPi projection services are active and their deployed projection/voice file hashes match the accepted SENTRY checkout.
- Active output instance is `office`; playback ownership for this qualification is therefore the Linux-PC SENTRY audio process.

## Pre-event baseline

- Front Door Lock has an active `UNLOCKED / ALWAYS / 00:00–23:59 / America/New_York` rule.
- Latest qualified Tapo lock journal position before the requested physical event: `12688`.
- Qualified Tapo lock event count: `42`.
- Trial ledger record count: `28`.
- Trial ledger mode: `0600`; current digest:
  `sha256:746c081973d1364c4205f3ffb991323f1839a1c29635ac68ed6caf4a6b8af296`.
- The ledger schema is content-free and records only timing/status metadata.

## Open evidence

- Fresh exact-build physical Tapo unlock: `OWNER-ACTION GATE` until observed.
- Event-to-playback latency and duplicate/provider-start counts: pending that event.
- Goal residual matrix and software closure: in progress.
- Three-day household trial: `ELAPSED-TIME GATE` until at least `2026-09-12T02:21:00Z`.

## Coherent software residual: personality configuration

- Added durable household-scoped free-form SENTRY personality profiles with
  create/edit/activate/delete owner controls and an explicit built-in fallback.
- The live UI retained the same authenticated browser session and active
  profile across a real UI-container restart. Temporary qualification records
  were deleted afterward.
- The installed credential-isolated SENTRY client read the server-owned active
  profile contract; SENTRY prompt regressions prove the text remains
  presentation-only and cannot replace ANIMA authority or mandatory factual
  alert behavior.
- Complete ANIMA and SENTRY regression suites passed locally. Hosted exact-head
  evidence remains pending publication of this consolidated owner checkpoint.

## R3 continuous household learning

- Implementation and boundary: deterministic source-linked pattern candidates,
  exact review packets, provider-start-fenced structured SENTRY outcomes,
  versioned Memory correction/supersession, Obsidian hierarchy, incremental
  durable review tasks, owner inspection and later sparse-context retrieval.
- Live source inventory at final local qualification: 121 raw eligible event
  rows across four qualified device-event classes and four local dates; all
  source identities were unique. There were zero qualified presence
  transitions, so no arrival/departure or household-member attribution was
  inferred.
- Explicit live catch-up: six candidates, one
  `LEARNED_ROUTINE_SUGGESTION`, five `TENTATIVE_HYPOTHESIS`, zero declared
  routines/automations/permissions/identity assertions/actions. Request and
  packet are represented by sanitized SHA-256 digests only:
  `79ef1ce30af8d23f4dacf2052877f86a613cc410eb6a56b3e46a8faea788dd19`
  and `652364fcc97ae37704223aa1b044895e163838bd9e627d6626b7a4375c4e1b3d`.
- Continuous tasks: one daily 86,400-second review and one multi-day
  259,200-second review are active. Catch-up remains explicitly separate from
  scheduled due-run evidence.
- Later-use live trace: an ordinary UI-originated SENTRY request retrieved one
  relevant learned-routine suggestion and two tentative hypotheses alongside
  explicit owner context. The request is represented only by digest
  `98087e4961509f5d0ee09b2033f6d1a93e6c6aefc573901956a439d331b2aa6f`.
  Internal review packet/config/completion records were absent; SENTRY preserved
  uncertainty and did not infer actor, cause, policy or routine certainty.
- Obsidian: learning outcomes use managed `300.1`–`300.5` note types and
  digest-checked correction. Fourteen total managed notes were observed after
  catch-up and later decision logging; all observed note modes were `0660`.
- PASSED locally: full ANIMA validation `1169 passed / 76 skipped`, Ruff,
  strict mypy (147 source files), focused migrated-PostgreSQL learning tests,
  main Playwright `115 passed / 14 intentional smaller-viewport skips`, focused
  responsive browser `42 passed`, frontend `14 passed`, TypeScript/Vite, and
  complete qualified SENTRY `542 passed`.
- The aggregate `scripts/validate.sh` wrapper initially failed because `uv` was
  absent from the shell PATH; direct `.venv/bin/anima-validate` ran the same
  governed Python validation successfully. A first SENTRY run under the host
  interpreter failed because it lacked the qualified media/ML libraries; it was
  rerun successfully under `/home/sketch/.venvs/sentry-ubuntu/bin/python`.
- `.venv/bin/python -m build` was unavailable because the optional `build`
  module is not installed in that environment. The repository-pinned
  `.venv/bin/uv build --sdist --wheel` completed both artifacts successfully.
- Full architecture/evidence boundary: `docs/GOAL-027A-HOUSEHOLD-LEARNING-R3.md`.
- Implementation head `6ddee068dfa18e1623d9deacdb91cff0d0cbbdae`
  published successfully, but exact-head CI `34423847476` is retained as
  `FAILED`: every backend/policy/build/frontend gate passed before one tablet
  Playwright stream-quota test failed because `pauseAt(new Date())` raced the
  installed fake clock and attempted to move backward. The test now starts at
  a fixed epoch and pauses one second forward; the same scenario passes on
  desktop, tablet and phone. This is a test-only correction.
