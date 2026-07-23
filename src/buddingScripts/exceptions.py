"""Exception types for the buddingScripts library and CLI."""


class BuddingScriptsError(Exception):
    """Base exception for buddingScripts errors."""


class CLIInputError(BuddingScriptsError):
    """Raised when CLI input is invalid."""

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return "CLI input Error: " + self.message
