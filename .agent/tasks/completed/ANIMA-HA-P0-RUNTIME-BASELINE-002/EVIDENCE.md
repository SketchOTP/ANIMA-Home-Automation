# Phase 0 evidence

## Checkpoint

- Implementation checkpoint: `3fd0bfd1dc2c26798423a8077d2a1d9ca3bc3480`
- Remote `main`: same SHA; GitHub Actions run `33232446199` concluded `success`.
- Final metadata checkpoint will record this implementation SHA and may advance `main` by ledger-only changes.

## Observed environment

- Ubuntu 24.04.4 LTS, x86_64, CPython 3.12.3, Docker 29.7.2, Compose 5.5.0.
- `uv` 0.12.7 installed in an isolated tool directory for validation.

## Validation

- Locked dependency sync: PASSED.
- Ruff format/lint: PASSED.
- mypy 1.17.1 strict check: PASSED.
- pytest: PASSED, 4 tests.
- Source distribution and wheel build: PASSED; migration SQL included in wheel.
- Fresh checkout from the implementation checkpoint: PASSED for sync, validation, build, simulator readiness, and repeat migrations.
- PostgreSQL container health: PASSED; PostgreSQL 16.15, pgvector 0.8.6 available.
- Migration initialization/repeat: PASSED; first run applied `0001_runtime_baseline`, repeat applied zero.
- Restart persistence: PASSED; migration/runtime metadata remained present after `docker compose restart db`.
- Idle resource observation: approximately 0.02% CPU / 71 MiB before restart and 0.00% CPU / 23 MiB after restart on this host.
- ARM64: image manifest and PyPI wheel evidence only; no native Pi execution.
- Public safety: PASSED after review; `.env.example` contains only an explicitly labeled non-secret development placeholder.

## Host limitation

The SFTP-mounted workspace cannot reliably create Python virtual-environment symlinks and caused slow mypy traversal. The source and tests were copied by allowlist to a local filesystem and the complete validation/build gate passed there. This is not claimed as ARM64 or Pi evidence.
