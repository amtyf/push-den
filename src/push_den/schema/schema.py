class Schema:
    FCM_NOTIFICATION_SCHEMA = {
        "type": "object",
        "properties": {
            "message_title": {"type": "string"},
            "message_body": {"type": "string"},
        },
        "additionalProperties": True,
    }

    DATA_SCHEMA = {
        "type": "object",
        "properties": {
            "priority": {"enum": ["normal", "high"]},
            "ttl": {"type": "number"},
        },
        "additionalProperties": True,
    }

    APNS_NOTIFICATION_SCHEMA = {
        "type": "object",
        "properties": {
            "message_title": {"type": "string"},
            "message_body": {"type": "string"},
            "timeout": {"type": "number"},
            "priority": {"enum": ["normal", "high"]},
            "ttl": {"type": "number"},
            "data": {"type": "object"},
        },
        "additionalProperties": True,
    }
