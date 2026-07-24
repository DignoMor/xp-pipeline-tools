"""StorageManager location CRUD (SPEC007 slice).

Encodes record_location / get_drive / check_duplicates / delete_location /
get_all_locations2drive. DB create-on-open schema is SPEC005
(test_yulab_storage_db.py). Allocator / TreeVisualizer are out of scope here.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _storage_manager_cls():
    pkg = importlib.import_module("YuLabDataAllocator")
    assert hasattr(pkg, "StorageManager")
    return pkg.StorageManager


def _exc(name: str):
    pkg = importlib.import_module("YuLabDataAllocator")
    assert hasattr(pkg, name), f"expected YuLabDataAllocator.{name}"
    return getattr(pkg, name)


def _sm(tmp_path: Path):
    return _storage_manager_cls()(tmp_path / "loc.db")


# --- record / get / check ---


def test_record_location_and_get_drive(tmp_path: Path) -> None:
    """record_location stores branch→drive; get_drive returns the drive name."""
    sm = _sm(tmp_path)
    sm.record_location("proj/a", "drive1")
    assert sm.get_drive("proj/a") == "drive1"


def test_get_drive_returns_none_when_missing(tmp_path: Path) -> None:
    """get_drive returns None when the branch has no DB row."""
    sm = _sm(tmp_path)
    assert sm.get_drive("missing/branch") is None


def test_check_duplicates_false_then_true(tmp_path: Path) -> None:
    """check_duplicates is False before insert and True after."""
    sm = _sm(tmp_path)
    assert sm.check_duplicates("proj/a") is False
    sm.record_location("proj/a", "drive1")
    assert sm.check_duplicates("proj/a") is True


def test_record_location_duplicate_raises_duplicate_branch_error(tmp_path: Path) -> None:
    """Second record_location for the same branch raises DuplicateBranchError."""
    sm = _sm(tmp_path)
    DuplicateBranchError = _exc("DuplicateBranchError")
    sm.record_location("proj/a", "drive1")
    with pytest.raises(DuplicateBranchError):
        sm.record_location("proj/a", "drive2")
    # Original mapping is preserved
    assert sm.get_drive("proj/a") == "drive1"


def test_duplicate_branch_error_is_allocator_error(tmp_path: Path) -> None:
    """DuplicateBranchError from record_location is catchable as AllocatorError."""
    sm = _sm(tmp_path)
    AllocatorError = _exc("AllocatorError")
    sm.record_location("x", "d1")
    with pytest.raises(AllocatorError):
        sm.record_location("x", "d2")


# --- delete_location ---


def test_delete_location_removes_row(tmp_path: Path) -> None:
    """delete_location removes the DB row so get_drive returns None."""
    sm = _sm(tmp_path)
    sm.record_location("proj/a", "drive1")
    sm.delete_location("proj/a")
    assert sm.get_drive("proj/a") is None
    assert sm.check_duplicates("proj/a") is False


def test_delete_location_missing_raises_location_not_found_error(tmp_path: Path) -> None:
    """delete_location with no matching row raises LocationNotFoundError."""
    sm = _sm(tmp_path)
    LocationNotFoundError = _exc("LocationNotFoundError")
    with pytest.raises(LocationNotFoundError):
        sm.delete_location("no/such/branch")


def test_location_not_found_error_is_allocator_error(tmp_path: Path) -> None:
    """LocationNotFoundError is catchable as AllocatorError."""
    sm = _sm(tmp_path)
    AllocatorError = _exc("AllocatorError")
    with pytest.raises(AllocatorError):
        sm.delete_location("gone")


# --- get_all_locations2drive ---


def test_get_all_locations2drive_empty(tmp_path: Path) -> None:
    """get_all_locations2drive returns {} when the DB has no rows."""
    sm = _sm(tmp_path)
    assert sm.get_all_locations2drive() == {}


def test_get_all_locations2drive_maps_all_branches(tmp_path: Path) -> None:
    """get_all_locations2drive returns all branch_path → drive mappings (legacy name)."""
    sm = _sm(tmp_path)
    sm.record_location("a/b", "drive1")
    sm.record_location("c", "drive2")
    mapping = sm.get_all_locations2drive()
    assert mapping == {"a/b": "drive1", "c": "drive2"}


def test_get_all_locations2drive_reflects_delete(tmp_path: Path) -> None:
    """Deleted branches no longer appear in get_all_locations2drive."""
    sm = _sm(tmp_path)
    sm.record_location("keep", "drive1")
    sm.record_location("drop", "drive1")
    sm.delete_location("drop")
    assert sm.get_all_locations2drive() == {"keep": "drive1"}
