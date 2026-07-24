"""Allocate / resolve / delete abstract branches across configured drives."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .config_handler import ConfigHandler
from .exceptions import (
    BranchNotFoundError,
    DuplicateBranchError,
    PathNotFoundError,
    PathOutsideDrivesError,
    StaleDriveError,
)
from .storage_manager import StorageManager


class Allocator:
    """Choose drives by free space and map abstract branches to filesystem paths."""

    def __init__(
        self, config_path: Path | str, db_path: Path | str
    ) -> None:
        self.config_handler = ConfigHandler(config_path)
        self.storage_manager = StorageManager(db_path)

    def check_space(self) -> dict[str, int]:
        """Return free bytes per configured drive name via ``shutil.disk_usage``."""
        free: dict[str, int] = {}
        for name, path in self.config_handler.get_drive_paths().items():
            free[name] = shutil.disk_usage(path).free
        return free

    def allocate(self, branch_name: str) -> str:
        """Create ``branch_name`` on the drive with the most free space.

        Tie-break: ``max`` on ``check_space`` keys in drives-map insertion order.
        Returns the absolute target path.
        """
        if self.storage_manager.check_duplicates(branch_name):
            raise DuplicateBranchError(
                f"Branch already allocated: {branch_name}"
            )

        space = self.check_space()
        drive = max(space, key=space.get)
        drive_paths = self.config_handler.get_drive_paths()
        target_path = os.path.join(drive_paths[drive], branch_name)
        self.make_directory(target_path)
        self.storage_manager.record_location(branch_name, drive)
        return target_path

    def get_path(self, branch_name: str) -> str:
        """Resolve the absolute filesystem path for ``branch_name``."""
        drive = self.storage_manager.get_drive(branch_name)
        if drive is None:
            raise BranchNotFoundError(f"Branch not found: {branch_name}")

        drive_paths = self.config_handler.get_drive_paths()
        if drive not in drive_paths:
            raise StaleDriveError(
                f"Drive {drive!r} for branch {branch_name!r} "
                f"is not in the loaded config"
            )
        return os.path.join(drive_paths[drive], branch_name)

    def delete_branch(self, branch_name: str) -> None:
        """Remove the on-disk tree and the DB row for ``branch_name``."""
        path = self.get_path(branch_name)
        self.remove_directory(path)
        self.storage_manager.delete_location(branch_name)

    def make_directory(self, path: str) -> None:
        """Create directory tree ``path`` if it lies under a configured drive."""
        if not self._path_under_drives(path):
            raise PathOutsideDrivesError(
                f"Path is outside configured drives: {path}"
            )
        os.makedirs(path, exist_ok=True)

    def remove_directory(self, path: str) -> None:
        """Remove directory tree ``path`` if it lies under a configured drive."""
        if not self._path_under_drives(path):
            raise PathOutsideDrivesError(
                f"Path is outside configured drives: {path}"
            )
        if not os.path.exists(path):
            raise PathNotFoundError(f"Path not found: {path}")
        shutil.rmtree(path)

    def _path_under_drives(self, path: str) -> bool:
        drive_paths = self.config_handler.get_drive_paths().values()
        return any(path.startswith(drive) for drive in drive_paths)
