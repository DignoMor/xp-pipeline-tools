"""Config JSON load and drive-path validation for YuLabDataAllocator."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .exceptions import ConfigFileError, DrivePathError, InvalidConfigError


class ConfigHandler:
    """Load and validate a YuLabDataAllocator config JSON file."""

    def __init__(self, config_path: Path | str) -> None:
        self.config_path = Path(config_path)
        self._drives: dict[str, str] = {}
        self.load_config(self.config_path)

    def load_config(self, config_path: Path | str) -> dict[str, str]:
        """Read, parse, and validate ``config_path``; store drive map.

        Returns the validated ``drives`` map.
        """
        path = Path(config_path)
        self.config_path = path
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ConfigFileError(f"Config file not found: {path}") from exc
        except OSError as exc:
            raise ConfigFileError(
                f"Config file unreadable: {path}: {exc}"
            ) from exc

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InvalidConfigError(
                f"Config file is not valid JSON: {path}: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise InvalidConfigError(
                f"Config file must contain a JSON object: {path}"
            )

        drives = self._validate_drives_object(data)
        self._drives = drives
        self.validate_paths()
        return self.get_drive_paths()

    def reload_config(self) -> dict[str, str]:
        """Re-read and re-validate the current ``config_path``."""
        return self.load_config(self.config_path)

    def get_drive_paths(self) -> dict[str, str]:
        """Return a copy of the loaded ``drives`` map (name → absolute path)."""
        return dict(self._drives)

    def validate_paths(self) -> None:
        """Ensure every drive path is absolute and exists.

        Raises ``DrivePathError`` on the first failing drive.
        """
        for name, drive_path in self._drives.items():
            if not os.path.isabs(drive_path):
                raise DrivePathError(
                    f"Drive {name!r} path is not absolute: {drive_path}"
                )
            if not os.path.exists(drive_path):
                raise DrivePathError(
                    f"Drive {name!r} path does not exist: {drive_path}"
                )

    @staticmethod
    def _validate_drives_object(data: dict[str, Any]) -> dict[str, str]:
        if "drives" not in data:
            raise InvalidConfigError("Missing required top-level key: drives")

        drives = data["drives"]
        if not isinstance(drives, dict):
            raise InvalidConfigError("'drives' must be an object")
        if not drives:
            raise InvalidConfigError(
                "'drives' must contain at least one drive"
            )

        validated: dict[str, str] = {}
        for name, value in drives.items():
            if not isinstance(name, str) or not name:
                raise InvalidConfigError(
                    f"Invalid drive name {name!r}: must be a non-empty string"
                )
            if not isinstance(value, str):
                raise InvalidConfigError(
                    f"drives[{name!r}] must be a string path"
                )
            validated[name] = value
        return validated
