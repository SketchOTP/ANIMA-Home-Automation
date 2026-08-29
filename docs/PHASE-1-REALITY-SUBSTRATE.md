# Phase 1 — Reality Substrate

Phase 1 establishes the deterministic, provider-independent substrate that later
attention and cognition phases will consume. It contains no Home Assistant
adapter, Household Graph, memory, permissions, agent runtime, or action tools.

## Event model

`anima_ha.events.EventEnvelope` is the ANIMA-owned immutable envelope. It keeps
event occurrence time separate from receive/record time and carries schema
version, event/source identity, subject key, optional source sequence,
correlation/causation, confidence/evidence, delivery importance, typed JSON
payload, and non-authoritative metadata. The only supported envelope schema in
this phase is version `1`; unknown versions fail explicitly.

Truth observations are encoded as `truth.observation` payloads using a generic
`namespace / subject / attribute`-style `truth_key`. An observation can be
`KNOWN`, `UNKNOWN`, or `UNAVAILABLE`, and retains source, timestamps, optional
source sequence, confidence, evidence kind, freshness duration, and event
provenance.

## Journal and projection boundary

`PostgresEventJournal` is the canonical append-only store. A generated identity
provides stable monotonic `journal_position`. Unique event identity and a
partial unique `(source, source_event_id)` index make ingestion idempotent,
including concurrent duplicate attempts. An append-only database trigger
rejects normal SQL updates/deletes as a second safety boundary.

`PostgresRealityStore` journals first, then invokes `PostgresTruthProjection`.
Truth observations and their current materialized resolution are separate from
the journal. A projection checkpoint advances only after a projection
transaction commits. Failures are recorded in
`anima_projection_failures`; the canonical event remains available for retry.

## Ordering and reconciliation

For each truth key and source, an explicit source sequence takes precedence over
arrival order. Without a sequence, observation time, receive time, and event ID
provide deterministic ordering. Tied latest observations remain candidates so
contradictory values become `CONFLICTING` rather than being guessed away.

Identical latest values from multiple sources are corroboration. A known value
whose freshness deadline has passed becomes `STALE` while retaining its value
and provenance. If no known candidate exists, explicit unavailable/unknown
states are returned. Direct evidence is preferred over inferred evidence only
when the values agree; evidence and all candidates remain visible to callers.

## Replay and rebuild

`PostgresTruthProjection.rebuild()` truncates only derived truth tables and
replays the canonical journal in journal-position order. It validates the
event schema, performs no external calls, and returns replay/state counts.
Because the reducer is pure and deterministic, the rebuilt resolution can be
compared with the live resolution at a chosen reference time.

## Commands and evidence boundary

```bash
uv sync --locked --dev
docker compose up -d db
ANIMA_DATABASE_URL=postgresql://anima:anima_dev_only@localhost:55432/anima \
  uv run --locked --group dev anima-migrate
ANIMA_DATABASE_URL=postgresql://anima:anima_dev_only@localhost:55432/anima \
  uv run --locked --group dev anima-sim --once --scenario normal
```

The simulator injects only synthetic, deterministic reality-substrate events;
it does not claim real-home or Home Assistant behavior. Unit tests exercise the
pure reducer. PostgreSQL integration evidence exercises persistence,
concurrency, append-only enforcement, projection retry, and rebuild. The
current live integration evidence is x86-64 only; no ARM64 or physical-home
claim is made.
