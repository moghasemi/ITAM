from django.test import SimpleTestCase

from apps.assets.hwagent_service import (
    generate_technical_spec_summary,
    parse_hwagent_json,
)


class HWAgentPayloadCompatibilityTests(SimpleTestCase):
    def test_desktop_motherboard_key_is_normalized_to_baseboard(self):
        payload = {
            "computerName": "TEST-PC",
            "motherboard": {
                "manufacturer": "Example Board Inc.",
                "product": "B760M",
                "serial": "MB-12345",
            },
            "cpu": {"name": "Example CPU", "cores": 8, "threads": 16, "speed": 4200},
        }

        normalized = parse_hwagent_json(payload)

        self.assertEqual(normalized["baseboard"], payload["motherboard"])
        self.assertEqual(normalized["motherboard"], payload["motherboard"])
        summary = generate_technical_spec_summary(normalized)
        self.assertIn("MB: Example Board Inc. B760M", summary)

    def test_legacy_baseboard_key_remains_supported(self):
        payload = {
            "computerName": "LEGACY-PC",
            "baseboard": {"manufacturer": "Legacy", "product": "H510", "serial": "OLD-1"},
        }

        normalized = parse_hwagent_json(payload)

        self.assertEqual(normalized["motherboard"], payload["baseboard"])
        self.assertIn("MB: Legacy H510", generate_technical_spec_summary(normalized))

    def test_payload_without_hardware_fields_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_hwagent_json({"timestamp": "2026-11-10 12:00:00"})
