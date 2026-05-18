class ApnsSenderType(object):
    VOIP = "voip"
    BACKGROUND = "background"
    MUTABLE = "alert"
    IMMUTABLE = "immutable_alert"

    __all__ = [VOIP, BACKGROUND, MUTABLE, IMMUTABLE]
