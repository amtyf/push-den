# push-den

`push-den` is a Python wrapper library for sending push notifications through Firebase Cloud Messaging (FCM) and Apple Push Notification service (APNs).

[![Python](https://img.shields.io/badge/python-3.8%2B-blueviolet?logo=python&logoColor=white)](https://www.python.org)
[![Pre-Commit](https://img.shields.io/badge/pre--commit-enabled-blue?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Code Style: Black](https://img.shields.io/badge/code%20style-Black-000000.svg)](https://github.com/psf/black)
[![Tests](https://github.com/amtyf/push-den/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/amtyf/push-den/actions/workflows/tests.yml)
[![Codecov](https://codecov.io/gh/amtyf/push-den/graph/badge.svg)](https://codecov.io/gh/amtyf/push-den)
[![License: MIT](https://img.shields.io/badge/License-MIT-ff69b4.svg)](./LICENSE)
[![PyPI](https://img.shields.io/pypi/v/push-den?logo=pypi&logoColor=white)](https://pypi.org/project/push-den/)

Current version: `1.3.3`

Release history: [CHANGELOG.md](./CHANGELOG.md)

## PyPI Project Page

[https://pypi.org/project/push-den/](https://pypi.org/project/push-den/)

## Dependencies

- Python 3.8 or above

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


```python
from push_den.notificationfactory.fcm_factory.fcm_notification import FcmNotification
from push_den.notificationfactory.apns_factory.apns_notification import ApnsNotification

fcm_size = FcmNotification.calculate_payload_size(payload)
apns_size = ApnsNotification.calculate_payload_size(payload)

print(fcm_size)
print(apns_size)
```
