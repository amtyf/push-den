import unittest
from typing import List
from unittest.mock import Mock


def build_fcm_single_payload(device_tokens: List[str]) -> dict:
    return {
        "type": "fcm",
        "device_tokens": device_tokens,
        "device_token": device_tokens[0],
        "send_mode": "single_data",
        "notification": {
            "data": {
                "message_title": "sample-title",
                "message_body": "sample-message",
            }
        },
    }


def build_fcm_multi_payload(device_tokens: List[str]) -> dict:
    return {
        "type": "fcm",
        "device_tokens": device_tokens,
        "send_mode": "multiple_data",
        "notification": {
            "data": {
                "message_title": "sample-title",
                "message_body": "sample-message",
            }
        },
    }


class TestFcmPayloads(unittest.TestCase):
    def test_build_single_payload_has_expected_structure(self) -> None:
        payload = build_fcm_single_payload(["token-1", "token-2"])

        self.assertEqual(payload["type"], "fcm")
        self.assertEqual(payload["send_mode"], "single_data")
        self.assertEqual(payload["device_token"], "token-1")
        self.assertEqual(payload["notification"]["data"]["message_body"], "sample-message")

    def test_build_multiple_payload_has_expected_structure(self) -> None:
        tokens = ["token-1", "token-2"]
        payload = build_fcm_multi_payload(tokens)

        self.assertEqual(payload["type"], "fcm")
        self.assertEqual(payload["send_mode"], "multiple_data")
        self.assertEqual(payload["device_tokens"], tokens)

    def test_processor_is_called_for_single_and_multiple_payloads(self) -> None:
        processor = Mock()
        tokens = ["token-1", "token-2"]
        single_payload = build_fcm_single_payload(tokens)
        multi_payload = build_fcm_multi_payload(tokens)

        processor.process_message(single_payload)
        processor.process_message(multi_payload)

        self.assertEqual(processor.process_message.call_count, 2)
        processor.process_message.assert_any_call(single_payload)
        processor.process_message.assert_any_call(multi_payload)


if __name__ == "__main__":
    unittest.main()


