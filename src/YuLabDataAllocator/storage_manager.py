"""SQLite location DB open/create and CRUD for YuLabDataAllocator."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .exceptions import DuplicateBranchError, LocationNotFoundError

_CREATE_DATA_LOCATION = """
CREATE TABLE IF NOT EXISTS data_location (
    branch_path TEXT PRIMARY KEY,
    drive_name TEXT
)
"""


class StorageManager:
    """Open (or create) the location DB and manage ``data_location`` rows."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute(_CREATE_DATA_LOCATION)
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def record_location(self, branch_path: str, drive_name: str) -> None:
        """INSERT a branch → drive mapping.

        Raises ``DuplicateBranchError`` if ``branch_path`` already exists.
        """
        try:
            self._conn.execute(
                "INSERT INTO data_location (branch_path, drive_name) "
                "VALUES (?, ?)",
                (branch_path, drive_name),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateBranchError(
                f"Branch already recorded: {branch_path}"
            ) from exc

    def get_drive(self, branch_path: str) -> str | None:
        """Return the drive name for ``branch_path``, or ``None`` if missing."""
        row = self._conn.execute(
            "SELECT drive_name FROM data_location WHERE branch_path = ?",
            (branch_path,),
        ).fetchone()
        return row[0] if row else None

    def check_duplicates(self, branch_path: str) -> bool:
        """Return ``True`` if ``branch_path`` already has a DB row."""
        return self.get_drive(branch_path) is not None

    def delete_location(self, branch_path: str) -> None:
        """DELETE the row for ``branch_path``.

        Raises ``LocationNotFoundError`` if no matching row existed.
        """
        cur = self._conn.execute(
            "DELETE FROM data_location WHERE branch_path = ?",
            (branch_path,),
        )
        self._conn.commit()
        if cur.rowcount == 0:
            raise LocationNotFoundError(
                f"No location recorded for branch: {branch_path}"
            )

    def get_all_locations2drive(self) -> dict[str, str]:
        """Return all ``branch_path → drive_name`` mappings."""
        rows = self._conn.execute(
            "SELECT branch_path, drive_name FROM data_location"
        ).fetchall()
        return {branch_path: drive_name for branch_path, drive_name in rows}
