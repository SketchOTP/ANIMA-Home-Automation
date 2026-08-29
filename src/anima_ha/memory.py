"""ANIMA-owned governed memory and rebuildable local retrieval index.

The PostgreSQL memory table is authoritative.  The full-text table is a
derived index that may be deleted and rebuilt without losing memory records.
This module deliberately exposes no permission or authority mutation surface.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.journal import PostgresEventJournal


class MemoryValidationError(ValueError):
    """Raised when a memory would violate the canonical contract."""


class MemoryType(StrEnum):
    EXPLICIT_PREFERENCE = "EXPLICIT_PREFERENCE"
    EXPLICIT_FACT = "EXPLICIT_FACT"
    OBSERVED_CONTEXT = "OBSERVED_CONTEXT"
    INFERRED_PATTERN = "INFERRED_PATTERN"
    INTERACTION_MEMORY = "INTERACTION_MEMORY"
    AGENT_LESSON = "AGENT_LESSON"
    TEMPORARY_EPISODIC = "TEMPORARY_EPISODIC"


class MemoryStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    RETRACTED = "RETRACTED"


class ProvenanceKind(StrEnum):
    EXPLICIT_INPUT = "EXPLICIT_INPUT"
    EVENT_JOURNAL = "EVENT_JOURNAL"
    TRUTH_OBSERVATION = "TRUTH_OBSERVATION"
    HOUSEHOLD_GRAPH = "HOUSEHOLD_GRAPH"
    INFERRED_FROM_HISTORY = "INFERRED_FROM_HISTORY"
    PRIOR_MEMORY = "PRIOR_MEMORY"
    AGENT_LESSON = "AGENT_LESSON"


class RetrievalMode(StrEnum):
    INDEXED_LEXICAL = "INDEXED_LEXICAL"
    LEXICAL_FALLBACK = "LEXICAL_FALLBACK"


@dataclass(frozen=True, slots=True)
class MemoryProvenance:
    kind: ProvenanceKind
    source_ref: str
    source_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: UUID
    household_id: UUID
    memory_type: MemoryType
    content: str
    retrieval_text: str
    provenance: MemoryProvenance
    created_at: datetime
    subject_id: UUID | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    confidence: float | None = None
    expires_at: datetime | None = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    supersedes_memory_id: UUID | None = None
    superseded_by_memory_id: UUID | None = None
    graph_refs: tuple[UUID, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "memory_type", MemoryType(self.memory_type))
        object.__setattr__(self, "status", MemoryStatus(self.status))
        if not self.content.strip() or not self.retrieval_text.strip():
            raise MemoryValidationError("content and retrieval_text must not be empty")
        if not self.provenance.source_ref.strip():
            raise MemoryValidationError("provenance source_ref must not be empty")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise MemoryValidationError("confidence must be between 0 and 1")
        if self.memory_type == MemoryType.AGENT_LESSON and (
            self.confidence is None or self.confidence > 0.5
        ):
            raise MemoryValidationError("agent lessons require confidence <= 0.5")
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise MemoryValidationError("valid_until must not precede valid_from")
        if (
            self.supersedes_memory_id == self.memory_id
            or self.superseded_by_memory_id == self.memory_id
        ):
            raise MemoryValidationError("memory cannot supersede itself")
        for value in (self.created_at, self.valid_from, self.valid_until, self.expires_at):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise MemoryValidationError("memory timestamps must be timezone-aware")
        _validate_metadata(self.metadata)

    @classmethod
    def create(
        cls,
        *,
        household_id: UUID,
        memory_type: MemoryType,
        content: str,
        provenance: MemoryProvenance,
        created_at: datetime | None = None,
        retrieval_text: str | None = None,
        **kwargs: Any,
    ) -> MemoryRecord:
        return cls(
            memory_id=UUID(str(kwargs.pop("memory_id", uuid4()))),
            household_id=household_id,
            memory_type=memory_type,
            content=content,
            retrieval_text=retrieval_text or normalize_retrieval_text(content),
            provenance=provenance,
            created_at=created_at or datetime.now(UTC),
            **kwargs,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "memory_id": str(self.memory_id),
            "household_id": str(self.household_id),
            "subject_id": str(self.subject_id) if self.subject_id else None,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "retrieval_text": self.retrieval_text,
            "provenance": {
                "kind": self.provenance.kind.value,
                "source_ref": self.provenance.source_ref,
                "source_event_id": self.provenance.source_event_id,
            },
            "created_at": self.created_at.isoformat(),
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "confidence": self.confidence,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status.value,
            "supersedes_memory_id": str(self.supersedes_memory_id)
            if self.supersedes_memory_id
            else None,
            "superseded_by_memory_id": str(self.superseded_by_memory_id)
            if self.superseded_by_memory_id
            else None,
            "graph_refs": [str(value) for value in self.graph_refs],
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    memory: MemoryRecord
    lexical_score: float
    precedence_rank: int
    mode: RetrievalMode


def normalize_retrieval_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def _validate_metadata(value: Any, key_path: str = "metadata") -> None:
    forbidden = {"authority", "permission", "permissions", "policy", "grant", "grants"}
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in forbidden:
                raise MemoryValidationError(f"{key_path} cannot contain authority metadata")
            _validate_metadata(child, f"{key_path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_metadata(child, f"{key_path}[{index}]")
    else:
        json.dumps(value, sort_keys=True)


def memory_precedence(memory_type: MemoryType) -> int:
    return {
        MemoryType.EXPLICIT_FACT: 500,
        MemoryType.EXPLICIT_PREFERENCE: 490,
        MemoryType.TEMPORARY_EPISODIC: 480,
        MemoryType.INTERACTION_MEMORY: 300,
        MemoryType.OBSERVED_CONTEXT: 250,
        MemoryType.AGENT_LESSON: 150,
        MemoryType.INFERRED_PATTERN: 100,
    }[MemoryType(memory_type)]


class MemoryService:
    """Canonical memory repository and bounded retrieval service."""

    def __init__(
        self, database_url: str, connect_timeout: int = 5, *, index_enabled: bool = True
    ) -> None:
        self.database_url = database_url
        self.connect_timeout = connect_timeout
        self.index_enabled = index_enabled
        self.journal = PostgresEventJournal(database_url, connect_timeout)

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self.database_url, connect_timeout=self.connect_timeout, row_factory=dict_row
        )

    @staticmethod
    def _memory(row: dict[str, Any]) -> MemoryRecord:
        return MemoryRecord(
            memory_id=UUID(str(row["memory_id"])),
            household_id=UUID(str(row["household_id"])),
            subject_id=UUID(str(row["subject_id"])) if row["subject_id"] else None,
            memory_type=MemoryType(str(row["memory_type"])),
            content=str(row["content"]),
            retrieval_text=str(row["retrieval_text"]),
            provenance=MemoryProvenance(
                ProvenanceKind(str(row["provenance_kind"])),
                str(row["source_ref"]),
                str(row["source_event_id"]) if row["source_event_id"] else None,
            ),
            created_at=row["created_at"],
            valid_from=row["valid_from"],
            valid_until=row["valid_until"],
            confidence=row["confidence"],
            expires_at=row["expires_at"],
            status=MemoryStatus(str(row["status"])),
            supersedes_memory_id=(
                UUID(str(row["supersedes_memory_id"])) if row["supersedes_memory_id"] else None
            ),
            superseded_by_memory_id=(
                UUID(str(row["superseded_by_memory_id"]))
                if row["superseded_by_memory_id"]
                else None
            ),
            graph_refs=tuple(UUID(str(value)) for value in (row["graph_refs"] or [])),
            metadata=dict(row["metadata"] or {}),
        )

    @staticmethod
    def _audit_event(
        action: str, memory: MemoryRecord, *, related_id: UUID | None = None
    ) -> EventEnvelope:
        payload = {
            "action": action,
            "memory": memory.to_payload(),
            "related_memory_id": str(related_id) if related_id else None,
        }
        event_id = f"memory-mutation-{uuid4()}"
        return EventEnvelope.create(
            event_id=event_id,
            event_type="memory.mutation",
            source="memory_service",
            subject_key=f"household/{memory.household_id}",
            occurred_at=memory.created_at,
            payload=payload,
            source_event_id=event_id,
            importance=EventImportance.NORMAL,
            delivery_class=DeliveryClass.GUARANTEED,
        )

    @staticmethod
    def _index_one(connection: psycopg.Connection[Any], memory_id: UUID) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_memory_search_index (memory_id, search_document, indexed_at)
                SELECT memory_id, to_tsvector('simple', retrieval_text), now()
                FROM anima_memory_records
                WHERE memory_id = %s AND status = 'ACTIVE'
                  AND (expires_at IS NULL OR expires_at > now())
                ON CONFLICT (memory_id) DO UPDATE SET
                    search_document = EXCLUDED.search_document, indexed_at = now()
                """,
                (memory_id,),
            )

    def create(self, memory: MemoryRecord) -> MemoryRecord:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO anima_memory_records (
                        memory_id, household_id, subject_id, memory_type, content, retrieval_text,
                        provenance_kind, source_ref, source_event_id, created_at, valid_from,
                        valid_until, confidence, expires_at, status, supersedes_memory_id,
                        graph_refs, metadata
                    ) VALUES (%(memory_id)s, %(household_id)s, %(subject_id)s, %(memory_type)s,
                              %(content)s, %(retrieval_text)s, %(provenance_kind)s, %(source_ref)s,
                              %(source_event_id)s, %(created_at)s, %(valid_from)s, %(valid_until)s,
                              %(confidence)s, %(expires_at)s, %(status)s, %(supersedes_memory_id)s,
                              %(graph_refs)s::jsonb, %(metadata)s::jsonb)
                    """,
                    {
                        "memory_id": memory.memory_id,
                        "household_id": memory.household_id,
                        "subject_id": memory.subject_id,
                        "memory_type": memory.memory_type.value,
                        "content": memory.content,
                        "retrieval_text": memory.retrieval_text,
                        "provenance_kind": memory.provenance.kind.value,
                        "source_ref": memory.provenance.source_ref,
                        "source_event_id": memory.provenance.source_event_id,
                        "created_at": memory.created_at,
                        "valid_from": memory.valid_from,
                        "valid_until": memory.valid_until,
                        "confidence": memory.confidence,
                        "expires_at": memory.expires_at,
                        "status": memory.status.value,
                        "supersedes_memory_id": memory.supersedes_memory_id,
                        "graph_refs": json.dumps([str(value) for value in memory.graph_refs]),
                        "metadata": json.dumps(memory.metadata, sort_keys=True),
                    },
                )
            if self.index_enabled:
                self._index_one(connection, memory.memory_id)
            self.journal.append_in_connection(connection, self._audit_event("CREATED", memory))
            connection.commit()
        return memory

    def get(self, memory_id: UUID) -> MemoryRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM anima_memory_records WHERE memory_id = %s", (memory_id,)
                )
                row = cursor.fetchone()
        return self._memory(row) if row else None

    def _transition(self, memory_id: UUID, status: MemoryStatus, action: str) -> MemoryRecord:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM anima_memory_records WHERE memory_id = %s FOR UPDATE",
                    (memory_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise MemoryValidationError("memory does not exist")
                memory = self._memory(row)
                if memory.status != MemoryStatus.ACTIVE:
                    raise MemoryValidationError("only ACTIVE memories may transition")
                cursor.execute(
                    "UPDATE anima_memory_records SET status = %s WHERE memory_id = %s",
                    (status.value, memory_id),
                )
                cursor.execute(
                    "DELETE FROM anima_memory_search_index WHERE memory_id = %s", (memory_id,)
                )
                transitioned = replace(memory, status=status)
            self.journal.append_in_connection(connection, self._audit_event(action, transitioned))
            connection.commit()
        return transitioned

    def expire(self, memory_id: UUID) -> MemoryRecord:
        return self._transition(memory_id, MemoryStatus.EXPIRED, "EXPIRED")

    def expire_due(self, *, household_id: UUID | None = None, now: datetime | None = None) -> int:
        """Materialize elapsed expiry into lifecycle state and audit it."""

        now = now or datetime.now(UTC)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                if household_id is None:
                    cursor.execute(
                        """
                        SELECT * FROM anima_memory_records
                        WHERE status = 'ACTIVE' AND expires_at IS NOT NULL AND expires_at <= %s
                        FOR UPDATE
                        """,
                        (now,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM anima_memory_records
                        WHERE household_id = %s AND status = 'ACTIVE'
                          AND expires_at IS NOT NULL AND expires_at <= %s
                        FOR UPDATE
                        """,
                        (household_id, now),
                    )
                rows = list(cursor.fetchall())
                expired = [replace(self._memory(row), status=MemoryStatus.EXPIRED) for row in rows]
                if expired:
                    cursor.execute(
                        """
                        UPDATE anima_memory_records SET status = 'EXPIRED'
                        WHERE memory_id = ANY(%s)
                        """,
                        ([memory.memory_id for memory in expired],),
                    )
                    cursor.execute(
                        "DELETE FROM anima_memory_search_index WHERE memory_id = ANY(%s)",
                        ([memory.memory_id for memory in expired],),
                    )
            for memory in expired:
                self.journal.append_in_connection(connection, self._audit_event("EXPIRED", memory))
            connection.commit()
        return len(expired)

    def retract(self, memory_id: UUID) -> MemoryRecord:
        return self._transition(memory_id, MemoryStatus.RETRACTED, "RETRACTED")

    def correct(self, original_id: UUID, replacement: MemoryRecord) -> MemoryRecord:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM anima_memory_records WHERE memory_id = %s FOR UPDATE",
                    (original_id,),
                )
                original_row = cursor.fetchone()
                if original_row is None:
                    raise MemoryValidationError("memory does not exist")
                original = self._memory(original_row)
                if original.status != MemoryStatus.ACTIVE:
                    raise MemoryValidationError("only ACTIVE memories may be corrected")
                if replacement.household_id != original.household_id:
                    raise MemoryValidationError("correction must remain in the same household")
                replacement = replace(
                    replacement,
                    supersedes_memory_id=original.memory_id,
                    created_at=replacement.created_at,
                    status=MemoryStatus.ACTIVE,
                )
                cursor.execute(
                    """
                    INSERT INTO anima_memory_records (
                        memory_id, household_id, subject_id, memory_type, content, retrieval_text,
                        provenance_kind, source_ref, source_event_id, created_at, valid_from,
                        valid_until, confidence, expires_at, status, supersedes_memory_id,
                        graph_refs, metadata
                    ) VALUES (%(memory_id)s, %(household_id)s, %(subject_id)s, %(memory_type)s,
                              %(content)s, %(retrieval_text)s, %(provenance_kind)s, %(source_ref)s,
                              %(source_event_id)s, %(created_at)s, %(valid_from)s, %(valid_until)s,
                              %(confidence)s, %(expires_at)s, %(status)s, %(supersedes_memory_id)s,
                              %(graph_refs)s::jsonb, %(metadata)s::jsonb)
                    """,
                    {
                        "memory_id": replacement.memory_id,
                        "household_id": replacement.household_id,
                        "subject_id": replacement.subject_id,
                        "memory_type": replacement.memory_type.value,
                        "content": replacement.content,
                        "retrieval_text": replacement.retrieval_text,
                        "provenance_kind": replacement.provenance.kind.value,
                        "source_ref": replacement.provenance.source_ref,
                        "source_event_id": replacement.provenance.source_event_id,
                        "created_at": replacement.created_at,
                        "valid_from": replacement.valid_from,
                        "valid_until": replacement.valid_until,
                        "confidence": replacement.confidence,
                        "expires_at": replacement.expires_at,
                        "status": replacement.status.value,
                        "supersedes_memory_id": replacement.supersedes_memory_id,
                        "graph_refs": json.dumps([str(value) for value in replacement.graph_refs]),
                        "metadata": json.dumps(replacement.metadata, sort_keys=True),
                    },
                )
                cursor.execute(
                    "UPDATE anima_memory_records SET status = 'SUPERSEDED', "
                    "superseded_by_memory_id = %s WHERE memory_id = %s",
                    (replacement.memory_id, original_id),
                )
                cursor.execute(
                    "DELETE FROM anima_memory_search_index WHERE memory_id = %s", (original_id,)
                )
            if self.index_enabled:
                self._index_one(connection, replacement.memory_id)
            self.journal.append_in_connection(
                connection, self._audit_event("CORRECTED", replacement, related_id=original_id)
            )
            connection.commit()
        return replacement

    def _rows_for_filters(
        self,
        *,
        household_id: UUID,
        subject_id: UUID | None,
        memory_types: Iterable[MemoryType] | None,
        graph_ref: UUID | None,
        now: datetime,
    ) -> tuple[str, dict[str, Any]]:
        clauses = [
            "m.household_id = %(household_id)s",
            "m.status = 'ACTIVE'",
            "(m.expires_at IS NULL OR m.expires_at > %(now)s)",
            "(m.valid_from IS NULL OR m.valid_from <= %(now)s)",
            "(m.valid_until IS NULL OR m.valid_until >= %(now)s)",
        ]
        params: dict[str, Any] = {"household_id": household_id, "now": now}
        if subject_id is not None:
            clauses.append("m.subject_id = %(subject_id)s")
            params["subject_id"] = subject_id
        if memory_types:
            clauses.append("m.memory_type = ANY(%(memory_types)s)")
            params["memory_types"] = [MemoryType(value).value for value in memory_types]
        if graph_ref is not None:
            clauses.append("m.graph_refs @> %(graph_refs)s::jsonb")
            params["graph_refs"] = json.dumps([str(graph_ref)])
        return " AND ".join(clauses), params

    def retrieve(
        self,
        query: str,
        *,
        household_id: UUID,
        top_k: int = 5,
        subject_id: UUID | None = None,
        memory_types: Iterable[MemoryType] | None = None,
        graph_ref: UUID | None = None,
        now: datetime | None = None,
    ) -> list[MemorySearchResult]:
        if top_k < 1:
            raise MemoryValidationError("top_k must be positive")
        now = now or datetime.now(UTC)
        self.expire_due(household_id=household_id, now=now)
        where, params = self._rows_for_filters(
            household_id=household_id,
            subject_id=subject_id,
            memory_types=memory_types,
            graph_ref=graph_ref,
            now=now,
        )
        try:
            if self.index_enabled:
                with self._connect() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            f"""
                            SELECT m.*, COALESCE(ts_rank(i.search_document,
                                plainto_tsquery('simple', %(query)s)), 0)::double precision
                                AS lexical_score
                            FROM anima_memory_records m
                            LEFT JOIN anima_memory_search_index i ON i.memory_id = m.memory_id
                            WHERE {where}
                              AND (%(query)s = '' OR (
                                  i.search_document @@ plainto_tsquery('simple', %(query)s)))
                            ORDER BY CASE m.memory_type
                                WHEN 'EXPLICIT_FACT' THEN 500
                                WHEN 'EXPLICIT_PREFERENCE' THEN 490
                                WHEN 'TEMPORARY_EPISODIC' THEN 480
                                WHEN 'INTERACTION_MEMORY' THEN 300
                                WHEN 'OBSERVED_CONTEXT' THEN 250
                                WHEN 'AGENT_LESSON' THEN 150
                                ELSE 100 END DESC,
                                lexical_score DESC, m.created_at DESC, m.memory_id
                            LIMIT %(top_k)s
                            """,
                            {**params, "query": normalize_retrieval_text(query), "top_k": top_k},
                        )
                        rows = list(cursor.fetchall())
                if rows or not query.strip():
                    return [
                        MemorySearchResult(
                            self._memory(row),
                            float(row["lexical_score"]),
                            memory_precedence(MemoryType(str(row["memory_type"]))),
                            RetrievalMode.INDEXED_LEXICAL,
                        )
                        for row in rows
                    ]
        except psycopg.Error:
            pass
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT m.* FROM anima_memory_records m WHERE {where}", params)
                rows = list(cursor.fetchall())
        terms = set(re.findall(r"[\w]+", normalize_retrieval_text(query)))
        ranked: list[MemorySearchResult] = []
        for row in rows:
            memory = self._memory(row)
            words = set(re.findall(r"[\w]+", memory.retrieval_text))
            score = len(terms & words) / max(len(terms), 1) if terms else 0.0
            if terms and score == 0:
                continue
            ranked.append(
                MemorySearchResult(
                    memory,
                    score,
                    memory_precedence(memory.memory_type),
                    RetrievalMode.LEXICAL_FALLBACK,
                )
            )
        ranked.sort(
            key=lambda item: (
                -item.precedence_rank,
                -item.lexical_score,
                -item.memory.created_at.timestamp(),
                str(item.memory.memory_id),
            )
        )
        return ranked[:top_k]

    def clear_index(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE anima_memory_search_index")
            connection.commit()

    def rebuild_index(self) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE anima_memory_search_index")
                cursor.execute(
                    """
                    INSERT INTO anima_memory_search_index (memory_id, search_document)
                    SELECT memory_id, to_tsvector('simple', retrieval_text)
                    FROM anima_memory_records
                    WHERE status = 'ACTIVE' AND (expires_at IS NULL OR expires_at > now())
                    """
                )
                count = cursor.rowcount
            connection.commit()
        return count

    def index_count(self) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) AS count FROM anima_memory_search_index")
                row = cursor.fetchone()
                assert row is not None
                return int(row["count"])
