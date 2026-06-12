from push_den.notification import Notification


class TestNotifier(Notification):
    """Test Notifier"""

    __test__ = False

    def __init__(self):
        self._client = "Testing factory..."

    def send(self, msg_payload):
        message = msg_payload

        print(f"{self._client}\n{message}")
