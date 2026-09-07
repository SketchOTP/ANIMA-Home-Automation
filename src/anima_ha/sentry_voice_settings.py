"""ANIMA-owned household voice presentation settings for SENTRY."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg

VOICE_IDS = frozenset({
    "af_bella", "af_sarah", "am_adam", "am_michael",
    "bf_emma", "bf_isabella", "bm_george", "bm_lewis",
})
DEFAULT_VOICE = "bm_george"
DEFAULT_SPEED = 0.9


def validate_voice_settings(value: dict[str, Any] | None) -> dict[str, Any]:
    value = value or {}
    voice = value.get("voice_id", DEFAULT_VOICE)
    speed = value.get("speech_speed", DEFAULT_SPEED)
    if not isinstance(voice, str) or voice not in VOICE_IDS:
        raise ValueError("unsupported SENTRY voice")
    if (
        isinstance(speed, bool)
        or not isinstance(speed, (int, float))
        or not 0.75 <= float(speed) <= 1.30
    ):
        raise ValueError("SENTRY speech speed must be between 0.75 and 1.30")
    return {"voice_id": voice, "speech_speed": round(float(speed), 2)}


class SentryVoiceSettingsStore:
    """Small household-scoped store; no SENTRY or browser credentials."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def get(self, household_id: UUID) -> dict[str, Any]:
        with psycopg.connect(self.database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT voice_id, speech_speed "
                "FROM anima_sentry_voice_settings WHERE household_id=%s",
                (household_id,),
            )
            row = cursor.fetchone()
        return validate_voice_settings(dict(row) if row else None)

    def update(self, household_id: UUID, value: dict[str, Any]) -> dict[str, Any]:
        settings = validate_voice_settings(value)
        with psycopg.connect(self.database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_sentry_voice_settings (household_id, voice_id, speech_speed)
                VALUES (%s,%s,%s)
                ON CONFLICT (household_id) DO UPDATE SET
                    voice_id=EXCLUDED.voice_id, speech_speed=EXCLUDED.speech_speed, updated_at=now()
                """,
                (household_id, settings["voice_id"], settings["speech_speed"]),
            )
            connection.commit()
        return settings
