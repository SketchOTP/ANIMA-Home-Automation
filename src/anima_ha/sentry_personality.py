"""Household-scoped presentation profiles for the SENTRY intelligence."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import errors
from psycopg.rows import dict_row

MAX_PROFILE_NAME = 80
MAX_PROFILE_TEXT = 4000
BUILT_IN_PROFILE_NAME = "Built-in SENTRY"
PRESENTATION_BOUNDARY = (
    "Personality affects wording only. ANIMA Truth, identity, policy, mandatory factual alerts, "
    "tool authorization, and verified action results always take precedence."
)


class SentryPersonalityConflict(ValueError):
    """The requested profile mutation conflicts with current durable state."""


def _clean_text(value: Any, *, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    result = value.strip()
    if not result or len(result) > maximum:
        raise ValueError(f"{field} must contain 1 to {maximum} characters")
    if any(ord(character) < 32 and character not in "\n\r\t" for character in result):
        raise ValueError(f"{field} contains unsupported control characters")
    return result


def validate_personality_profile(value: dict[str, Any]) -> dict[str, str]:
    return {
        "name": _clean_text(value.get("name"), field="name", maximum=MAX_PROFILE_NAME),
        "profile_text": _clean_text(
            value.get("profile_text"), field="profile_text", maximum=MAX_PROFILE_TEXT
        ),
    }


def _uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"invalid {field}") from exc


def default_personality_payload() -> dict[str, Any]:
    return {
        "status": "DEFAULT",
        "profile_id": None,
        "name": BUILT_IN_PROFILE_NAME,
        "profile_text": "",
        "version": None,
        "presentation_only": True,
        "boundary": PRESENTATION_BOUNDARY,
    }


class SentryPersonalityStore:
    """Versioned free-form SENTRY presentation profiles owned by ANIMA."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @staticmethod
    def _payload(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "profile_id": str(row["profile_id"]),
            "name": str(row["name"]),
            "profile_text": str(row["profile_text"]),
            "version": str(row["version"]),
            "active": bool(row["active"]),
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "presentation_only": True,
        }

    def list(self, household_id: UUID) -> dict[str, Any]:
        with (
            psycopg.connect(self.database_url, row_factory=dict_row) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                """
                SELECT profile_id, name, profile_text, version, active, created_at, updated_at
                FROM anima_sentry_personality_profiles
                WHERE household_id=%s
                ORDER BY active DESC, lower(name), profile_id
                """,
                (household_id,),
            )
            items = [self._payload(dict(row)) for row in cursor.fetchall()]
        active = next((item["profile_id"] for item in items if item["active"]), None)
        return {
            "items": items,
            "active_profile_id": active,
            "fallback_active": active is None,
            "fallback_name": BUILT_IN_PROFILE_NAME,
            "boundary": PRESENTATION_BOUNDARY,
        }

    def active(self, household_id: UUID) -> dict[str, Any]:
        with (
            psycopg.connect(self.database_url, row_factory=dict_row) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                """
                SELECT profile_id, name, profile_text, version, active, created_at, updated_at
                FROM anima_sentry_personality_profiles
                WHERE household_id=%s AND active
                """,
                (household_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return default_personality_payload()
        return {"status": "ACTIVE", **self._payload(dict(row)), "boundary": PRESENTATION_BOUNDARY}

    def create(self, household_id: UUID, value: dict[str, Any]) -> dict[str, Any]:
        profile = validate_personality_profile(value)
        profile_id = uuid4()
        version = uuid4()
        try:
            with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
                active = connection.execute(
                    "SELECT 1 FROM anima_sentry_personality_profiles "
                    "WHERE household_id=%s AND active",
                    (household_id,),
                ).fetchone()
                row = connection.execute(
                    """
                    INSERT INTO anima_sentry_personality_profiles (
                        profile_id, household_id, name, profile_text, version, active
                    ) VALUES (%s,%s,%s,%s,%s,%s)
                    RETURNING profile_id, name, profile_text, version, active,
                              created_at, updated_at
                    """,
                    (
                        profile_id,
                        household_id,
                        profile["name"],
                        profile["profile_text"],
                        version,
                        active is None,
                    ),
                ).fetchone()
                connection.commit()
        except errors.UniqueViolation as exc:
            raise SentryPersonalityConflict("profile name already exists") from exc
        assert row is not None
        return self._payload(dict(row))

    def update(self, household_id: UUID, value: dict[str, Any]) -> dict[str, Any]:
        profile = validate_personality_profile(value)
        profile_id = _uuid(value.get("profile_id"), "profile_id")
        expected_version = _uuid(value.get("expected_version"), "expected_version")
        try:
            with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
                row = connection.execute(
                    """
                    UPDATE anima_sentry_personality_profiles
                    SET name=%s, profile_text=%s, version=%s, updated_at=now()
                    WHERE household_id=%s AND profile_id=%s AND version=%s
                    RETURNING profile_id, name, profile_text, version, active,
                              created_at, updated_at
                    """,
                    (
                        profile["name"],
                        profile["profile_text"],
                        uuid4(),
                        household_id,
                        profile_id,
                        expected_version,
                    ),
                ).fetchone()
                connection.commit()
        except errors.UniqueViolation as exc:
            raise SentryPersonalityConflict("profile name already exists") from exc
        if row is None:
            raise SentryPersonalityConflict("profile changed or no longer exists")
        return self._payload(dict(row))

    def activate(self, household_id: UUID, value: dict[str, Any]) -> dict[str, Any]:
        profile_id = _uuid(value.get("profile_id"), "profile_id")
        expected_version = _uuid(value.get("expected_version"), "expected_version")
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            selected = connection.execute(
                """
                SELECT 1 FROM anima_sentry_personality_profiles
                WHERE household_id=%s AND profile_id=%s AND version=%s
                FOR UPDATE
                """,
                (household_id, profile_id, expected_version),
            ).fetchone()
            if selected is None:
                raise SentryPersonalityConflict("profile changed or no longer exists")
            connection.execute(
                "UPDATE anima_sentry_personality_profiles SET active=FALSE, updated_at=now() "
                "WHERE household_id=%s AND active",
                (household_id,),
            )
            row = connection.execute(
                """
                UPDATE anima_sentry_personality_profiles
                SET active=TRUE, version=%s, updated_at=now()
                WHERE household_id=%s AND profile_id=%s
                RETURNING profile_id, name, profile_text, version, active,
                          created_at, updated_at
                """,
                (uuid4(), household_id, profile_id),
            ).fetchone()
            connection.commit()
        assert row is not None
        return self._payload(dict(row))

    def delete(self, household_id: UUID, value: dict[str, Any]) -> dict[str, Any]:
        profile_id = _uuid(value.get("profile_id"), "profile_id")
        expected_version = _uuid(value.get("expected_version"), "expected_version")
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """
                DELETE FROM anima_sentry_personality_profiles
                WHERE household_id=%s AND profile_id=%s AND version=%s
                RETURNING active
                """,
                (household_id, profile_id, expected_version),
            ).fetchone()
            connection.commit()
        if row is None:
            raise SentryPersonalityConflict("profile changed or no longer exists")
        return {
            "profile_id": str(profile_id),
            "deleted": True,
            "fallback_active": bool(row[0]),
        }

    def mutate(self, household_id: UUID, operation: str, value: dict[str, Any]) -> dict[str, Any]:
        operations = {
            "create": self.create,
            "update": self.update,
            "activate": self.activate,
            "delete": self.delete,
        }
        selected = operations.get(operation)
        if selected is None:
            raise ValueError("unsupported personality operation")
        selected(household_id, value)
        return self.list(household_id)
