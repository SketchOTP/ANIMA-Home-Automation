import unittest
from typing import Any, cast
from uuid import UUID, uuid4

from anima_ha.plugins import InvocationContext, PluginValidationError
from anima_ha.policy import RequestOrigin
from anima_ha.sentry_voice_settings import (
    SENTRY_CONTROL_MANIFEST,
    SentryControlNativePlugin,
    validate_voice_settings,
)


class SentryVoiceSettingsTests(unittest.TestCase):
    def test_sleep_mode_is_household_setting_with_standby_default(self) -> None:
        self.assertEqual(
            validate_voice_settings(None),
            {
                "voice_id": "bm_george",
                "speech_speed": 0.9,
                "sleep_enabled": False,
                "active_instance_id": "living_room",
            },
        )
        self.assertTrue(validate_voice_settings({"sleep_enabled": True})["sleep_enabled"])

    def test_active_instance_is_bounded_to_installed_faces(self) -> None:
        self.assertEqual(
            validate_voice_settings({"active_instance_id": "office"})["active_instance_id"],
            "office",
        )
        with self.assertRaises(ValueError):
            validate_voice_settings({"active_instance_id": "bedroom"})

    def test_sleep_mode_rejects_non_boolean_values(self) -> None:
        with self.assertRaises(ValueError):
            validate_voice_settings({"sleep_enabled": "true"})

    def test_voice_catalogue_exposes_only_one_way_sleep_control(self) -> None:
        tool = SENTRY_CONTROL_MANIFEST.tools[0]
        self.assertEqual(tool["name"], "enter_sleep_mode")
        self.assertNotIn("wake", tool["name"])
        self.assertEqual(tool["input_schema"]["additionalProperties"], False)

    def test_sleep_control_preserves_voice_settings_and_cannot_wake(self) -> None:
        class Store:
            def __init__(self) -> None:
                self.value: dict[str, Any] = {
                    "voice_id": "bm_george",
                    "speech_speed": 0.9,
                    "sleep_enabled": False,
                    "active_instance_id": "living_room",
                }
                self.updates: list[tuple[UUID, dict[str, Any]]] = []

            def get(self, household_id: UUID) -> dict[str, Any]:
                del household_id
                return dict(self.value)

            def update(self, household_id: UUID, value: dict[str, Any]) -> dict[str, Any]:
                self.updates.append((household_id, dict(value)))
                self.value = dict(value)
                return dict(value)

        store = Store()
        plugin = SentryControlNativePlugin(cast(Any, store))
        context = InvocationContext(
            household_id=uuid4(),
            principal_id=uuid4(),
            episode_id=None,
            tool_request_id=uuid4(),
            ordinal=1,
            system_idempotency_key="test:sentry-sleep",
            origin=RequestOrigin.DIRECT_USER,
        )
        result = plugin.invoke_with_invocation_context("enter_sleep_mode", {}, 1.0, context)
        self.assertEqual(
            result,
            {"status": "SUCCEEDED", "sleep_enabled": True, "wake_available": False},
        )
        self.assertTrue(store.value["sleep_enabled"])
        self.assertEqual(store.value["voice_id"], "bm_george")
        self.assertEqual(store.value["speech_speed"], 0.9)
        self.assertEqual(store.value["active_instance_id"], "living_room")
        with self.assertRaises(PluginValidationError):
            plugin.invoke_with_invocation_context("exit_sleep_mode", {}, 1.0, context)
