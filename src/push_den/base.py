from jsonschema import validate
import firebase_admin
from firebase_admin import messaging
from firebase_admin.credentials import Certificate
from .schema import Schema


class BaseAPI:
    def __init__(self, certificate_name: str = None):

        if certificate_name is None:
            raise Exception("Certificate name must be provided.")

        self.cert = Certificate(certificate_name)
        self.default_app = firebase_admin.initialize_app(credential=self.cert)
        self.MAX_TTL = 2419200

    def notify_single_device(self, device_token=None, notification=None):
        if device_token is None:
            raise Exception("Must provide a device token.")

        if notification is None:
            raise Exception("Notification data must be provided.")

        validate(instance=notification, schema=Schema.FCM_NOTIFICATION_SCHEMA)

        message = messaging.Message(
            token=device_token,
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
            ),
        )

        response = messaging.send(message)

        return response

    def notify_multiple_devices(self, device_tokens: list = [], notification=None):
        if len(device_tokens) == 0:
            raise Exception("Must provide device tokens.")

        if notification is None:
            raise Exception("Notification data must be provided.")

        validate(instance=notification, schema=Schema.FCM_NOTIFICATION_SCHEMA)

        message = messaging.MulticastMessage(
            tokens=device_tokens,
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
            ),
        )
        response = messaging.send_multicast(message)
        return response

    def single_device_data_message(self, device_token=None, data=None):
        if device_token is None:
            raise Exception("Must provide a device token.")

        if data is None:
            raise Exception("Data must be provided.")

        validate(instance=data, schema=Schema.DATA_SCHEMA)

        message = messaging.Message(
            data=data,
            token=device_token,
            android=messaging.AndroidConfig(
                priority=data.get("priority") or "normal",
                ttl=data.get("ttl") or self.MAX_TTL,
            ),
        )
        response = messaging.send(message)
        return response

    def multiple_devices_data_message(self, device_tokens: list = [], data=None):
        if len(device_tokens) == 0:
            raise Exception("Must provide device tokens.")

        if data is None:
            raise Exception("Data must be provided.")

        validate(instance=data, schema=Schema.DATA_SCHEMA)

        message = messaging.MulticastMessage(
            data=data,
            tokens=device_tokens,
            android=messaging.AndroidConfig(
                priority=data.get("priority") or "normal",
                ttl=data.get("ttl") or self.MAX_TTL,
            ),
        )
        response = messaging.send_multicast(message)
        return response
