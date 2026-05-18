# push-den

A wrapper library for sending push notifications through Firebase Cloud Messaging (FCM) and Apple Push Notification service (APNs).

## Requirements

- Python 3.8+

## Installation

```bash
pip install push-den
```

For local build/install:

```bash
python -m build
pip install dist/push_den-<version>-py3-none-any.whl
```

## Configuration

Create a `.env` file from `.env.example` and set the required values.

Minimal runtime configuration in code:

```python
import os
from push_den.processor import NotificationProcessor

fcm_credential_path = os.getenv("FIREBASE_ADMIN_PRIVATE_KEY")

apns = {
    "APNS_AUTH_KEY": os.getenv("APNS_AUTH_KEY"),
    "TEAM_ID": os.getenv("TEAM_ID"),
    "ALGORITHM": os.getenv("ALGORITHM", "ES256"),
    "APNS_KEY_ID": os.getenv("APNS_KEY_ID"),
    "BUNDLE_ID": os.getenv("BUNDLE_ID"),
    "IOS_HTTP_URL": os.getenv("IOS_HTTP_URL", "api.push.apple.com:443"),
    "IOS_HTTP_SANDBOX_URL": os.getenv("IOS_HTTP_SANDBOX_URL"),
}

notification_processor = NotificationProcessor(fcm=fcm_credential_path, apns=apns)
```

## Usage

### FCM single notification (`single`)

```python
payload = {
    "type": "fcm",
    "send_mode": "single",
    "device_token": "<fcm-device-token>",
    "notification": {
        "message_title": "Hello",
        "message_body": "Welcome",
        "priority": "high",
        "ttl": 60,
    },
}

response = notification_processor.process_message(payload)
print(response.message_id, response.success, response.exception)
```

### FCM multicast data message (`multiple_data`)

```python
payload = {
    "type": "fcm",
    "send_mode": "multiple_data",
    "device_tokens": ["<token-1>", "<token-2>"],
    "notification": {
        "data": {
            "event": "order.created",
            "order_id": "1001",
        },
        "priority": "normal",
        "ttl": 120,
    },
}

response = notification_processor.process_message(payload)
print(response.success_count, response.failure_count)
```

### APNs mutable alert (`alert`)

```python
payload = {
    "type": "apns",
    "send_mode": "alert",
    "device_token": "<apns-device-token>",
    "notification": {
        "title": "New Message",
        "data": "You have a new notification",
        "ttl": 3600,
    },
}

response = notification_processor.process_message(payload)
print(response.status, response.read().decode("utf-8"))
```

### APNs immutable alert (`immutable_alert`)

```python
payload = {
    "type": "apns",
    "send_mode": "immutable_alert",
    "device_tokens": ["<token-1>", "<token-2>"],
    "notification": {
        "title": "Account Notice",
        "message_body": "Your profile has been updated.",
        "ttl": 3600,
    },
}

response = notification_processor.process_message(payload)
print(response)
```

## Payload size helpers

You can estimate payload size before sending:

```python
from push_den.notificationfactory.fcm_factory.fcm_notification import FcmNotification
from push_den.notificationfactory.apns_factory.apns_notification import ApnsNotification

fcm_size = FcmNotification.calculate_payload_size(payload)
apns_size = ApnsNotification.calculate_payload_size(payload)

print(fcm_size)
print(apns_size)
```
