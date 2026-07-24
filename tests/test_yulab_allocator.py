"""Allocator allocate / get / delete / space / drive-prefix guards (SPEC007).

Encodes max-free-space selection, DB+disk join invariants, and PathOutside /
PathNotFound / StaleDrive / BranchNotFound / DuplicateBranch errors.
Config load and DB create-on-open are SPEC005; CLI is SPEC006 (out of scope).
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import NamedTuple

import pytest


def _pkg():
    return importlib.import_module("YuLabDataAllocator")


def _allocator_cls():
    pkg = _pkg()
    assert hasattr(pkg, "Allocator")
    return pkg.Allocator


def _exc(name: str):
    pkg = _pkg()
    assert hasattr(pkg, name), f"expected YuLabDataAllocator.{name}"
    return getattr(pkg, name)


def _write_config(path: Path, drives: dict[str, str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"drives": drives}), encoding="utf-8")
    return path


def _make_drives(tmp_path: Path, names: tuple[str, ...] = ("drive1", "drive2")) -> dict[str, str]:
    drives: dict[str, str] = {}
    for name in names:
        root = tmp_path / "drives" / name
        root.mkdir(parents=True, exist_ok=True)
        drives[name] = str(root.resolve())
    return drives


def _allocator(tmp_path: Path, drives: dict[str, str] | None = None):
    drives = drives if drives is not None else _make_drives(tmp_path)
    config_path = _write_config(tmp_path / "config.json", drives)
    db_path = tmp_path / "loc.db"
    return _allocator_cls()(config_path, db_path), drives


class _FakeUsage(NamedTuple):
    total: int
    used: int
    free: int


# --- construction / check_space ---


def test_allocator_constructs_from_config_and_db_paths(tmp_path: Path) -> None:
    """Allocator(config_path, db_path) builds ConfigHandler + StorageManager."""
    alloc, _ = _allocator(tmp_path)
    space = alloc.check_space()
    assert isinstance(space, dict)
    assert set(space) == {"drive1", "drive2"}
    assert all(isinstance(v, int) for v in space.values())


def test_check_space_uses_disk_usage_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """check_space returns free bytes per drive via shutil.disk_usage(...).free."""
    alloc, drives = _allocator(tmp_path)
    free_by_path = {
        drives["drive1"]: 100,
        drives["drive2"]: 500,
    }

    def fake_disk_usage(path: str | os.PathLike[str]) -> _FakeUsage:
        p = os.path.normpath(str(path))
        for configured, free in free_by_path.items():
            if p == os.path.normpath(configured):
                return _FakeUsage(total=free + 1, used=1, free=free)
        raise AssertionError(f"unexpected disk_usage path: {path!r}")

    import shutil

    monkeypatch.setattr(shutil, "disk_usage", fake_disk_usage)

    space = alloc.check_space()
    assert space["drive1"] == 100
    assert space["drive2"] == 500


# --- allocate ---


def test_allocate_chooses_drive_with_maximum_free_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """allocate selects the drive with max free bytes and returns join(drive, branch)."""
    alloc, drives = _allocator(tmp_path)
    free_map = {drives["drive1"]: 10, drives["drive2"]: 999}

    def fake_disk_usage(path: str | os.PathLike[str]) -> _FakeUsage:
        p = str(path)
        for configured, free in free_map.items():
            if p == configured or os.path.normpath(p) == os.path.normpath(configured):
                return _FakeUsage(total=free + 1, used=1, free=free)
        raise AssertionError(f"unexpected path: {path!r}")

    import shutil

    monkeypatch.setattr(shutil, "disk_usage", fake_disk_usage)

    target = alloc.allocate("proj/run1")
    expected = os.path.join(drives["drive2"], "proj/run1")
    assert target == expected
    assert Path(target).is_dir()
    assert alloc.get_path("proj/run1") == expected


def test_allocate_tie_break_follows_max_on_check_space_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Equal free space: allocate uses whichever max returns first (drives insertion order)."""
    # Insertion order: first, second — equal free → first wins under max(dict.values) iteration
    drives = _make_drives(tmp_path, ("first", "second"))
    alloc, _ = _allocator(tmp_path, drives)

    def fake_disk_usage(path: str | os.PathLike[str]) -> _FakeUsage:
        return _FakeUsage(total=100, used=0, free=50)

    import shutil

    monkeypatch.setattr(shutil, "disk_usage", fake_disk_usage)

    target = alloc.allocate("tied")
    assert target == os.path.join(drives["first"], "tied")


def test_allocate_duplicate_raises_duplicate_branch_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """allocate on an already-recorded branch raises DuplicateBranchError."""
    alloc, _ = _allocator(tmp_path)
    DuplicateBranchError = _exc("DuplicateBranchError")

    def fake_disk_usage(path: str | os.PathLike[str]) -> _FakeUsage:
        return _FakeUsage(total=100, used=0, free=50)

    import shutil

    monkeypatch.setattr(shutil, "disk_usage", fake_disk_usage)

    alloc.allocate("same")
    with pytest.raises(DuplicateBranchError):
        alloc.allocate("same")


# --- get_path ---


