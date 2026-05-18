class NotificationFactory(object):
    """Client factory for Notifications"""

    def __init__(self):
        self._creators = {}
        self._default = None

    def register(self, name, factory, default=False):
        self._creators[name] = factory
        if default or self._default is None:
            self._default = self._creators[name]

    def get_api(self, name=None):
        if name is None:
            return self._default
        if name not in self._creators:
            raise NameError(f"Unsupported factory: {name}")
        return self._creators[name]

    def get_api_list(self, names=None):
        apis = []
        if names is None:
            apis.append(self._default)
            return apis
        for name in names:
            if name not in self._creators:
                raise NameError(f"Unsupported factory: {name}")
            apis.append(self._creators[name])
        return apis
