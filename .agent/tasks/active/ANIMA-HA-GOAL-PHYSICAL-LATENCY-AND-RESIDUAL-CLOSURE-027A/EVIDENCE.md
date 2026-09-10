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
- Complete ANIMA and SENTRY regression suites passed locally. The published
  consolidated owner checkpoint is exact-head hosted green; see the R4
  publication section below.

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
- Correction head `01433593f18247f181cc7a601a049e6bb10ec262` then
  passed the formerly failing main browser suite and every earlier hosted gate.
  Exact-head CI `34425286338` is nevertheless retained as `FAILED` because the
  later owner-product Memory suite still expected the superseded phrase
  “system-authored audit records.” The product now describes all managed
  decision/learning records as “system-authored, evidence-linked”; the test was
  aligned to that existing behavior. The complete owner-product browser
  verifier subsequently passed locally (`42 + 15 + 3 + 33` scenarios).
- Final implementation/correction head
  `9b84d3aaa8fbf853ecb9812080f4ea667a696e07` is exact-head hosted green:
  CI `34426846774` `PASSED`. Artifact `10133392831`, digest
  `sha256:adf82cd694063ed43ae01f8f3f2090cbece604572a28ba4783233012490788df`.
  The run includes the full ANIMA validation, OPA, real Core/PostgreSQL and
  accepted resilience qualifications, public-safety scan, ARM64 image/runtime,
  container health, main Playwright and the complete owner-product browser
  verifier. R3 is hosted-qualified at E4, with the live catch-up/later-use paths
  retaining E5 operational evidence.

## R4 residual closure — 2026-09-10

### Personality decision isolation

- `PASSED` locally: direct and autonomous operational prompts now discard the
  owner profile before prompt construction and use neutral built-in operational
  guidance. The obsolete profile-to-operational prompt helper was removed.
- `PASSED` locally: only a completed, harmless, tool-free, non-autonomous
  result is eligible for a separate ephemeral presentation pass. The renderer
  uses a bounded JSON schema and read-only/no-tool/ignore-user-config Codex
  execution. Its only mutable field is `answer`; it cannot change structured
  status, facts, tools, authorization, notification requirements or terminal
  outcomes. Renderer failure falls back to the neutral answer.
- `PASSED` locally: existing action/event regressions and new focused tests
  prove tool-bearing, autonomous, limited, failure and consequential paths do
  not enter the personality renderer. Mandatory first alert speech remains
  outside this path.
- `PASSED` locally: an active custom profile changes a harmless ordinary answer
  only through the second renderer call while the operational invocation input
  contains no profile text and structured result fields remain unchanged.

### Profile lifecycle correction

- `PASSED` locally: ANIMA PostgreSQL and owner API profile creation now always
  saves `active=false`; the first profile is not implicitly selected.
- `PASSED` locally: `Built-in SENTRY` is an explicit UI/API operation that
  deactivates custom profiles without deleting them. Version-checked activation
  remains atomic and household-scoped; the profile version is refreshed after
  built-in fallback before reactivation, preserving optimistic concurrency.

### Wake and identity evidence boundaries

- `PASSED` (`E1_OBSERVED`): the completed ten-minute metadata-only observation
  of the live office instance showed repeated `LISTENING`,
  `last_segment_outcome=non_wake`, empty Vosk class, no wake-chime request, no
  command dispatch and no Codex dispatch. This qualifies the unattended ambient
  interval only and contains no audio or transcript.
- `OWNER-ACTION GATE`: three exact spoken `Sentry` wakes plus the confusing
  negative phrase remain to be performed against the running instance. No live
  wake pass is fabricated.
- `OWNER-ACTION GATE` / nonblocking UX follow-up: the permanent goal requires a
  demonstrable voice software path, not final whole-home face hardware. Corrected
  eight-capture face enrollment is therefore not a permanent-goal acceptance
  gate; a fresh owner enrollment remains unobserved.

### Tooling and remaining gates

- `PASSED`: `DO_NOT_TRACK=1 npx --yes @nanonets/graft telemetry status` reports
  telemetry `off`. Repository-local Graft `AGENTS.md`, `.gitignore` and ignored
  `graft/` remain intentionally outside product commits.
- Full exact residual matrix: `docs/GOAL-027A-R4-RESIDUAL-CLOSURE.md`.
- Remaining gates are a fresh exact-build physical Tapo unlock latency sample,
  the three-day household trial no earlier than `2026-09-12T02:21:00Z`, and
  owner spoken wake/face follow-ups. Permanent-goal completion is not claimed.

### R4 published qualification

- `PASSED`: ANIMA head
  `20fb54f37ac2775e3c0498f2a206193462d99572` has exact-head CI `34431369009`
  `PASSED`. The run completed deterministic, PostgreSQL/OPA, Phase 13/14,
  ARM64, container, browser, safety and artifact gates.
- GitHub artifact `10134892070`, named
  `phase12-h5-evidence-20fb54f37ac2775e3c0498f2a206193462d99572`, was
  published. The GitHub artifact API exposes no native digest; the downloaded
  evidence-tree aggregate digest is
  `sha256:b4fc65f1cacbad7e0450a586976255e7e4c884cfa507965ec8a16199ea6cdba0`.
- `PASSED`: SENTRY head
  `8e459ad1c62b46ea3c51003f8df984fd14480004` has exact-head CI `34431379452`
  `PASSED` (deterministic and security-focused jobs).