def test_get_path_joins_drive_and_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_path returns join(config_drives[drive], branch); never invents intermediates."""
    alloc, drives = _allocator(tmp_path)

    def fake_disk_usage(path: str | os.PathLike[str]) -> _FakeUsage:
        return _FakeUsage(total=100, used=0, free=50)

    import shutil

    monkeypatch.setattr(shutil, "disk_usage", fake_disk_usage)

    alloc.allocate("a/b/c")
    assert alloc.get_path("a/b/c") == os.path.join(drives["drive1"], "a/b/c")
    BranchNotFoundError = _exc("BranchNotFoundError")
    with pytest.raises(BranchNotFoundError):
        alloc.get_path("a")
    with pytest.raises(BranchNotFoundError):
        alloc.get_path("a/b")


def test_get_path_unknown_branch_raises_branch_not_found_error(tmp_path: Path) -> None:
    """get_path for a missing DB row raises BranchNotFoundError."""
    alloc, _ = _allocator(tmp_path)
    BranchNotFoundError = _exc("BranchNotFoundError")
    with pytest.raises(BranchNotFoundError):
        alloc.get_path("never/allocated")


def test_get_path_stale_drive_raises_stale_drive_error(tmp_path: Path) -> None:
    """get_path when DB drive_name is not in loaded config raises StaleDriveError."""
    StorageManager = _pkg().StorageManager
    drives = _make_drives(tmp_path, ("drive1",))
    config_path = _write_config(tmp_path / "config.json", drives)
    db_path = tmp_path / "loc.db"
    sm = StorageManager(db_path)
    sm.record_location("orphan", "removed_drive")
    alloc = _allocator_cls()(config_path, db_path)
    StaleDriveError = _exc("StaleDriveError")
    with pytest.raises(StaleDriveError):
        alloc.get_path("orphan")


# --- delete_branch ---


def test_delete_branch_removes_directory_and_db_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """delete_branch removes the on-disk tree and the location row."""
    alloc, _ = _allocator(tmp_path)

    def fake_disk_usage(path: str | os.PathLike[str]) -> _FakeUsage:
        return _FakeUsage(total=100, used=0, free=50)

    import shutil

    monkeypatch.setattr(shutil, "disk_usage", fake_disk_usage)

    target = alloc.allocate("to/delete")
    assert Path(target).is_dir()
    alloc.delete_branch("to/delete")
    assert not Path(target).exists()
    BranchNotFoundError = _exc("BranchNotFoundError")
    with pytest.raises(BranchNotFoundError):
        alloc.get_path("to/delete")


def test_delete_branch_unknown_raises_branch_not_found_error(tmp_path: Path) -> None:
    """delete_branch on an unknown branch raises BranchNotFoundError."""
    alloc, _ = _allocator(tmp_path)
    BranchNotFoundError = _exc("BranchNotFoundError")
    with pytest.raises(BranchNotFoundError):
        alloc.delete_branch("missing")


# --- make_directory / remove_directory guards ---


def test_make_directory_inside_drive_creates_tree(tmp_path: Path) -> None:
    """make_directory creates a directory tree under a configured drive root."""
    alloc, drives = _allocator(tmp_path)
    path = os.path.join(drives["drive1"], "nested", "dir")
    alloc.make_directory(path)
    assert Path(path).is_dir()


def test_make_directory_outside_drives_raises_path_outside_drives_error(
    tmp_path: Path,
) -> None:
    """make_directory outside configured drive prefixes raises PathOutsideDrivesError."""
    alloc, _ = _allocator(tmp_path)
    PathOutsideDrivesError = _exc("PathOutsideDrivesError")
    outside = str(tmp_path / "outside" / "dir")
    with pytest.raises(PathOutsideDrivesError):
        alloc.make_directory(outside)


def test_remove_directory_outside_drives_raises_path_outside_drives_error(
    tmp_path: Path,
) -> None:
    """remove_directory outside configured drive prefixes raises PathOutsideDrivesError."""
    alloc, _ = _allocator(tmp_path)
    PathOutsideDrivesError = _exc("PathOutsideDrivesError")
    outside = str(tmp_path / "outside")
    outside_path = Path(outside)
    outside_path.mkdir(parents=True)
    with pytest.raises(PathOutsideDrivesError):
        alloc.remove_directory(outside)


def test_remove_directory_missing_raises_path_not_found_error(tmp_path: Path) -> None:
    """remove_directory for a missing path under a drive raises PathNotFoundError."""
    alloc, drives = _allocator(tmp_path)
    PathNotFoundError = _exc("PathNotFoundError")
    missing = os.path.join(drives["drive1"], "no", "such")
    with pytest.raises(PathNotFoundError):
        alloc.remove_directory(missing)


def test_remove_directory_inside_drive_removes_tree(tmp_path: Path) -> None:
    """remove_directory deletes an existing tree under a configured drive."""
    alloc, drives = _allocator(tmp_path)
    path = os.path.join(drives["drive1"], "rm", "me")
    alloc.make_directory(path)
    assert Path(path).is_dir()
    alloc.remove_directory(path)
    assert not Path(path).exists()


def test_drive_prefix_guard_uses_startswith(tmp_path: Path) -> None:
    """Guard is string startswith on configured drive paths (legacy)."""
    alloc, drives = _allocator(tmp_path)
    PathOutsideDrivesError = _exc("PathOutsideDrivesError")
    # Path that does not start with either drive string
    sibling = str(Path(drives["drive1"]).parent / "other_root" / "x")
    Path(sibling).parent.mkdir(parents=True, exist_ok=True)
    with pytest.raises(PathOutsideDrivesError):
        alloc.make_directory(sibling)
