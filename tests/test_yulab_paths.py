"""Default config/DB paths for YuLabDataAllocator (SPEC005 slice).

Encodes $YUHOME config path and $HOME DB path as the only v1 locations.
No CLI --config / --db overrides; paths live under different parents.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _default_config_path():
    """Default config path helper must be importable without the CLI."""
    pkg = importlib.import_module("YuLabDataAllocator")
    assert hasattr(pkg, "default_config_path"), (
        "expected YuLabDataAllocator.default_config_path for the Planned config path"
    )
    return pkg.default_config_path


def _default_db_path():
    """Default DB path helper must be importable without the CLI."""
    pkg = importlib.import_module("YuLabDataAllocator")
    assert hasattr(pkg, "default_db_path"), (
        "expected YuLabDataAllocator.default_db_path for the Planned DB path"
    )
    return pkg.default_db_path


def _yuhome_unset_error():
    pkg = importlib.import_module("YuLabDataAllocator")
    return pkg.YuhomeUnsetError


def test_default_config_path_under_yuhome(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Default (only) config path is Path(YUHOME) / '.YuLabDataAllocator' / 'config.json'."""
    yuhome = tmp_path / "yuhome"
    yuhome.mkdir()
    monkeypatch.setenv("YUHOME", str(yuhome))
    default_config_path = _default_config_path()
    assert default_config_path() == yuhome / ".YuLabDataAllocator" / "config.json"


def test_default_config_path_filename_and_dir_are_exact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Config lives in .YuLabDataAllocator/config.json under YUHOME (legacy product names)."""
    monkeypatch.setenv("YUHOME", str(tmp_path))
    path = _default_config_path()()
    assert path.name == "config.json"
    assert path.parent.name == ".YuLabDataAllocator"


def test_default_db_path_under_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Default (only) DB path is Path.home() / '.YuLabDataAllocator' / 'YuLabDataAllocator.db'."""
    monkeypatch.setenv("HOME", str(tmp_path))
    default_db_path = _default_db_path()
    assert default_db_path() == Path.home() / ".YuLabDataAllocator" / "YuLabDataAllocator.db"
    assert default_db_path() == tmp_path / ".YuLabDataAllocator" / "YuLabDataAllocator.db"


def test_default_db_path_filename_and_dir_are_exact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """DB filename is exactly YuLabDataAllocator.db under .YuLabDataAllocator/."""
    monkeypatch.setenv("HOME", str(tmp_path))
    path = _default_db_path()()
    assert path.name == "YuLabDataAllocator.db"
    assert path.parent.name == ".YuLabDataAllocator"


def test_config_and_db_default_paths_are_not_same_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Config path is under $YUHOME; DB path is under $HOME — not the same directory."""
    yuhome = tmp_path / "lab"
    home = tmp_path / "user"
    yuhome.mkdir()
    home.mkdir()
    monkeypatch.setenv("YUHOME", str(yuhome))
    monkeypatch.setenv("HOME", str(home))
    config_path = _default_config_path()()
    db_path = _default_db_path()()
    assert config_path.parent != db_path.parent
    assert config_path.is_relative_to(yuhome)
    assert db_path.is_relative_to(home)


def test_yuhome_unset_raises_yuhome_unset_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolving default config path with YUHOME unset raises YuhomeUnsetError naming YUHOME."""
    monkeypatch.delenv("YUHOME", raising=False)
    default_config_path = _default_config_path()
    Err = _yuhome_unset_error()
    with pytest.raises(Err) as excinfo:
        default_config_path()
    assert "YUHOME" in str(excinfo.value)


def test_yuhome_empty_raises_yuhome_unset_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolving default config path with empty YUHOME raises YuhomeUnsetError naming YUHOME."""
    monkeypatch.setenv("YUHOME", "")
    default_config_path = _default_config_path()
    Err = _yuhome_unset_error()
    with pytest.raises(Err) as excinfo:
        default_config_path()
    assert "YUHOME" in str(excinfo.value)


def test_v1_path_surface_is_default_only() -> None:
    """v1 locks out --config/--db: Planned path surface is default helpers only."""
    pkg = importlib.import_module("YuLabDataAllocator")
    assert hasattr(pkg, "default_config_path")
    assert hasattr(pkg, "default_db_path")
    assert not hasattr(pkg, "parse_config_arg")
    assert not hasattr(pkg, "parse_db_arg")
    assert not hasattr(pkg, "config_path_from_argv")
    assert not hasattr(pkg, "db_path_from_argv")
