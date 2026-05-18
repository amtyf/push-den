import unittest
from typing import List
from unittest.mock import Mock


def build_apns_single_payload(device_token: str) -> dict:
    return {
        "force_exit_on": [413],
        "type": "apns",
        "device_token": device_token,
        "send_mode": "alert",
        "notification": {
            "title": "sample-title",
            "data": {
                "message_title": "sample-title",
                "message_body": "sample-message",
            },
        },
    }


def build_apns_multi_payload(device_tokens: List[str]) -> dict:
    return {
        "force_exit_on": [413],
        "type": "apns",
        "device_tokens": device_tokens,
        "send_mode": "alert",
        "notification": {
            "title": "sample-title",
            "data": {
                "message_title": "sample-title",
                "message_body": "sample-message",
            },
        },
    }


class TestApnsPayloads(unittest.TestCase):
    def test_build_single_payload_has_expected_structure(self) -> None:
        payload = build_apns_single_payload("token-1")

        self.assertEqual(payload["type"], "apns")
        self.assertEqual(payload["send_mode"], "alert")
        self.assertEqual(payload["device_token"], "token-1")
        self.assertEqual(payload["notification"]["data"]["message_title"], "sample-title")

    def test_build_multiple_payload_has_expected_structure(self) -> None:
        tokens = ["token-1", "token-2"]
        payload = build_apns_multi_payload(tokens)

        self.assertEqual(payload["type"], "apns")
        self.assertEqual(payload["device_tokens"], tokens)
        self.assertEqual(payload["notification"]["title"], "sample-title")

    def test_processor_is_called_for_single_and_multiple_payloads(self) -> None:
        processor = Mock()
        single_payload = build_apns_single_payload("token-1")
        multi_payload = build_apns_multi_payload(["token-1", "token-2"])

        processor.process_message(single_payload)
        processor.process_message(multi_payload)

        self.assertEqual(processor.process_message.call_count, 2)
        processor.process_message.assert_any_call(single_payload)
        processor.process_message.assert_any_call(multi_payload)


if __name__ == "__main__":
    unittest.main()


