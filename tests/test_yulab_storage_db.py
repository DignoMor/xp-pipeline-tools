"""SQLite location DB create-on-open (SPEC005 slice).

Encodes default-path open via StorageManager, parent-dir creation, and
data_location schema (branch_path PK, drive_name). Allocate/get/delete and
Allocator are out of scope (SPEC007).
"""

from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest


def _storage_manager_cls():
    """StorageManager must be importable without going through the CLI."""
    pkg = importlib.import_module("YuLabDataAllocator")
    assert hasattr(pkg, "StorageManager"), (
        "expected YuLabDataAllocator.StorageManager to open/create the location DB"
    )
    return pkg.StorageManager


def _default_db_path():
    pkg = importlib.import_module("YuLabDataAllocator")
    assert hasattr(pkg, "default_db_path")
    return pkg.default_db_path


def _table_info(db_path: Path) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute("PRAGMA table_info(data_location)").fetchall()


def _table_sql(db_path: Path) -> str:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='data_location'"
        ).fetchone()
    assert row is not None, "expected data_location table"
    return row[0]


def test_storage_manager_creates_db_and_data_location_on_open(tmp_path: Path) -> None:
    """Opening StorageManager creates the DB file and data_location table."""
    StorageManager = _storage_manager_cls()
    db_path = tmp_path / "YuLabDataAllocator.db"
    assert not db_path.exists()
    StorageManager(db_path)
    assert db_path.is_file()
    info = _table_info(db_path)
    colnames = {row[1] for row in info}
    assert "branch_path" in colnames
    assert "drive_name" in colnames


def test_storage_manager_creates_parent_directory_if_missing(tmp_path: Path) -> None:
    """Parent directory is created if missing when the DB is first opened."""
    StorageManager = _storage_manager_cls()
    parent = tmp_path / ".YuLabDataAllocator"
    db_path = parent / "YuLabDataAllocator.db"
    assert not parent.exists()
    StorageManager(db_path)
    assert parent.is_dir()
    assert db_path.is_file()


def test_data_location_branch_path_is_primary_key(tmp_path: Path) -> None:
    """branch_path is the PRIMARY KEY (uniqueness of allocated branches)."""
    StorageManager = _storage_manager_cls()
    db_path = tmp_path / "loc.db"
    StorageManager(db_path)
    sql = _table_sql(db_path).upper()
    assert "BRANCH_PATH" in sql
    assert "PRIMARY KEY" in sql


def test_data_location_columns_are_text(tmp_path: Path) -> None:
    """data_location columns branch_path and drive_name are TEXT."""
    StorageManager = _storage_manager_cls()
    db_path = tmp_path / "loc.db"
    StorageManager(db_path)
    info = {row[1]: row[2].upper() for row in _table_info(db_path)}
    assert info["branch_path"] == "TEXT"
    assert info["drive_name"] == "TEXT"


def test_create_table_if_not_exists_is_idempotent(tmp_path: Path) -> None:
    """Re-opening an existing DB uses CREATE TABLE IF NOT EXISTS (no error)."""
    StorageManager = _storage_manager_cls()
    db_path = tmp_path / "loc.db"
    StorageManager(db_path)
    StorageManager(db_path)  # second open must succeed
    assert db_path.is_file()
    assert _table_info(db_path)


def test_storage_manager_opens_at_default_db_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """StorageManager can open the SPEC005 default DB path under $HOME."""
    StorageManager = _storage_manager_cls()
    monkeypatch.setenv("HOME", str(tmp_path))
    db_path = _default_db_path()()
    assert db_path == tmp_path / ".YuLabDataAllocator" / "YuLabDataAllocator.db"
    StorageManager(db_path)
    assert db_path.is_file()
    colnames = {row[1] for row in _table_info(db_path)}
    assert colnames >= {"branch_path", "drive_name"}


def test_branch_path_primary_key_rejects_duplicate_insert(tmp_path: Path) -> None:
    """PRIMARY KEY on branch_path enforces uniqueness at the SQLite layer."""
    StorageManager = _storage_manager_cls()
    db_path = tmp_path / "loc.db"
    StorageManager(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO data_location (branch_path, drive_name) VALUES (?, ?)",
            ("proj/a", "drive1"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO data_location (branch_path, drive_name) VALUES (?, ?)",
                ("proj/a", "drive2"),
            )
