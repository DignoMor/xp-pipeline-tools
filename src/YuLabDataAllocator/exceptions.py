"""Exception types for the YuLabDataAllocator library and CLI."""


class YuLabDataAllocatorError(Exception):
    """Base exception for YuLabDataAllocator errors."""

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class ConfigError(YuLabDataAllocatorError):
    """Base for config path / schema / drive-path errors."""


class YuhomeUnsetError(ConfigError):
    """Raised when ``YUHOME`` is missing or empty when resolving the config path."""


class ConfigFileError(ConfigError):
    """Raised when the config file is missing or unreadable."""


class InvalidConfigError(ConfigError):
    """Raised when config JSON is invalid, not an object, or ``drives`` is bad."""


class DrivePathError(ConfigError):
    """Raised when a drive path is not absolute or does not exist."""
