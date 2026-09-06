# Goal increment — server-owned backup snapshots

ANIMA now exposes a bounded owner-facing backup surface without exposing
PostgreSQL administration to the browser, model, or SENTRY.

The authenticated Backups view can create a PostgreSQL custom-format archive
and validate its recorded SHA-256 digest. The Core composition owns the
database connection, `pg_dump` process, absolute backup directory, archive
permissions, and household filtering. Browser payloads contain no database
URL, credential, archive path, or household authority; the authenticated
InvocationContext supplies household scope.

The current surface intentionally does not restore an active database. Restore
requires a controlled maintenance workflow that can stop/reconstruct the
application, migrate the restored database, and re-observe Home Assistant
before treating physical state as current. The existing Phase 14 `pg_dump` /
`pg_restore` evidence remains the qualification record for that operator
workflow; this increment adds no new restore claim.

The archive manifest is server-only metadata. UI payloads contain only the
backup reference, timestamp, size, schema version, digest, and integrity
status. A backup is household-scoped and is not visible to another household.
