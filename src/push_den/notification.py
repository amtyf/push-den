class Notification:
    def notify_single_device(self, *args, **kwargs):
        raise NotImplementedError("Should be implemented in a subclass")

    def notify_multiple_devices(self, *args, **kwargs):
        raise NotImplementedError("Should be implemented in a subclass")

    def send(self, *args, **kwargs):
        raise NotImplementedError("Should be implemented in a subclass")
