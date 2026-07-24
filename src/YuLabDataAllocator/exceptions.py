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


class AllocatorError(YuLabDataAllocatorError):
    """Domain base for allocate / location / tree errors."""


class DuplicateBranchError(AllocatorError):
    """Raised when ``allocate`` / ``record_location`` hits a duplicate branch."""


class BranchNotFoundError(AllocatorError):
    """Raised when ``get_path`` / ``delete_branch`` cannot find a branch."""


class StaleDriveError(AllocatorError):
    """Raised when a DB ``drive_name`` is not in the loaded config."""


class PathOutsideDrivesError(AllocatorError):
    """Raised when mkdir/rmtree targets a path outside configured drive roots."""


class PathNotFoundError(AllocatorError):
    """Raised when ``remove_directory`` targets a path missing on disk."""


class LocationNotFoundError(AllocatorError):
    """Raised when ``delete_location`` finds no DB row for the branch."""


class TreeError(AllocatorError):
    """Raised for invalid tree structure (e.g. ``tree2str`` multiple roots)."""
