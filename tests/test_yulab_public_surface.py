"""Planned public surface importability (SPEC007 slice).

Symbols must be importable from the YuLabDataAllocator package for unit tests
without going through the CLI. Exact submodule layout is an implementation
detail. SPEC006 CLI / console script / -m are out of scope.
"""

from __future__ import annotations

import importlib


_PLANNED_SYMBOLS = (
    "YuLabDataAllocatorError",
    "ConfigError",
    "YuhomeUnsetError",
    "ConfigFileError",
    "InvalidConfigError",
    "DrivePathError",
    "AllocatorError",
    "DuplicateBranchError",
    "BranchNotFoundError",
    "StaleDriveError",
    "PathOutsideDrivesError",
    "PathNotFoundError",
    "LocationNotFoundError",
    "TreeError",
    "ConfigHandler",
    "StorageManager",
    "Allocator",
    "TreeVisualizer",
)


def test_planned_public_surface_importable_from_package() -> None:
    """All Planned SPEC007 symbols are importable from YuLabDataAllocator."""
    pkg = importlib.import_module("YuLabDataAllocator")
    for name in _PLANNED_SYMBOLS:
        assert hasattr(pkg, name), f"missing public symbol: {name}"
        assert getattr(pkg, name) is not None
