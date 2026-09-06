# Goal increment — server-owned backup snapshots

ANIMA now exposes a bounded owner-facing backup surface without exposing
PostgreSQL administration to the browser, model, or SENTRY.

The authenticated Backups view can create a PostgreSQL custom-format archive
and validate its recorded SHA-256 digest. The Core composition owns the
database connection, `pg_dump` process, absolute backup directory, archive
permissions, and household filtering. Browser payloads contain no database
URL, credential, archive path, or household authority; the authenticated
InvocationContext supplies household scope.

The owner-facing surface now also supports an explicitly confirmed Core-owned
restore of a validated archive into the configured ANIMA database. The restore
uses PostgreSQL cleanup and single-transaction safeguards, applies current
migrations, and marks restored physical Truth `UNKNOWN_UNTIL_REOBSERVED` until
Home Assistant performs a fresh reconciliation. The browser never receives a
database URL, credential, archive path, or raw administration command.

This is a controlled recovery operation, not a claim that restored physical
state is current. The existing Phase 14 `pg_dump` / `pg_restore` evidence
remains the clean-environment qualification record; this increment adds the
bounded owner initiation and Core execution path.

The archive manifest is server-only metadata. UI payloads contain only the
backup reference, timestamp, size, schema version, digest, and integrity
status. A backup is household-scoped and is not visible to another household.

Implementation checkpoint: `da7392bf57b2ecf615bbfcace5700e9fb0e6fcef`.
Exact-head hosted CI: `34058199339` (PASS). Published artifact:
`9996805982`; the public artifact endpoint did not expose a digest without
authenticated download.

Final governance checkpoint: `7d57f32dda04295a0c4830849416e753490791a1`.
Exact-head hosted CI: `34059183314` (PASS). Published artifact:
`9997092423`; the public artifact endpoint did not expose a digest without
authenticated download.
