"""Default RC path for buddingScripts (SPEC002 slice).

Encodes Path.home() / .buddingScriptsRC.json as the only v1 RC location.
No CLI --rc override; no SPEC003 home-RC load-at-startup wiring.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _default_rc_path():
    """Default RC path helper must be importable without the CLI."""
    pkg = importlib.import_module("buddingScripts")
    assert hasattr(pkg, "default_rc_path"), (
        "expected buddingScripts.default_rc_path for the Planned RC path"
    )
    return pkg.default_rc_path


def test_default_rc_path_is_home_dotfile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Default (only) path is Path.home() / '.buddingScriptsRC.json'."""
    monkeypatch.setenv("HOME", str(tmp_path))
    default_rc_path = _default_rc_path()
    assert default_rc_path() == Path.home() / ".buddingScriptsRC.json"
    assert default_rc_path() == tmp_path / ".buddingScriptsRC.json"


def test_default_rc_path_filename_is_exact() -> None:
    """RC filename is exactly .buddingScriptsRC.json (legacy product name)."""
    default_rc_path = _default_rc_path()
    assert default_rc_path().name == ".buddingScriptsRC.json"


def test_v1_rc_path_surface_is_default_only() -> None:
    """v1 locks out --rc: Planned path surface is default_rc_path only (no override API)."""
    pkg = importlib.import_module("buddingScripts")
    assert hasattr(pkg, "default_rc_path")
    # No argv/--rc parsing helpers on the package public surface.
    assert not hasattr(pkg, "parse_rc_arg")
    assert not hasattr(pkg, "rc_path_from_argv")
