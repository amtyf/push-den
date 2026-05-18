import unittest

from push_den.enums.apns import ApnsSenderType
from push_den.notificationfactory.apns_factory.apns_notification import (
    ApnsNotification,
)


class TestApnsPayloadSize(unittest.TestCase):
    def setUp(self):
        # Bypass __init__ to avoid file/env dependency for APNS key loading.
        self.apns_notification = ApnsNotification.__new__(ApnsNotification)
        self.apns_notification.max_list_size = 1000

    def test_calculate_payload_size_mutable_single_device(self):
        payload = {
            "send_mode": ApnsSenderType.MUTABLE,
            "device_token": "device-token-1",
            "notification": {
                "title": "Hello",
                "data": "Hello from mutable",
            },
        }

        result = self.apns_notification.calculate_payload_size(payload)
        expected_size = len(
            self.apns_notification._build_payload(
                "alert", "Hello from mutable", title="Hello", mutable_content=True
            )
        )

        self.assertEqual(result["payload_size_bytes"], expected_size)
        self.assertEqual(result["target_count"], 1)
        self.assertEqual(result["total_payload_size_bytes"], expected_size)
        self.assertTrue(result["is_within_limit"])
        self.assertEqual(result["overflow_bytes"], 0)

    def test_calculate_payload_size_immutable_uses_message_body(self):
        payload = {
            "send_mode": ApnsSenderType.IMMUTABLE,
            "device_token": "device-token-1",
            "notification": {
                "title": "Immutable Title",
                "data": "should-not-be-used",
                "message_body": "immutable-body",
            },
        }

        result = ApnsNotification.calculate_payload_size(payload)
        expected_size = len(
            self.apns_notification._build_payload(
                "alert",
                "immutable-body",
                title="Immutable Title",
                mutable_content=False,
            )
        )

        self.assertEqual(result["payload_size_bytes"], expected_size)

    def test_calculate_payload_size_device_list_total(self):
        payload = {
            "send_mode": ApnsSenderType.BACKGROUND,
            "device_tokens": ["a", "b", "c"],
            "notification": {
                "title": "Background",
                "data": "Background body",
            },
        }

        result = self.apns_notification.calculate_payload_size(payload)
        expected_single = len(
            self.apns_notification._build_payload(
                "background",
                "Background body",
                title="Background",
                mutable_content=True,
            )
        )

        self.assertEqual(result["target_count"], 3)
        self.assertEqual(result["payload_size_bytes"], expected_single)
        self.assertEqual(result["total_payload_size_bytes"], expected_single * 3)

    def test_calculate_payload_size_over_4kb_limit(self):
        very_large_message = "x" * 5000
        payload = {
            "send_mode": ApnsSenderType.MUTABLE,
            "device_token": "device-token-1",
            "notification": {
                "title": "Large",
                "data": very_large_message,
            },
        }

        result = self.apns_notification.calculate_payload_size(payload)

        self.assertGreater(result["payload_size_bytes"], 4096)
        self.assertFalse(result["is_within_limit"])
        self.assertEqual(result["overflow_bytes"], result["payload_size_bytes"] - 4096)


if __name__ == "__main__":
    unittest.main()
