# H5U evidence

## Starting state

- Starting SHA: `684806ae53832ddd40cd0ee000ffbe35609a8ff2`.
- Branch: `main`; starting local and `origin/main` were aligned and clean.
- Retrieval confidence: `ADEQUATE`.

## Implemented boundary

The continuation adds a PostgreSQL-backed `anima_pending_approvals` record and
an ANIMA-owned `PendingApprovalStore`. The pending record binds the exact
action intent, challenge, authenticated principal, household, episode, tool
version, idempotency identity, resource/lock scope, preconditions, and a
bounded server-normalized argument envelope. Its public payload deliberately
omits executable arguments. Approval/rejection is atomically claimed and
single-use; expiry, wrong principal/household, replay, and rejection fail
closed. Approval reuses the original episode/request identity and invokes the
existing coordinator once, retaining Phase 9 observation and terminal-status
authority.

The AgentRuntime leaves a confirmation episode resumable and exposes a
same-episode continuation. The UI lists pending approvals and sends only an
approval ID plus `APPROVE`/`REJECT`, protected by the existing session,
CSRF, and origin checks.

## Evidence status

- `PASSED / E3_TARGET_TESTED`: in-memory exact-intent confirmation, rejection,
  expiry, wrong-principal, and single-use tests.
- `PASSED / E3_TARGET_TESTED`: same-episode AgentRuntime continuation without
  replaying the original tool request.
- `PASSED / E3_TARGET_TESTED`: real PostgreSQL migration, durable approval,
  exact-intent preservation, argument omission from payload, wrong-principal
  rejection, one provider call, and replay rejection via
  `scripts/verify_phase12_h5u_confirmation.py`.
- `PASSED / E4_REGRESSION_PROTECTED`: full validation, OPA, H4/H5 Core,
  isolated-HA API, restricted-content, frontend, and clean-filesystem browser
  reproduction as recorded in the session evidence.
- Historical H5T `FAILED / ValueError` task attempt remains preserved as
  negative evidence; the current H5 Core target reproduces task mutation
  successfully after the bounded correction.

Implementation checkpoint: `dbb4720882b25ad1d840c2c270191227f0c4ea1d`.
Implementation hosted CI: `33746353829` passed on that exact SHA.
The subsequent governance commit is the final governed checkpoint; its exact
SHA and hosted CI are recorded in the final Authority/Notion readback. Phase
12 remains pending Architect acceptance; Phase 13 is not implemented.
