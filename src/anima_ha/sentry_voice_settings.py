"""ANIMA-owned household voice presentation settings for SENTRY."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from anima_ha.action import ActionStatus, ActionStore
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
from anima_ha.policy import RequestOrigin
from anima_ha.sentry_identity_profiles import SentryIdentityProfileClient

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


def _audio_tool(name: str, properties: dict[str, Any], *, read_only: bool) -> dict[str, Any]:
    return {
        "name": name,
        "description": (
            "Bounded direct-operator SENTRY audio control; "
            "workstation volume or fixed Pi USB/HDMI output"
        ),
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "required": ["status", "result"],
            "properties": {
                "status": {"enum": ["SUCCEEDED", "UNKNOWN_RESULT"]}
                if name == "adjust_system_volume"
                else {"const": "SUCCEEDED"},
                "result": {"type": "object"},
                **(
                    {"outcome": {"const": "UNKNOWN_RESULT"}}
                    if name == "adjust_system_volume"
                    else {}
                ),
            },
            "additionalProperties": False,
        },
        "semantic_action": name,
        "risk_class": "READ_ONLY" if read_only else "LOW_RISK_HOME_CONTROL",
        "read_only": read_only,
        "idempotency": Idempotency.KEYED.value
        if name == "adjust_system_volume"
        else Idempotency.IDEMPOTENT.value,
        "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
    }


AUDIO_TOOLS = (
    _audio_tool("get_system_volume", {}, read_only=True),
    _audio_tool(
        "set_system_volume",
        {"percent": {"type": "number", "minimum": 0, "maximum": 150}},
        read_only=False,
    ),
    _audio_tool(
        "adjust_system_volume",
        {"delta_percent": {"type": "number", "minimum": -100, "maximum": 100, "not": {"const": 0}}},
        read_only=False,
    ),
    _audio_tool("set_system_muted", {"muted": {"type": "boolean"}}, read_only=False),
    _audio_tool("get_projection_audio_output", {}, read_only=True),
    _audio_tool(
        "set_projection_audio_output",
        {"output": {"type": "string", "enum": ["usb", "hdmi"]}},
        read_only=False,
    ),
)


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
        *AUDIO_TOOLS,
    ),
    source="builtin:anima_ha.sentry_voice_settings",
)


class SentryControlNativePlugin:
    """Expose only the self-limiting spoken sleep transition to SENTRY."""

    def __init__(
        self,
        store: SentryVoiceSettingsStore,
        audio_client: SentryIdentityProfileClient | None = None,
        principal_is_current: Callable[[UUID, UUID], bool] | None = None,
        action_store: ActionStore | None = None,
    ) -> None:
        self.store = store
        self.audio_client = audio_client
        self.principal_is_current = principal_is_current
        self.action_store = action_store

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
        if name in {tool["name"] for tool in AUDIO_TOOLS}:
            if context.origin != RequestOrigin.DIRECT_USER or context.principal_id is None:
                raise PluginValidationError("SENTRY audio requires a current direct principal")
            if self.principal_is_current is None or not self.principal_is_current(
                context.household_id, context.principal_id
            ):
                raise PluginValidationError(
                    "SENTRY audio principal is not a current household member"
                )
            if self.audio_client is None:
                raise PluginValidationError("SENTRY audio transport is unavailable")
            if name == "adjust_system_volume":
                return self._adjust_once(arguments, context)
            return {"status": "SUCCEEDED", "result": self.audio_client.audio(name, arguments)}
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

    def _adjust_once(self, arguments: dict[str, Any], context: InvocationContext) -> dict[str, Any]:
        """Reserve in the existing action ledger before the relative host effect.

        A duplicate never claims an uncertain attempt again, including across
        Core restarts and an HTTP result lost after the host incremented.
        Current policy and membership are checked before reaching this method.
        """
        request = context.audio_action_request
        binding = {
            "principal_id": str(context.principal_id),
            "origin": context.origin.value,
            "tool_request_id": str(context.tool_request_id),
            "ordinal": context.ordinal,
        }
        if (
            self.action_store is None
            or request is None
            or request.action_id != context.tool_request_id
            or request.household_id != context.household_id
            or request.identity.principal_id != context.principal_id
            or request.origin != context.origin
            or request.tool_request_number != context.ordinal
            or request.tool.tool_id != "anima.sentry-control.adjust_system_volume"
            or request.arguments != {**arguments, "_invocation": binding}
            or request.idempotency_key
            != f"sentry-audio:{context.household_id}:{context.system_idempotency_key}"
        ):
            raise PluginValidationError("SENTRY relative audio requires a durable Core binding")
        unknown = {"status": "UNKNOWN_RESULT", "result": {}, "outcome": "UNKNOWN_RESULT"}
        claim = self.action_store.claim(request)
        if claim.idempotency_conflict:
            raise PluginValidationError("SENTRY audio idempotency conflict; no dispatch")
        if claim.duplicate:
            if claim.record.status == ActionStatus.SUCCEEDED and claim.record.result:
                return dict(claim.record.result)
            return unknown
        self.action_store.update(
            request.action_id,
            ActionStatus.EXECUTING,
            detail="relative audio attempt reserved before host dispatch; never replay",
        )
        assert self.audio_client is not None
        try:
            result = {
                "status": "SUCCEEDED",
                "result": self.audio_client.audio("adjust_system_volume", arguments),
            }
        except Exception:
            self.action_store.update(
                request.action_id,
                ActionStatus.UNKNOWN_RESULT,
                detail="relative host result unavailable; no retry or replay",
                result=unknown,
            )
            return unknown
        # A failed terminal write leaves EXECUTING, hence an uncertain duplicate
        # cannot repeat the effect even if the host returned a result once.
        self.action_store.update(request.action_id, ActionStatus.SUCCEEDED, result=result)
        return result
