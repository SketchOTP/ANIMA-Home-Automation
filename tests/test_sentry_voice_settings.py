import unittest

from anima_ha.sentry_voice_settings import validate_voice_settings


class SentryVoiceSettingsTests(unittest.TestCase):
    def test_sleep_mode_is_household_setting_with_standby_default(self):
        self.assertEqual(
            validate_voice_settings(None),
            {"voice_id": "bm_george", "speech_speed": 0.9, "sleep_enabled": False},
        )
        self.assertTrue(validate_voice_settings({"sleep_enabled": True})["sleep_enabled"])

    def test_sleep_mode_rejects_non_boolean_values(self):
        with self.assertRaises(ValueError):
            validate_voice_settings({"sleep_enabled": "true"})
