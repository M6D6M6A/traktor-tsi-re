class TsiError(Exception):
    """Base exception for TSI parsing errors."""


class XmlEntryNotFound(TsiError):
    """DeviceIO.Config.Controller not found in TSI XML."""


class FrameError(TsiError):
    """Invalid or malformed frame encountered."""
