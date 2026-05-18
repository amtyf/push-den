from ..notificationfactory.notification_factory import NotificationFactory

from ..notificationfactory.fcm_factory.fcm_notification import FcmNotification
from ..notificationfactory.apns_factory.apns_notification import ApnsNotification
from ..notificationfactory.custom_factory.test_notifier import TestNotifier


class NotificationProcessor:
    def register_factories(self):
        """
        Register Notification factories here.
        """
        self.factory.register("custom", TestNotifier(), default=True)
        if self.fcm:
            self.factory.register("fcm", FcmNotification(self.fcm))
        if self.apns:
            self.factory.register("apns", ApnsNotification(self.apns))

    def __init__(self, fcm=None, apns=None):
        self.fcm = fcm
        self.apns = apns
        self.factory = NotificationFactory()
        self.register_factories()

    def process_message(self, message):
        sender = message.get("type")
        senders = self.factory.get_api_list([sender])

        if senders is not None:
            for sender in senders:
                return sender.send(message)
