import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import Mock, patch

import httpx
import pytest

from push_den.base import BaseAPI
from push_den.enums.apns import ApnsSenderType
from push_den.enums.fcm import FcmSenderType
from push_den.notification import Notification
from push_den.notificationfactory.apns_factory.apns_notification import (
    ApnsNotification,
    ResponseCompat,
)
from push_den.notificationfactory.custom_factory.test_notifier import TestNotifier
from push_den.notificationfactory.fcm_factory.fcm_notification import FcmNotification
from push_den.notificationfactory.notification_factory import NotificationFactory
from push_den.processor.notification_processor import NotificationProcessor


class FakeSyncApnsClient:
    def __init__(self, *args, **kwargs):
        self.base_url = str(kwargs.get("base_url"))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, path, content=None, headers=None):
        reg_id = path.rsplit("/", 1)[-1]
        if reg_id == "retry" and "sandbox" not in self.base_url:
            return httpx.Response(400, content=b"retry")
        return httpx.Response(200, content=f"{self.base_url}:{reg_id}".encode("utf-8"))


class FakeAsyncApnsClient:
    def __init__(self, *args, **kwargs):
        self.base_url = str(kwargs.get("base_url"))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, path, content=None, headers=None):
        reg_id = path.rsplit("/", 1)[-1]
        if reg_id in {"slow", "slow2"}:
            await asyncio.sleep(5.0)
        if reg_id == "boom":
            raise RuntimeError("boom")
        if reg_id == "retry" and "sandbox" not in self.base_url:
            return httpx.Response(400, content=b"retry")
        return httpx.Response(200, content=f"{self.base_url}:{reg_id}".encode("utf-8"))


class FakeSendResponse:
    def __init__(self, payload, error):
        self.payload = payload
        self.error = error


def _key_file(tmp_path: Path, name: str) -> str:
    key_path = tmp_path / name
    key_path.write_text("secret-key", encoding="utf-8")
    return str(key_path)


