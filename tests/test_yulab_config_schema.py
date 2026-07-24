"""Config JSON load / validate for YuLabDataAllocator (SPEC005 slice).

Encodes drives map schema, absolute+exist path rules, ≥1 drive, and
ConfigError-family conditions. Does not wire CLI (SPEC006) or Allocator
(SPEC007 allocate/get/delete).
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any

import pytest


def _config_handler_cls():
    """ConfigHandler must be importable without going through the CLI."""
    pkg = importlib.import_module("YuLabDataAllocator")
    assert hasattr(pkg, "ConfigHandler"), (
        "expected YuLabDataAllocator.ConfigHandler to load and validate config JSON"
    )
    return pkg.ConfigHandler


def _exc(name: str):
    pkg = importlib.import_module("YuLabDataAllocator")
    assert hasattr(pkg, name), f"expected YuLabDataAllocator.{name}"
    return getattr(pkg, name)


def _write_config(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid_drives(tmp_path: Path, names: tuple[str, ...] = ("drive1", "drive2")) -> dict[str, str]:
    """Build a drives map pointing at absolute existing temp directories."""
    drives: dict[str, str] = {}
    for name in names:
        root = tmp_path / "drives" / name
        root.mkdir(parents=True, exist_ok=True)
        drives[name] = str(root.resolve())
    return drives


def _valid_config(tmp_path: Path) -> dict[str, Any]:
    return {"drives": _valid_drives(tmp_path)}


# --- successful load / schema ---


def test_config_handler_loads_drives_map(tmp_path: Path) -> None:
    """ConfigHandler loads a JSON object with required top-level key drives."""
    ConfigHandler = _config_handler_cls()
    path = _write_config(tmp_path / "config.json", _valid_config(tmp_path))
    handler = ConfigHandler(path)
    drives = handler.get_drive_paths()
    assert isinstance(drives, dict)
    assert len(drives) >= 1
    assert set(drives) == set(_valid_config(tmp_path)["drives"])


def test_config_handler_ignores_unknown_top_level_keys(tmp_path: Path) -> None:
    """Unknown top-level keys are ignored (forward-compatible)."""
    ConfigHandler = _config_handler_cls()
    payload = _valid_config(tmp_path)
    payload["future_extension"] = {"x": 1}
    path = _write_config(tmp_path / "extra.json", payload)
    handler = ConfigHandler(path)
    drives = handler.get_drive_paths()
    assert "drive1" in drives
    assert "drive2" in drives


def test_get_drive_paths_returns_absolute_existing_paths(tmp_path: Path) -> None:
    """Each drives value is an absolute path that exists at load time."""
    ConfigHandler = _config_handler_cls()
    path = _write_config(tmp_path / "config.json", _valid_config(tmp_path))
    handler = ConfigHandler(path)
    for name, drive_path in handler.get_drive_paths().items():
        assert isinstance(name, str) and name
        assert os.path.isabs(drive_path), f"{name} path must be absolute"
        assert os.path.exists(drive_path), f"{name} path must exist"


def test_validate_paths_succeeds_for_valid_drives(tmp_path: Path) -> None:
    """validate_paths accepts absolute existing drive roots."""
    ConfigHandler = _config_handler_cls()
    path = _write_config(tmp_path / "config.json", _valid_config(tmp_path))
    handler = ConfigHandler(path)
    handler.validate_paths()  # must not raise


def test_config_handler_does_not_auto_create_config_file(tmp_path: Path) -> None:
    """Config file and parent must not be auto-created on missing path."""
    ConfigHandler = _config_handler_cls()
    ConfigFileError = _exc("ConfigFileError")
    missing = tmp_path / ".YuLabDataAllocator" / "config.json"
    assert not missing.exists()
    assert not missing.parent.exists()
    with pytest.raises(ConfigFileError):
        ConfigHandler(missing)
    assert not missing.exists()
    assert not missing.parent.exists()


def test_reload_config_re_reads_and_re_validates(tmp_path: Path) -> None:
    """reload_config re-reads the file and re-validates drives."""
    ConfigHandler = _config_handler_cls()
    path = _write_config(tmp_path / "config.json", _valid_config(tmp_path))
    handler = ConfigHandler(path)
    new_drive = tmp_path / "drives" / "drive3"
    new_drive.mkdir(parents=True)
    updated = {"drives": {**handler.get_drive_paths(), "drive3": str(new_drive.resolve())}}
    path.write_text(json.dumps(updated), encoding="utf-8")
    handler.reload_config()
    assert "drive3" in handler.get_drive_paths()


# --- errors ---


def test_missing_config_file_raises_config_file_error(tmp_path: Path) -> None:
    """Missing config file fails with ConfigFileError naming the path."""
    ConfigHandler = _config_handler_cls()
    ConfigFileError = _exc("ConfigFileError")
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises(ConfigFileError) as excinfo:
        ConfigHandler(missing)
    assert str(missing) in str(excinfo.value)


def test_unreadable_config_file_raises_config_file_error(tmp_path: Path) -> None:
    """Unreadable config file fails with ConfigFileError naming the path."""
    ConfigHandler = _config_handler_cls()
    ConfigFileError = _exc("ConfigFileError")
    path = _write_config(tmp_path / "unreadable.json", _valid_config(tmp_path))
    path.chmod(0o000)
    try:
        with pytest.raises(ConfigFileError) as excinfo:
            ConfigHandler(path)
        assert str(path) in str(excinfo.value)
    finally:
        path.chmod(0o644)


def test_invalid_json_raises_invalid_config_error(tmp_path: Path) -> None:
    """Config that is not valid JSON fails as InvalidConfigError."""
    ConfigHandler = _config_handler_cls()
    InvalidConfigError = _exc("InvalidConfigError")
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(InvalidConfigError):
        ConfigHandler(path)


def test_config_non_object_raises_invalid_config_error(tmp_path: Path) -> None:
    """Config JSON that is not a single object fails as InvalidConfigError."""
    ConfigHandler = _config_handler_cls()
    InvalidConfigError = _exc("InvalidConfigError")
    path = _write_config(tmp_path / "list.json", [1, 2, 3])
    with pytest.raises(InvalidConfigError):
        ConfigHandler(path)


def test_missing_drives_key_raises_invalid_config_error(tmp_path: Path) -> None:
    """Missing drives key is a hard InvalidConfigError."""
    ConfigHandler = _config_handler_cls()
    InvalidConfigError = _exc("InvalidConfigError")
    path = _write_config(tmp_path / "no_drives.json", {"other": {}})
    with pytest.raises(InvalidConfigError):
        ConfigHandler(path)


def test_drives_non_object_raises_invalid_config_error(tmp_path: Path) -> None:
    """Non-object drives value is a hard InvalidConfigError."""
    ConfigHandler = _config_handler_cls()
    InvalidConfigError = _exc("InvalidConfigError")
    path = _write_config(tmp_path / "drives_list.json", {"drives": ["not", "object"]})
    with pytest.raises(InvalidConfigError):
        ConfigHandler(path)


def test_empty_drives_raises_invalid_config_error(tmp_path: Path) -> None:
    """Empty drives object (≥1 required) is a hard InvalidConfigError."""
    ConfigHandler = _config_handler_cls()
    InvalidConfigError = _exc("InvalidConfigError")
    path = _write_config(tmp_path / "empty.json", {"drives": {}})
    with pytest.raises(InvalidConfigError):
        ConfigHandler(path)


def test_empty_drive_name_raises_invalid_config_error(tmp_path: Path) -> None:
    """Drive names must be non-empty strings."""
    ConfigHandler = _config_handler_cls()
    InvalidConfigError = _exc("InvalidConfigError")
    root = tmp_path / "d"
    root.mkdir()
    path = _write_config(tmp_path / "empty_name.json", {"drives": {"": str(root.resolve())}})
    with pytest.raises(InvalidConfigError):
        ConfigHandler(path)


def test_relative_drive_path_raises_drive_path_error(tmp_path: Path) -> None:
    """Relative drive path is a DrivePathError naming drive + path."""
    ConfigHandler = _config_handler_cls()
    DrivePathError = _exc("DrivePathError")
    rel = "relative/drive"
    (tmp_path / "relative" / "drive").mkdir(parents=True)
    path = _write_config(tmp_path / "rel.json", {"drives": {"d1": rel}})
    with pytest.raises(DrivePathError) as excinfo:
        ConfigHandler(path)
    msg = str(excinfo.value)
    assert "d1" in msg
    assert rel in msg


def test_missing_drive_path_raises_drive_path_error(tmp_path: Path) -> None:
    """Drive path that does not exist is a DrivePathError naming drive + path."""
    ConfigHandler = _config_handler_cls()
    DrivePathError = _exc("DrivePathError")
    missing = str((tmp_path / "no_such_drive").resolve())
    path = _write_config(tmp_path / "miss.json", {"drives": {"d1": missing}})
    with pytest.raises(DrivePathError) as excinfo:
        ConfigHandler(path)
    msg = str(excinfo.value)
    assert "d1" in msg
    assert missing in msg


def test_drive_path_errors_are_config_errors(tmp_path: Path) -> None:
    """DrivePathError is catchable as ConfigError."""
    ConfigHandler = _config_handler_cls()
    ConfigError = _exc("ConfigError")
    DrivePathError = _exc("DrivePathError")
    missing = str((tmp_path / "gone").resolve())
    path = _write_config(tmp_path / "miss.json", {"drives": {"d1": missing}})
    with pytest.raises(ConfigError):
        ConfigHandler(path)
    with pytest.raises(DrivePathError):
        ConfigHandler(path)
