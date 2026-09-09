"""ANIMA-owned household voice presentation settings for SENTRY."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    ExternalContentTrust,
    Idempotency,
    InvocationContext,
    PluginManifest,
    PluginValidationError,
    RuntimeKind,
    TrustClass,
)

VOICE_IDS = frozenset(
    {
        "af_bella",
        "af_sarah",
        "am_adam",
        "am_michael",
        "bf_emma",
        "bf_isabella",
        "bm_george",
        "bm_lewis",
    }
)
DEFAULT_VOICE = "bm_george"
DEFAULT_SPEED = 0.9
DEFAULT_SLEEP_ENABLED = False
SENTRY_INSTANCE_IDS = frozenset({"living_room", "office"})
DEFAULT_ACTIVE_INSTANCE_ID = "living_room"


def validate_voice_settings(value: dict[str, Any] | None) -> dict[str, Any]:
    value = value or {}
    voice = value.get("voice_id", DEFAULT_VOICE)
    speed = value.get("speech_speed", DEFAULT_SPEED)
    sleep_enabled = value.get("sleep_enabled", DEFAULT_SLEEP_ENABLED)
    active_instance_id = value.get("active_instance_id", DEFAULT_ACTIVE_INSTANCE_ID)
    if not isinstance(voice, str) or voice not in VOICE_IDS:
        raise ValueError("unsupported SENTRY voice")
    if (
        isinstance(speed, bool)
        or not isinstance(speed, (int, float, Decimal))
        or not 0.75 <= float(speed) <= 1.30
    ):
        raise ValueError("SENTRY speech speed must be between 0.75 and 1.30")
    if not isinstance(sleep_enabled, bool):
        raise ValueError("SENTRY sleep_enabled must be boolean")
    if not isinstance(active_instance_id, str) or active_instance_id not in SENTRY_INSTANCE_IDS:
        raise ValueError("unsupported active SENTRY instance")
    return {
        "voice_id": voice,
        "speech_speed": round(float(speed), 2),
        "sleep_enabled": sleep_enabled,
        "active_instance_id": active_instance_id,
    }


class SentryVoiceSettingsStore:
    """Small household-scoped store; no SENTRY or browser credentials."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def get(self, household_id: UUID) -> dict[str, Any]:
        with (
            psycopg.connect(self.database_url, row_factory=dict_row) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "SELECT voice_id, speech_speed, sleep_enabled, active_instance_id "
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
                INSERT INTO anima_sentry_voice_settings (
                    household_id, voice_id, speech_speed, sleep_enabled, active_instance_id
                )
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (household_id) DO UPDATE SET
                    voice_id=EXCLUDED.voice_id, speech_speed=EXCLUDED.speech_speed,
                    sleep_enabled=EXCLUDED.sleep_enabled,
                    active_instance_id=EXCLUDED.active_instance_id, updated_at=now()
                """,
                (
                    household_id,
                    settings["voice_id"],
                    settings["speech_speed"],
                    settings["sleep_enabled"],
                    settings["active_instance_id"],
                ),
            )
            connection.commit()
        return settings


SENTRY_CONTROL_MANIFEST = PluginManifest(
    plugin_id="anima.sentry-control",
    plugin_version="1.0.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="SENTRY control",
    description="ANIMA-owned one-way control of SENTRY wake availability",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("sentry.control",),
    tools=(
        {
            "name": "enter_sleep_mode",
            "description": (
                "Put SENTRY into sleep mode after an explicit spoken request. "
                "This is one-way: return to standby/wake listening manually in ANIMA Settings; "
                "no SENTRY tool can wake it."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "required": ["status", "sleep_enabled", "wake_available"],
                "properties": {
                    "status": {"const": "SUCCEEDED"},
                    "sleep_enabled": {"const": True},
                    "wake_available": {"const": False},
                },
                "additionalProperties": False,
            },
            "semantic_action": "sentry.enter_sleep_mode",
            "risk_class": "LOW_RISK_HOME_CONTROL",
            "read_only": False,
            "idempotency": Idempotency.IDEMPOTENT.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
    ),
    source="builtin:anima_ha.sentry_voice_settings",
)


class SentryControlNativePlugin:
    """Expose only the self-limiting spoken sleep transition to SENTRY."""

    def __init__(self, store: SentryVoiceSettingsStore) -> None:
        self.store = store

    def start(self, secret_env: dict[str, str]) -> None:
        if secret_env:
            raise PluginValidationError("SENTRY control accepts no plugin secrets")

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in SENTRY_CONTROL_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        del name, arguments, timeout
        raise PluginValidationError("SENTRY control requires trusted invocation context")

    def invoke_with_invocation_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        context: InvocationContext,
    ) -> Any:
        del timeout
        if name != "enter_sleep_mode" or arguments:
            raise PluginValidationError("unknown SENTRY control operation")
        current = self.store.get(context.household_id)
        if current["sleep_enabled"]:
            return {"status": "SUCCEEDED", "sleep_enabled": True, "wake_available": False}
        self.store.update(
            context.household_id,
            {
                "voice_id": current["voice_id"],
                "speech_speed": current["speech_speed"],
                "sleep_enabled": True,
                "active_instance_id": current["active_instance_id"],
            },
        )
        return {"status": "SUCCEEDED", "sleep_enabled": True, "wake_available": False}
