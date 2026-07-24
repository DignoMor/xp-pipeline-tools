"""AllocatorError-family types for SPEC007 domain conditions.

Encodes the domain exception hierarchy under AllocatorError / YuLabDataAllocatorError,
construction, and stable str(). ConfigError family lives in test_yulab_config_errors.py.
"""

from __future__ import annotations

import importlib


_ALLOCATOR_ERROR_NAMES = (
    "AllocatorError",
    "DuplicateBranchError",
    "BranchNotFoundError",
    "StaleDriveError",
    "PathOutsideDrivesError",
    "PathNotFoundError",
    "LocationNotFoundError",
    "TreeError",
)


def _import_allocator_errors():
    """AllocatorError family must be importable without going through the CLI."""
    pkg = importlib.import_module("YuLabDataAllocator")
    names = ("YuLabDataAllocatorError", *_ALLOCATOR_ERROR_NAMES)
    missing = [n for n in names if not hasattr(pkg, n)]
    assert not missing, f"missing public symbols: {missing}"
    return {n: getattr(pkg, n) for n in names}


def test_allocator_error_hierarchy() -> None:
    """AllocatorError subclasses form the SPEC007 domain hierarchy."""
    e = _import_allocator_errors()
    assert issubclass(e["YuLabDataAllocatorError"], Exception)
    assert issubclass(e["AllocatorError"], e["YuLabDataAllocatorError"])
    for name in (
        "DuplicateBranchError",
        "BranchNotFoundError",
        "StaleDriveError",
        "PathOutsideDrivesError",
        "PathNotFoundError",
        "LocationNotFoundError",
        "TreeError",
    ):
        assert issubclass(e[name], e["AllocatorError"]), name
        assert issubclass(e[name], e["YuLabDataAllocatorError"]), name
        assert issubclass(e[name], Exception), name


def test_allocator_errors_are_constructible_with_stable_str() -> None:
    """AllocatorError-family types construct and expose a stable str() message."""
    e = _import_allocator_errors()
    for name in _ALLOCATOR_ERROR_NAMES:
        cls = e[name]
        err = cls("detail")
        text = str(err)
        assert text == str(err)  # stable
        assert "detail" in text


def test_allocator_errors_catchable_as_bases() -> None:
    """Fine subclasses are catchable as AllocatorError / YuLabDataAllocatorError."""
    e = _import_allocator_errors()
    for name in (
        "DuplicateBranchError",
        "BranchNotFoundError",
        "StaleDriveError",
        "PathOutsideDrivesError",
        "PathNotFoundError",
        "LocationNotFoundError",
        "TreeError",
    ):
        err = e[name]("x")
        assert isinstance(err, e["AllocatorError"])
        assert isinstance(err, e["YuLabDataAllocatorError"])
