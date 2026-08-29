# Durable Learnings

Temporary observations do not belong here. Add only findings likely to remain useful across future tasks.

---

## ANIMA-HA-P0-RUNTIME-BASELINE-002

- A pinned uv lockfile plus a narrow Python 3.12 support line gives Phase 0 reproducible package resolution without prematurely selecting future agent/event frameworks.
- The SFTP-mounted workspace cannot reliably host Python virtual-environment symlinks or mypy traversal; validation must distinguish this host filesystem limitation from application failures and can use a clean local-filesystem reproduction.
- The pgvector PostgreSQL image provides both amd64 and arm64 manifests and can be used as an extension-ready persistence substrate while vector/product schemas remain deferred.

---

## AUTHORITY-BOOTSTRAP-LEARNING-001 — Governance and implementation state are separate

- Date: 2026-08-28
- Evidence source: AUTHORITY-BOOTSTRAP-001 / Authority 3.0 Notion package
- Confidence: VERIFIED

### Learning

ANIMA HA starts with the Authority 3.0 governance package installed but with no implementation, dependencies, Git history, or runtime evidence.

### Why it matters

Future agents must treat governance bootstrap evidence as evidence of installed controls only, not evidence that any ANIMA HA capability or prototype acceptance criterion has been implemented.

### Recheck trigger

When the first implementation directive establishes repository, dependency, runtime, or test facts.

---

## ANIMA-HA-P0-LEARNING-001 — Existing GitHub baseline must remain the history parent

- Date: 2026-08-28
- Evidence source: ANIMA-HA-P0-GOVERNANCE-BASELINE-001 / remote inspection
- Confidence: VERIFIED

### Learning

The public `SketchOTP/ANIMA-Home-Automation` repository existed before local Git initialization at commit `088b267467fff93bfd225b9a94a6f4999759fb9f`, with `.gitignore` and `LICENSE` as its complete tree.

### Why it matters

Future checkpoints must preserve that history and must not replace or force-update `main` to discard the existing baseline.

### Recheck trigger

Any future history rewrite proposal, remote migration, or change to the repository's default branch.
