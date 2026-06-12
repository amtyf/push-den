import json
from firebase_admin.messaging import SendResponse
from jsonschema import validate
import firebase_admin
from firebase_admin import messaging
from firebase_admin.credentials import Certificate
from typing import Optional
from ...enums.fcm import FcmSenderType
from ...schema.schema import Schema
from ...notification import Notification


class FcmNotification(Notification):
    def __init__(self, certificate_name: Optional[str] = None):

        if certificate_name is None:
            raise Exception("Certificate name must be provided.")

        self.cert = Certificate(certificate_name)
        self.default_app = firebase_admin.initialize_app(credential=self.cert)
        self.MAX_TTL = 2419200

    def validate_data(self, device_tokens=None, notification=None):
        if device_tokens is None:
            device_tokens = []
        if len(device_tokens) == 0 or device_tokens[0] is None:
            raise Exception("Must provide a device token.")

        if notification is None:
            raise Exception("Notification data must be provided.")

        if notification.get("data"):
            validate(instance=notification.get("data"), schema=Schema.DATA_SCHEMA)

        validate(instance=notification, schema=Schema.FCM_NOTIFICATION_SCHEMA)

    def notify_single_device(self, device_token=None, notification=None):

        self.validate_data([device_token], notification)
        message = messaging.Message(
            token=device_token,
            data=notification.get("data") or {},
            notification=messaging.Notification(
                title=notification.get("message_title"),
                body=notification.get("message_body"),
            ),
            android=messaging.AndroidConfig(
                notification=messaging.AndroidNotification(
                    title=notification.get("message_title"),
                    body=notification.get("message_body"),
                ),
                priority=notification.get("priority") or "normal",
                ttl=notification.get("ttl") or self.MAX_TTL,
                fcm_options=messaging.AndroidFCMOptions(
                    analytics_label=notification.get("analytics_label")
                ),
            ),
        )

        try:
            response = messaging.send(message)
            return SendResponse({"name": response}, None)
        except Exception as e:
            return SendResponse(None, str(e))

    def notify_multiple_devices(self, device_tokens=None, notification=None):

        if device_tokens is None:
            device_tokens = []
        self.validate_data(device_tokens, notification)

        message = messaging.MulticastMessage(
            tokens=device_tokens,
            data=notification.get("data") or {},
            notification=messaging.Notification(
                title=notification.get("message_title"),
                body=notification.get("message_body"),
            ),
            android=messaging.AndroidConfig(
                notification=messaging.AndroidNotification(
                    title=notification.get("message_title"),
                    body=notification.get("message_body"),
                ),
                priority=notification.get("priority") or "normal",
                ttl=notification.get("ttl") or self.MAX_TTL,
                fcm_options=messaging.AndroidFCMOptions(
                    analytics_label=notification.get("analytics_label")
                ),
            ),
        )
        return messaging.send_each_for_multicast(message)

    def single_device_data_message(self, device_token=None, notification=None):
        if device_token is None:
            raise Exception("Must provide a device token.")

        data = notification.get("data")
        if data is None:
            raise Exception("Data must be provided.")

        validate(instance=data, schema=Schema.DATA_SCHEMA)

        message = messaging.Message(
            data=data,
            token=device_token,
            android=messaging.AndroidConfig(
                priority=notification.get("priority") or "normal",
                ttl=notification.get("ttl") or self.MAX_TTL,
                fcm_options=messaging.AndroidFCMOptions(
                    analytics_label=notification.get("analytics_label")
                ),
            ),
        )
        try:
            response = messaging.send(message)
            return SendResponse({"name": response}, None)
        except Exception as e:
            return SendResponse(None, str(e))

    def multiple_devices_data_message(
        self, device_tokens=None, notification=None
    ):
        if device_tokens is None:
            device_tokens = []
        if len(device_tokens) == 0:
            raise Exception("Must provide device tokens.")

        data = notification.get("data")
        if data is None:
            raise Exception("Data must be provided.")

        validate(instance=data, schema=Schema.DATA_SCHEMA)

        message = messaging.MulticastMessage(
            data=data,
            tokens=device_tokens,
            android=messaging.AndroidConfig(
                priority=notification.get("priority") or "normal",
                ttl=notification.get("ttl") or self.MAX_TTL,
                fcm_options=messaging.AndroidFCMOptions(
                    analytics_label=notification.get("analytics_label")
                ),
            ),
        )
        response = messaging.send_each_for_multicast(message)
        return response

    def send(self, payload=None):
        if payload is None:
            raise Exception("Message must be provided.")

        send_mode = payload.get("send_mode")
        device_token = payload.get("device_token")
        device_tokens = payload.get("device_tokens")
        notification = payload.get("notification")


        if send_mode is None:
            raise Exception("send_mode must be provided.")

        if send_mode == FcmSenderType.SINGLE:
            return self.notify_single_device(device_token, notification)
        elif send_mode == FcmSenderType.MULTIPLE:
            return self.notify_multiple_devices(device_tokens, notification)
        elif send_mode == FcmSenderType.SINGLE_DATA:
            return self.single_device_data_message(device_token, notification)
        elif send_mode == FcmSenderType.MULTIPLE_DATA:
            return self.multiple_devices_data_message(device_tokens, notification)
        else:
            raise Exception("Invalid FcmSenderType.")

    @staticmethod
    def _build_payload_for_size(send_mode, notification):
        if notification is None:
            raise Exception("Notification data must be provided.")

        if send_mode in [FcmSenderType.SINGLE, FcmSenderType.MULTIPLE]:
            if notification.get("data"):
                validate(instance=notification.get("data"), schema=Schema.DATA_SCHEMA)
            validate(instance=notification, schema=Schema.FCM_NOTIFICATION_SCHEMA)

            payload_data = {
                "notification": {
                    "title": notification.get("message_title"),
                    "body": notification.get("message_body"),
                }
            }
            if notification.get("data") is not None:
                payload_data["data"] = notification.get("data")
        elif send_mode in [FcmSenderType.SINGLE_DATA, FcmSenderType.MULTIPLE_DATA]:
            data = notification.get("data")
            if data is None:
                raise Exception("Data must be provided.")
            validate(instance=data, schema=Schema.DATA_SCHEMA)
            payload_data = {"data": data}
        else:
            raise Exception("Invalid FcmSenderType.")

        return json.dumps(
            payload_data, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    @staticmethod
    def calculate_payload_size(payload=None):
        """Return FCM JSON payload size details without sending any request."""
        max_payload_size_bytes = 4096

        if payload is None:
            raise Exception("Message must be provided.")

        send_mode = payload.get("send_mode")
        device_token = payload.get("device_token")
        device_tokens = payload.get("device_tokens")
        notification = payload.get("notification")

        if send_mode is None:
            raise Exception("send_mode must be provided.")

        if send_mode in [FcmSenderType.SINGLE, FcmSenderType.SINGLE_DATA]:
            if device_token is None:
                raise Exception("Must provide a device token.")
            target_count = 1
        elif send_mode in [FcmSenderType.MULTIPLE, FcmSenderType.MULTIPLE_DATA]:
            if device_tokens is None or len(device_tokens) == 0:
                raise Exception("Must provide device tokens.")
            target_count = len(device_tokens)
        else:
            raise Exception("Invalid FcmSenderType.")

        payload_bytes = FcmNotification._build_payload_for_size(send_mode, notification)
        payload_size_bytes = len(payload_bytes)

        return {
            "send_mode": send_mode,
            "fcm_max_payload_size_bytes": max_payload_size_bytes,
            "payload_size_bytes": payload_size_bytes,
            "total_payload_size_bytes": payload_size_bytes * target_count,
            "target_count": target_count,
            "is_within_limit": payload_size_bytes <= max_payload_size_bytes,
            "overflow_bytes": max(0, payload_size_bytes - max_payload_size_bytes),
        }
