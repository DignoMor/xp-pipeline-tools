"""SQLite location DB open/create for YuLabDataAllocator."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_CREATE_DATA_LOCATION = """
CREATE TABLE IF NOT EXISTS data_location (
    branch_path TEXT PRIMARY KEY,
    drive_name TEXT
)
"""


class StorageManager:
    """Open (or create) the location DB and ensure ``data_location`` exists."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute(_CREATE_DATA_LOCATION)
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()
