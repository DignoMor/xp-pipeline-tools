"""ConfigError-family types for SPEC005 load/path conditions.

Exception types are owned by SPEC007; this slice only requires the hierarchy
and raiseability for config resolve / file / JSON / drives / drive-path
failures. AllocatorError subclasses are out of scope.
"""

from __future__ import annotations

import importlib


def _import_config_errors():
    """ConfigError family must be importable without going through the CLI."""
    pkg = importlib.import_module("YuLabDataAllocator")
    names = (
        "YuLabDataAllocatorError",
        "ConfigError",
        "YuhomeUnsetError",
        "ConfigFileError",
        "InvalidConfigError",
        "DrivePathError",
    )
    missing = [n for n in names if not hasattr(pkg, n)]
    assert not missing, f"missing public symbols: {missing}"
    return {n: getattr(pkg, n) for n in names}


def test_config_error_hierarchy() -> None:
    """ConfigError subclasses form the SPEC007 hierarchy under YuLabDataAllocatorError."""
    e = _import_config_errors()
    assert issubclass(e["YuLabDataAllocatorError"], Exception)
    assert issubclass(e["ConfigError"], e["YuLabDataAllocatorError"])
    assert issubclass(e["YuhomeUnsetError"], e["ConfigError"])
    assert issubclass(e["ConfigFileError"], e["ConfigError"])
    assert issubclass(e["InvalidConfigError"], e["ConfigError"])
    assert issubclass(e["DrivePathError"], e["ConfigError"])


def test_config_errors_are_constructible_with_stable_str() -> None:
    """ConfigError-family types construct and expose a stable str() message."""
    e = _import_config_errors()
    for name in (
        "YuhomeUnsetError",
        "ConfigFileError",
        "InvalidConfigError",
        "DrivePathError",
    ):
        cls = e[name]
        err = cls("detail")
        text = str(err)
        assert text == str(err)  # stable
        assert "detail" in text