class TestCoreCoverage:
    def test_notification_abstract_methods_raise(self):
        notification = Notification()

        with pytest.raises(NotImplementedError):
            notification.notify_single_device()
        with pytest.raises(NotImplementedError):
            notification.notify_multiple_devices()
        with pytest.raises(NotImplementedError):
            notification.send()

    def test_notification_factory_register_lookup_and_validation(self):
        factory = NotificationFactory()
        first = Mock(name="first")
        second = Mock(name="second")
        third = Mock(name="third")

        factory.register("first", first)
        factory.register("second", second)
        factory.register("third", third, default=True)

        assert factory.get_api() is third
        assert factory.get_api("first") is first
        assert factory.get_api_list() == [third]
        assert factory.get_api_list(["first", "second"]) == [first, second]

        with pytest.raises(NameError, match="Unsupported factory: missing"):
            factory.get_api("missing")
        with pytest.raises(NameError, match="Unsupported factory: missing"):
            factory.get_api_list(["missing"])

    def test_processor_registers_factories_and_routes_messages(self):
        fcm_sender = Mock()
        fcm_sender.send.return_value = "fcm-response"
        apns_sender = Mock()
        apns_sender.send.return_value = "apns-response"

        with patch(
            "push_den.processor.notification_processor.FcmNotification",
            return_value=fcm_sender,
        ), patch(
            "push_den.processor.notification_processor.ApnsNotification",
            return_value=apns_sender,
        ):
            processor = NotificationProcessor(fcm="fcm-key", apns="apns-key")

        assert isinstance(processor.factory.get_api("custom"), TestNotifier)
        assert processor.factory.get_api("fcm") is fcm_sender
        assert processor.factory.get_api("apns") is apns_sender

        assert processor.process_message({"type": "fcm", "payload": 1}) == "fcm-response"
        assert processor.process_message({"type": "apns", "payload": 2}) == "apns-response"
        assert processor.process_message({"type": "custom", "payload": 3}) is None

        fcm_sender.send.assert_called_once_with({"type": "fcm", "payload": 1})
        apns_sender.send.assert_called_once_with({"type": "apns", "payload": 2})

    def test_custom_notifier_send_prints_payload(self, capsys):
        notifier = TestNotifier()
        notifier.send({"message": "hello"})

        output = capsys.readouterr().out
        assert "Testing factory..." in output
        assert "message" in output

    def test_base_api_init_and_methods(self, tmp_path):
        cert_file = _key_file(tmp_path, "firebase.json")

        with patch("push_den.base.Certificate", return_value="cert") as cert_cls, patch(
            "push_den.base.firebase_admin.initialize_app", return_value="app"
        ) as init_app:
            api = BaseAPI(cert_file)

        cert_cls.assert_called_once_with(cert_file)
        init_app.assert_called_once_with(credential="cert")
        assert api.MAX_TTL == 2419200

        with pytest.raises(Exception, match="Certificate name must be provided."):
            BaseAPI(None)

        with patch("push_den.base.validate") as validate_mock, patch(
            "push_den.base.messaging.Message", return_value="message"
        ) as msg_cls, patch(
            "push_den.base.messaging.Notification", return_value="notification"
        ) as notif_cls, patch(
            "push_den.base.messaging.AndroidConfig", return_value="android"
        ) as android_cls, patch(
            "push_den.base.messaging.AndroidNotification", return_value="android-notification"
        ) as android_notif_cls, patch(
            "push_den.base.messaging.send", return_value="single-response"
        ) as send_mock:
            single_result = api.notify_single_device(
                "token-1",
                {
                    "message_title": "Title",
                    "message_body": "Body",
                    "priority": "high",
                    "ttl": 60,
                },
            )

        assert single_result == "single-response"
        validate_mock.assert_called_once()
        msg_cls.assert_called_once()
        notif_cls.assert_called_once()
        android_cls.assert_called_once()
        android_notif_cls.assert_called_once()
        send_mock.assert_called_once_with("message")

        with pytest.raises(Exception, match="Must provide a device token."):
            api.notify_single_device(None, {"message_title": "T", "message_body": "B"})
        with pytest.raises(Exception, match="Notification data must be provided."):
            api.notify_single_device("token-1", None)

        with patch("push_den.base.validate") as validate_mock, patch(
            "push_den.base.messaging.MulticastMessage", return_value="multicast-message"
        ) as multicast_cls, patch(
            "push_den.base.messaging.Notification", return_value="notification"
        ), patch(
            "push_den.base.messaging.AndroidConfig", return_value="android"
        ), patch(
            "push_den.base.messaging.AndroidNotification", return_value="android-notification"
        ), patch(
            "push_den.base.messaging.send_multicast", return_value="multi-response"
        ) as send_multicast_mock:
            multi_result = api.notify_multiple_devices(
                ["token-1", "token-2"],
                {
                    "message_title": "Title",
                    "message_body": "Body",
                    "priority": "normal",
                    "ttl": 120,
                },
            )

        assert multi_result == "multi-response"
        validate_mock.assert_called_once()
        multicast_cls.assert_called_once()
        send_multicast_mock.assert_called_once_with("multicast-message")

        with pytest.raises(Exception, match="Must provide device tokens."):
            api.notify_multiple_devices([], {"message_title": "T", "message_body": "B"})
        with pytest.raises(Exception, match="Notification data must be provided."):
            api.notify_multiple_devices(["token-1"], None)

        with patch("push_den.base.validate") as validate_mock, patch(
            "push_den.base.messaging.Message", return_value="data-message"
        ) as msg_cls, patch(
            "push_den.base.messaging.AndroidConfig", return_value="android"
        ) as android_cls, patch(
            "push_den.base.messaging.send", return_value="data-response"
        ) as send_mock:
            data_result = api.single_device_data_message(
                "token-1",
                {"data": {"priority": "high", "ttl": 10, "value": "x"}},
            )

        assert data_result == "data-response"
        validate_mock.assert_called_once()
        msg_cls.assert_called_once()
        android_cls.assert_called_once()
        send_mock.assert_called_once_with("data-message")

        with pytest.raises(Exception, match="Must provide a device token."):
            api.single_device_data_message(None, {"data": {"value": "x"}})
        with pytest.raises(Exception, match="Data must be provided."):
            api.single_device_data_message("token-1", None)

        with patch("push_den.base.validate") as validate_mock, patch(
            "push_den.base.messaging.MulticastMessage", return_value="data-multicast"
        ) as multicast_cls, patch(
            "push_den.base.messaging.AndroidConfig", return_value="android"
        ), patch(
            "push_den.base.messaging.send_multicast", return_value="data-multi-response"
        ) as send_multicast_mock:
            multi_data_result = api.multiple_devices_data_message(
                ["token-1", "token-2"],
                {"data": {"priority": "normal", "ttl": 10, "value": "x"}},
            )

        assert multi_data_result == "data-multi-response"
        validate_mock.assert_called_once()
        multicast_cls.assert_called_once()
        send_multicast_mock.assert_called_once_with("data-multicast")

        with pytest.raises(Exception, match="Must provide device tokens."):
            api.multiple_devices_data_message([], {"data": {"value": "x"}})
        with pytest.raises(Exception, match="Data must be provided."):
            api.multiple_devices_data_message(["token-1"], None)

    def test_fcm_init_validation_send_and_size_helpers(self, tmp_path):
        cert_file = _key_file(tmp_path, "fcm.json")

        with pytest.raises(Exception, match="Certificate name must be provided."):
            FcmNotification(None)

        with patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.Certificate",
            return_value="cert",
        ) as cert_cls, patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.firebase_admin.initialize_app",
            return_value="app",
        ) as init_app:
            fcm = FcmNotification(cert_file)

        cert_cls.assert_called_once_with(cert_file)
        init_app.assert_called_once_with(credential="cert")
        assert fcm.MAX_TTL == 2419200

        blank = cast(FcmNotification, FcmNotification.__new__(FcmNotification))
        blank.MAX_TTL = 2419200

        with pytest.raises(Exception, match="Must provide a device token."):
            blank.notify_multiple_devices(None, {"message_title": "T", "message_body": "B"})
        with pytest.raises(Exception, match="Must provide a device token."):
            blank.validate_data(None, {"message_title": "T", "message_body": "B"})
        with pytest.raises(Exception, match="Must provide a device token."):
            blank.single_device_data_message(None, {"data": {"value": "x"}})
        with pytest.raises(Exception, match="Data must be provided."):
            blank.single_device_data_message("token-1", {"data": None})
        with pytest.raises(Exception, match="Must provide device tokens."):
            blank.multiple_devices_data_message([], {"data": {"value": "x"}})
        with pytest.raises(Exception, match="Must provide device tokens."):
            blank.multiple_devices_data_message(None, {"data": {"value": "x"}})
        with pytest.raises(Exception, match="Data must be provided."):
            blank.multiple_devices_data_message(["token-1"], {"data": None})

        with pytest.raises(Exception, match="Must provide a device token."):
            blank.validate_data([], {"message_title": "T"})
        with pytest.raises(Exception, match="Notification data must be provided."):
            blank.validate_data(["token-1"], None)

        with patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.validate"
        ) as validate_mock:
            blank.validate_data(
                ["token-1"],
                {
                    "message_title": "Title",
                    "message_body": "Body",
                    "data": {"priority": "high", "ttl": 10},
                },
            )
        assert validate_mock.call_count == 2

        with patch.object(blank, "validate_data") as validate_data_mock, patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.SendResponse",
            side_effect=FakeSendResponse,
        ), patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.messaging.Message",
            return_value="message",
        ) as msg_cls, patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.messaging.Notification",
            return_value="notification",
        ), patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.messaging.AndroidConfig",
            return_value="android",
        ), patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.messaging.AndroidNotification",
            return_value="android-notification",
        ), patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.messaging.AndroidFCMOptions",
            return_value="android-fcm-options",
        ), patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.messaging.send",
            return_value="message-id",
        ) as send_mock:
            single_result = blank.notify_single_device(
                "token-1",
                {
                    "message_title": "Title",
                    "message_body": "Body",
                    "data": {"priority": "high", "ttl": 10},
                    "priority": "high",
                    "ttl": 10,
                },
            )

        assert isinstance(single_result, FakeSendResponse)
        assert single_result.payload == {"name": "message-id"}
        assert single_result.error is None
        validate_data_mock.assert_called_once()
        msg_cls.assert_called_once()
        send_mock.assert_called_once_with("message")

        with patch.object(blank, "validate_data") as validate_data_mock, patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.SendResponse",
            side_effect=FakeSendResponse,
        ), patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.messaging.send",
            side_effect=RuntimeError("boom"),
        ) as send_mock:
            error_result = blank.notify_single_device(
                "token-1",
                {
                    "message_title": "Title",
                    "message_body": "Body",
                    "data": {"priority": "high", "ttl": 10},
                },
            )

        assert error_result.payload is None
        assert error_result.error == "boom"
        validate_data_mock.assert_called_once()
        send_mock.assert_called_once()

        with patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.messaging.send_each_for_multicast",
            return_value="multi-result",
        ) as send_each_mock, patch.object(blank, "validate_data") as validate_data_mock:
            multi_result = blank.notify_multiple_devices(
                ["token-1", "token-2"],
                {
                    "message_title": "Title",
                    "message_body": "Body",
                    "data": {"priority": "normal", "ttl": 10},
                },
            )

        assert multi_result == "multi-result"
        validate_data_mock.assert_called_once()
        send_each_mock.assert_called_once()

        with patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.validate"
        ) as validate_mock, patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.messaging.send",
            return_value="data-message-id",
        ) as send_mock, patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.SendResponse",
            side_effect=FakeSendResponse,
        ):
            data_result = blank.single_device_data_message(
                "token-1",
                {"data": {"priority": "normal", "ttl": 10, "value": "x"}},
            )

        assert data_result.payload == {"name": "data-message-id"}
        assert data_result.error is None
        validate_mock.assert_called_once()
        send_mock.assert_called_once()

        with patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.validate"
        ) as validate_mock, patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.messaging.send",
            side_effect=RuntimeError("data-boom"),
        ) as send_mock, patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.SendResponse",
            side_effect=FakeSendResponse,
        ):
            data_error = blank.single_device_data_message(
                "token-1",
                {"data": {"priority": "normal", "ttl": 10, "value": "x"}},
            )

        assert data_error.payload is None
        assert data_error.error == "data-boom"
        validate_mock.assert_called_once()
        send_mock.assert_called_once()

        with patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.messaging.send_each_for_multicast",
            return_value="data-multi-result",
        ) as send_each_mock, patch(
            "push_den.notificationfactory.fcm_factory.fcm_notification.validate"
        ) as validate_mock:
            data_multi_result = blank.multiple_devices_data_message(
                ["token-1", "token-2"],
                {"data": {"priority": "high", "ttl": 10, "value": "x"}},
            )

        assert data_multi_result == "data-multi-result"
        validate_mock.assert_called_once()
        send_each_mock.assert_called_once()

        with patch.object(blank, "notify_single_device", return_value="single") as single_mock, patch.object(
            blank, "notify_multiple_devices", return_value="multi"
        ) as multi_mock, patch.object(blank, "single_device_data_message", return_value="single-data") as single_data_mock, patch.object(
            blank, "multiple_devices_data_message", return_value="multi-data"
        ) as multi_data_mock:
            assert blank.send(
                {
                    "send_mode": FcmSenderType.SINGLE,
                    "device_token": "token-1",
                    "notification": {"message_title": "T", "message_body": "B"},
                }
            ) == "single"
            assert blank.send(
                {
                    "send_mode": FcmSenderType.MULTIPLE,
                    "device_tokens": ["token-1"],
                    "notification": {"message_title": "T", "message_body": "B"},
                }
            ) == "multi"
            assert blank.send(
                {
                    "send_mode": FcmSenderType.SINGLE_DATA,
                    "device_token": "token-1",
                    "notification": {"data": {"priority": "high", "ttl": 10}},
                }
            ) == "single-data"
            assert blank.send(
                {
                    "send_mode": FcmSenderType.MULTIPLE_DATA,
                    "device_tokens": ["token-1"],
                    "notification": {"data": {"priority": "high", "ttl": 10}},
                }
            ) == "multi-data"

        single_mock.assert_called_once()
        multi_mock.assert_called_once()
        single_data_mock.assert_called_once()
        multi_data_mock.assert_called_once()

        with pytest.raises(Exception, match="Message must be provided."):
            blank.send(None)
        with pytest.raises(Exception, match="send_mode must be provided."):
            blank.send({})
        with pytest.raises(Exception, match="Invalid FcmSenderType."):
            blank.send({"send_mode": "invalid", "notification": {}})

        assert FcmNotification._build_payload_for_size(
            FcmSenderType.SINGLE,
            {
                "message_title": "Title",
                "message_body": "Body",
                "data": {"priority": "high", "ttl": 10},
            },
        )
        assert FcmNotification._build_payload_for_size(
            FcmSenderType.SINGLE_DATA,
            {"data": {"priority": "high", "ttl": 10}},
        )
        with pytest.raises(Exception, match="Notification data must be provided."):
            FcmNotification._build_payload_for_size(FcmSenderType.SINGLE, None)
        with pytest.raises(Exception, match="Data must be provided."):
            FcmNotification._build_payload_for_size(FcmSenderType.SINGLE_DATA, {})
        with pytest.raises(Exception, match="Invalid FcmSenderType."):
            FcmNotification._build_payload_for_size("invalid", {"data": {"priority": "high", "ttl": 10}})

        single_size = FcmNotification.calculate_payload_size(
            {
                "send_mode": FcmSenderType.SINGLE,
                "device_token": "token-1",
                "notification": {
                    "message_title": "Hello",
                    "message_body": "World",
                    "data": {"k": "v"},
                },
            }
        )
        assert single_size["target_count"] == 1
        assert single_size["payload_size_bytes"] > 0

        multiple_size = FcmNotification.calculate_payload_size(
            {
                "send_mode": FcmSenderType.MULTIPLE,
                "device_tokens": ["a", "b", "c"],
                "notification": {
                    "message_title": "Hello",
                    "message_body": "World",
                    "data": {"k": "v"},
                },
            }
        )
        assert multiple_size["target_count"] == 3
        assert multiple_size["total_payload_size_bytes"] == multiple_size["payload_size_bytes"] * 3

        with pytest.raises(Exception, match="Message must be provided."):
            FcmNotification.calculate_payload_size(None)
        with pytest.raises(Exception, match="Notification data must be provided."):
            FcmNotification.calculate_payload_size(
                {"send_mode": FcmSenderType.SINGLE, "device_token": "token-1"}
            )
        with pytest.raises(Exception, match="send_mode must be provided."):
            FcmNotification.calculate_payload_size({"device_token": "token-1", "notification": {}})
        with pytest.raises(Exception, match="Must provide a device token."):
            FcmNotification.calculate_payload_size(
                {"send_mode": FcmSenderType.SINGLE, "notification": {}}
            )
        with pytest.raises(Exception, match="Must provide device tokens."):
            FcmNotification.calculate_payload_size(
                {"send_mode": FcmSenderType.MULTIPLE, "notification": {}}
            )
        with pytest.raises(Exception, match="Invalid FcmSenderType."):
            FcmNotification.calculate_payload_size(
                {"send_mode": "invalid", "device_token": "token-1", "notification": {}}
            )

    def test_apns_response_compat_and_init_and_helpers(self, tmp_path):
        key_file = _key_file(tmp_path, "apns.key")
        with pytest.raises(KeyError):
            ApnsNotification(None)
        apns = ApnsNotification(
            {
                "APNS_AUTH_KEY": key_file,
                "TEAM_ID": "team-id",
                "ALGORITHM": "ES256",
                "APNS_KEY_ID": "key-id",
                "BUNDLE_ID": "com.example.push-den",
                "IOS_HTTP_URL": "api.push.apple.com:443",
                "IOS_HTTP_SANDBOX_URL": "sandbox.push.apple.com:443",
            }
        )

        assert apns.secret_key == "secret-key"
        assert apns._get_base_url() == "https://api.push.apple.com:443"
        assert apns._get_base_url(use_sandbox=True) == "https://sandbox.push.apple.com:443"

        apns.ios_http_url = 123
        apns.ios_http_sandbox_url = 456
        with pytest.raises(RuntimeError, match="IOS_HTTP_URL must be a string host or URL"):
            apns._get_base_url()
        with pytest.raises(RuntimeError, match="IOS_HTTP_SANDBOX_URL is not configured"):
            apns._get_base_url(use_sandbox=True)

        with patch(
            "push_den.notificationfactory.apns_factory.apns_notification.jwt.encode",
            return_value="signed-token",
        ) as encode_mock, patch(
            "push_den.notificationfactory.apns_factory.apns_notification.time.time",
            return_value=1000.0,
        ):
            headers = ApnsNotification.get_request_headers(
                apns, "alert", "1030", ".voip"
            )

        assert headers["apns-expiration"] == "1030"
        assert headers["apns-topic"] == "com.example.push-den.voip"
        assert headers["authorization"] == "bearer signed-token"
        assert headers["apns-push-type"] == "alert"
        encode_mock.assert_called_once()
        assert ApnsNotification.get_path("abc") == "/3/device/abc"

        compat = ResponseCompat(httpx.Response(201, content=b"hello"))
        assert compat.status == 201
        assert compat.read() == b"hello"

        with pytest.raises(ValueError, match="Unknown push type: invalid"):
            ApnsNotification._build_payload("invalid", "body")

    def test_apns_sync_and_async_requests_and_bulk(self, tmp_path):
        key_file = _key_file(tmp_path, "apns.key")
        apns = ApnsNotification(
            {
                "APNS_AUTH_KEY": key_file,
                "TEAM_ID": "team-id",
                "ALGORITHM": "ES256",
                "APNS_KEY_ID": "key-id",
                "BUNDLE_ID": "com.example.push-den",
                "IOS_HTTP_URL": "api.push.apple.com:443",
                "IOS_HTTP_SANDBOX_URL": "sandbox.push.apple.com:443",
            }
        )

        with patch(
            "push_den.notificationfactory.apns_factory.apns_notification.httpx.Client",
            FakeSyncApnsClient,
        ):
            response = apns._send_request(
                "/3/device/retry", b"{}", {"apns-push-type": "alert"}
            )

        assert response.status == 200
        assert response.read().startswith(b"https://sandbox.push.apple.com:443")

        async def run_async_request():
            with patch(
                "push_den.notificationfactory.apns_factory.apns_notification.httpx.AsyncClient",
                FakeAsyncApnsClient,
            ):
                client = FakeAsyncApnsClient(base_url="https://api.push.apple.com:443")
                return await apns._send_request_async(
                    client,
                    "/3/device/retry",
                    b"{}",
                    {"apns-push-type": "alert"},
                )

        async_response = asyncio.run(run_async_request())
        assert async_response.status_code == 200
        assert async_response.content.startswith(b"https://sandbox.push.apple.com:443")

        async def run_bulk_async():
            with patch(
                "push_den.notificationfactory.apns_factory.apns_notification.httpx.AsyncClient",
                FakeAsyncApnsClient,
            ):
                return await apns._send_to_apns_bulk_async(
                    [200],
                    b"{}",
                    ["retry", "slow", "slow2"],
                    {"apns-push-type": "alert"},
                )

        bulk_result = asyncio.run(run_bulk_async())
        assert bulk_result["exit"] is True
        assert bulk_result["responses"]

        async def run_bulk_exception_async():
            with patch(
                "push_den.notificationfactory.apns_factory.apns_notification.httpx.AsyncClient",
                FakeAsyncApnsClient,
            ):
                return await apns._send_to_apns_bulk_async(
                    [],
                    b"{}",
                    ["boom"],
                    {"apns-push-type": "alert"},
                )

        exception_bulk = asyncio.run(run_bulk_exception_async())
        assert exception_bulk["responses"][0]["boom"]["status"] == 0

        with patch(
            "push_den.notificationfactory.apns_factory.apns_notification.httpx.AsyncClient",
            FakeAsyncApnsClient,
        ):
            sync_bulk = apns.send_to_apns_bulk(
                [200],
                b"{}",
                ["retry"],
                {"apns-push-type": "alert"},
            )
        assert sync_bulk["responses"]

        async def call_bulk_inside_loop():
            with patch(
                "push_den.notificationfactory.apns_factory.apns_notification.httpx.AsyncClient",
                FakeAsyncApnsClient,
            ):
                return apns.send_to_apns_bulk(
                    [200],
                    b"{}",
                    ["retry"],
                    {"apns-push-type": "alert"},
                )

        loop_bulk = asyncio.run(call_bulk_inside_loop())
        assert loop_bulk["responses"]

    def test_apns_send_helpers_wrappers_dispatch_and_size(self, tmp_path):
        key_file = _key_file(tmp_path, "apns.key")
        apns = ApnsNotification(
            {
                "APNS_AUTH_KEY": key_file,
                "TEAM_ID": "team-id",
                "ALGORITHM": "ES256",
                "APNS_KEY_ID": "key-id",
                "BUNDLE_ID": "com.example.push-den",
                "IOS_HTTP_URL": "api.push.apple.com:443",
                "IOS_HTTP_SANDBOX_URL": "sandbox.push.apple.com:443",
                "MAX_LIST_SIZE": 2,
            }
        )

        with patch(
            "push_den.notificationfactory.apns_factory.apns_notification.jwt.encode",
            return_value="signed-token",
        ), patch(
            "push_den.notificationfactory.apns_factory.apns_notification.time.time",
            return_value=1000.0,
        ), patch.object(apns, "_send_request", return_value="single-response") as send_request_mock:
            assert apns._send_notification("voip", "hello", "token-1", ttl=30) == "single-response"
            assert apns._send_notification("background", "hello", "token-1", title="Back", ttl=30) == "single-response"
            assert apns._send_notification("alert", "hello", "token-1", title="Title", mutable_content=False, ttl=30) == "single-response"

        assert send_request_mock.call_count == 3

        with patch(
            "push_den.notificationfactory.apns_factory.apns_notification.jwt.encode",
            return_value="signed-token",
        ), patch(
            "push_den.notificationfactory.apns_factory.apns_notification.time.time",
            return_value=1000.0,
        ), patch.object(apns, "send_to_apns_bulk", return_value="bulk-response") as bulk_mock:
            assert apns._send_notification_list("voip", "hello", ["token-1"], ttl=30) == "bulk-response"
            assert apns._send_notification_list("background", "hello", ["token-1"], title="Back", ttl=30) == "bulk-response"
            assert apns._send_notification_list("alert", "hello", ["token-1"], title="Title", mutable_content=False, ttl=30) == "bulk-response"

        assert bulk_mock.call_count == 3

        with pytest.raises(RuntimeError, match="Exception occurred in _send_notification"):
            apns._send_notification("invalid", "hello", "token-1")
        with pytest.raises(RuntimeError, match="Exception occurred in _send_notification_list"):
            apns._send_notification_list("invalid", "hello", ["token-1"])

        with patch.object(
            apns, "_send_notification", return_value="wrapped-single"
        ) as single_mock, patch.object(
            apns, "_send_notification_list", return_value="wrapped-multi"
        ) as multi_mock:
            assert apns.ios_push_notification_voip("body", "token-1") == "wrapped-single"
            assert apns.ios_push_notification_background("body", "token-1") == "wrapped-single"
            assert apns.ios_push_notification_alert("body", "token-1") == "wrapped-single"
            assert apns.ios_push_notification_voip_list("body", ["token-1"]) == "wrapped-multi"
            assert apns.ios_push_notification_background_list("body", ["token-1"]) == "wrapped-multi"
            assert apns.ios_push_notification_alert_list("body", ["token-1"]) == "wrapped-multi"

        assert single_mock.call_count == 3
        assert multi_mock.call_count == 3

        with pytest.raises(RuntimeError, match="Message must be provided."):
            apns.send(None)
        with pytest.raises(RuntimeError, match="send_mode must be provided."):
            apns.send({})
        with pytest.raises(RuntimeError, match=r"device token\(s\) must be provided."):
            apns.send({"send_mode": ApnsSenderType.MUTABLE, "notification": {}})
        with pytest.raises(RuntimeError, match="Device tokens list size exceeds maximum of 2."):
            apns.send(
                {
                    "send_mode": ApnsSenderType.MUTABLE,
                    "device_tokens": ["a", "b", "c"],
                    "notification": {"data": "body", "title": "Title", "ttl": 30},
                }
            )

        with patch.object(apns, "ios_push_notification_voip", return_value="voip") as voip_mock, patch.object(
            apns, "ios_push_notification_background", return_value="background"
        ) as background_mock, patch.object(
            apns, "ios_push_notification_alert", side_effect=["alert", "immutable"]
        ) as alert_mock, patch.object(
            apns, "ios_push_notification_voip_list", return_value="voip-list"
        ) as voip_list_mock, patch.object(
            apns, "ios_push_notification_background_list", return_value="background-list"
        ) as background_list_mock, patch.object(
            apns, "ios_push_notification_alert_list", return_value="alert-list"
        ) as alert_list_mock:
            assert apns.send(
                {
                    "send_mode": ApnsSenderType.VOIP,
                    "device_token": "token-1",
                    "notification": {"data": "body", "title": "Title", "ttl": 30},
                }
            ) == "voip"
            assert apns.send(
                {
                    "send_mode": ApnsSenderType.BACKGROUND,
                    "device_token": "token-1",
                    "notification": {"data": "body", "title": "Title", "ttl": 30},
                }
            ) == "background"
            assert apns.send(
                {
                    "send_mode": ApnsSenderType.MUTABLE,
                    "device_token": "token-1",
                    "notification": {"data": "body", "title": "Title", "ttl": 30},
                }
            ) == "alert"
            assert apns.send(
                {
                    "send_mode": ApnsSenderType.IMMUTABLE,
                    "device_token": "token-1",
                    "notification": {
                        "data": "body",
                        "message_body": "immutable-body",
                        "title": "Title",
                        "ttl": 30,
                    },
                }
            ) == "immutable"
            assert apns.send(
                {
                    "send_mode": ApnsSenderType.VOIP,
                    "device_tokens": ["token-1"],
                    "notification": {"data": "body", "title": "Title", "ttl": 30},
                    "force_exit_on": [200],
                }
            ) == "voip-list"
            assert apns.send(
                {
                    "send_mode": ApnsSenderType.BACKGROUND,
                    "device_tokens": ["token-1"],
                    "notification": {"data": "body", "title": "Title", "ttl": 30},
                    "force_exit_on": [200],
                }
            ) == "background-list"
            assert apns.send(
                {
                    "send_mode": ApnsSenderType.MUTABLE,
                    "device_tokens": ["token-1"],
                    "notification": {"data": "body", "title": "Title", "ttl": 30},
                    "force_exit_on": [200],
                }
            ) == "alert-list"
            assert apns.send(
                {
                    "send_mode": ApnsSenderType.IMMUTABLE,
                    "device_tokens": ["token-1"],
                    "notification": {
                        "data": "body",
                        "message_body": "immutable-body",
                        "title": "Title",
                        "ttl": 30,
                    },
                    "force_exit_on": [200],
                }
            ) == "alert-list"

        assert voip_mock.call_count == 1
        assert background_mock.call_count == 1
        assert alert_mock.call_count == 2
        assert voip_list_mock.call_count == 1
        assert background_list_mock.call_count == 1
        assert alert_list_mock.call_count == 2

        assert apns.send(
            {
                "send_mode": "invalid",
                "device_token": "token-1",
                "notification": {"data": "body", "title": "Title", "ttl": 30},
            }
        ) is None

        with pytest.raises(RuntimeError, match="Message must be provided."):
            ApnsNotification.calculate_payload_size(None)
        with pytest.raises(RuntimeError, match="send_mode must be provided."):
            ApnsNotification.calculate_payload_size({"device_token": "token-1", "notification": {}})
        with pytest.raises(RuntimeError, match=r"device token\(s\) must be provided."):
            ApnsNotification.calculate_payload_size({"send_mode": ApnsSenderType.VOIP, "notification": {}})
        with pytest.raises(RuntimeError, match="Device tokens list size exceeds maximum of 2."):
            ApnsNotification.calculate_payload_size(
                {
                    "send_mode": ApnsSenderType.VOIP,
                    "device_tokens": ["a", "b", "c"],
                    "notification": {"data": "body", "title": "Title"},
                },
                max_list_size=2,
            )
        with pytest.raises(RuntimeError, match="Unsupported send_mode provided."):
            ApnsNotification.calculate_payload_size(
                {"send_mode": "invalid", "device_token": "token-1", "notification": {}}
            )

        voip_size = ApnsNotification.calculate_payload_size(
            {
                "send_mode": ApnsSenderType.VOIP,
                "device_token": "token-1",
                "notification": {"data": "body", "title": "Title"},
            }
        )
        assert voip_size["target_count"] == 1
        assert voip_size["payload_size_bytes"] > 0

        background_size = ApnsNotification.calculate_payload_size(
            {
                "send_mode": ApnsSenderType.BACKGROUND,
                "device_tokens": ["a", "b"],
                "notification": {"data": "body", "title": "Title"},
            }
        )
        assert background_size["target_count"] == 2
        assert background_size["total_payload_size_bytes"] == background_size["payload_size_bytes"] * 2

        mutable_size = ApnsNotification.calculate_payload_size(
            {
                "send_mode": ApnsSenderType.MUTABLE,
                "device_token": "token-1",
                "notification": {"data": "body", "title": "Title"},
            }
        )
        immutable_size = ApnsNotification.calculate_payload_size(
            {
                "send_mode": ApnsSenderType.IMMUTABLE,
                "device_token": "token-1",
                "notification": {
                    "data": "body",
                    "message_body": "immutable-body",
                    "title": "Title",
                },
            }
        )
        assert mutable_size["send_mode"] == ApnsSenderType.MUTABLE
        assert immutable_size["send_mode"] == ApnsSenderType.IMMUTABLE

        large_size = ApnsNotification.calculate_payload_size(
            {
                "send_mode": ApnsSenderType.MUTABLE,
                "device_token": "token-1",
                "notification": {"data": "x" * 5000, "title": "Large"},
            }
        )
        assert large_size["overflow_bytes"] == large_size["payload_size_bytes"] - 4096
        assert large_size["is_within_limit"] is False

