import unittest

from push_den.enums.fcm import FcmSenderType
from push_den.notificationfactory.fcm_factory.fcm_notification import (
    FcmNotification,
)


class TestFcmPayloadSize(unittest.TestCase):
    def test_calculate_payload_size_single_notification(self):
        payload = {
            "send_mode": FcmSenderType.SINGLE,
            "device_token": "device-token-1",
            "notification": {
                "message_title": "Hello",
                "message_body": "World",
                "data": {"k": "v"},
            },
        }

        result = FcmNotification.calculate_payload_size(payload)
        expected_size = len(
            FcmNotification._build_payload_for_size(
                FcmSenderType.SINGLE, payload["notification"]
            )
        )

        self.assertEqual(result["payload_size_bytes"], expected_size)
        self.assertEqual(result["target_count"], 1)
        self.assertEqual(result["total_payload_size_bytes"], expected_size)
        self.assertTrue(result["is_within_limit"])
        self.assertEqual(result["overflow_bytes"], 0)

    def test_calculate_payload_size_single_data_uses_data_only(self):
        payload = {
            "send_mode": FcmSenderType.SINGLE_DATA,
            "device_token": "device-token-1",
            "notification": {
                "message_title": "Ignored title",
                "message_body": "Ignored body",
                "data": {"message": "data-only"},
            },
        }

        result = FcmNotification.calculate_payload_size(payload)
        expected_size = len(
            FcmNotification._build_payload_for_size(
                FcmSenderType.SINGLE_DATA, payload["notification"]
            )
        )

        self.assertEqual(result["payload_size_bytes"], expected_size)

    def test_calculate_payload_size_multiple_total(self):
        payload = {
            "send_mode": FcmSenderType.MULTIPLE,
            "device_tokens": ["a", "b", "c"],
            "notification": {
                "message_title": "Title",
                "message_body": "Body",
                "data": {"foo": "bar"},
            },
        }

        result = FcmNotification.calculate_payload_size(payload)
        expected_single = len(
            FcmNotification._build_payload_for_size(
                FcmSenderType.MULTIPLE, payload["notification"]
            )
        )

        self.assertEqual(result["target_count"], 3)
        self.assertEqual(result["payload_size_bytes"], expected_single)
        self.assertEqual(result["total_payload_size_bytes"], expected_single * 3)

    def test_calculate_payload_size_over_4kb_limit(self):
        payload = {
            "send_mode": FcmSenderType.SINGLE,
            "device_token": "device-token-1",
            "notification": {
                "message_title": "Large",
                "message_body": "x" * 5000,
                "data": {"k": "v"},
            },
        }

        result = FcmNotification.calculate_payload_size(payload)

        self.assertGreater(result["payload_size_bytes"], 4096)
        self.assertFalse(result["is_within_limit"])
        self.assertEqual(result["overflow_bytes"], result["payload_size_bytes"] - 4096)

    def test_calculate_payload_size_requires_token_for_single(self):
        payload = {
            "send_mode": FcmSenderType.SINGLE,
            "notification": {
                "message_title": "Hello",
                "message_body": "World",
                "data": {"k": "v"},
            },
        }

        with self.assertRaises(Exception):
            FcmNotification.calculate_payload_size(payload)


if __name__ == "__main__":
    unittest.main()
