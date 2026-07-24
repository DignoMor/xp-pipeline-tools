"""Shipped example config under code/example_configs/ (SPEC005 slice).

Normative shape: drives map with ≥2 absolute path strings (placeholders OK).
Must not embed a lab $YUHOME tree. Load/validate against temp drive dirs.
"""

from __future__ import annotations

import importlib
import json
import os
import re
from pathlib import Path
from typing import Any


def _example_config_path(code_root: Path) -> Path:
    """SPEC005 ships example_configs/YuLabDataAllocator-config.json (or equivalent)."""
    preferred = code_root / "example_configs" / "YuLabDataAllocator-config.json"
    if preferred.is_file():
        return preferred
    # Allow an equivalent filename under example_configs/ that names the component.
    candidates = sorted(
        (code_root / "example_configs").glob("*YuLabDataAllocator*config*.json")
    )
    assert candidates, (
        f"expected shipped example under {code_root / 'example_configs'} "
        "(YuLabDataAllocator-config.json or equivalent)"
    )
    return candidates[0]


def _load_example(code_root: Path) -> dict[str, Any]:
    path = _example_config_path(code_root)
    assert path.is_file(), f"expected shipped example config at {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _config_handler_cls():
    pkg = importlib.import_module("YuLabDataAllocator")
    assert hasattr(pkg, "ConfigHandler")
    return pkg.ConfigHandler


def test_shipped_example_config_exists(code_root: Path) -> None:
    """Package ships an example config under code/example_configs/."""
    path = _example_config_path(code_root)
    assert path.is_file()


def test_example_has_drives_object_with_at_least_two_entries(code_root: Path) -> None:
    """Shipped example has drives map with at least two drives."""
    data = _load_example(code_root)
    assert "drives" in data
    assert isinstance(data["drives"], dict)
    assert len(data["drives"]) >= 2


def test_example_drive_values_are_absolute_strings(code_root: Path) -> None:
    """Each drives value is an absolute path string (placeholders allowed)."""
    data = _load_example(code_root)
    for name, drive_path in data["drives"].items():
        assert isinstance(name, str) and name, "drive names must be non-empty"
        assert isinstance(drive_path, str), f"{name} value must be a string"
        assert os.path.isabs(drive_path), f"{name} must be absolute: {drive_path!r}"


def test_example_does_not_embed_lab_yuhome_tree(code_root: Path) -> None:
    """Shipped file must not embed a single lab's $YUHOME tree layout."""
    data = _load_example(code_root)
    # Reject lab-style home trees; illustrative /tmp/... placeholders are fine.
    labish = re.compile(
        r"(^|/)\.YuLabDataAllocator(/|$)|/home/[^/]+/|/Users/[^/]+/",
        re.IGNORECASE,
    )
    for name, drive_path in data["drives"].items():
        assert not labish.search(drive_path), (
            f"example drive {name!r} must not embed lab $YUHOME/$HOME trees: {drive_path!r}"
        )


def test_example_passes_config_handler_with_temp_drive_dirs(
    code_root: Path, tmp_path: Path
) -> None:
    """Unit tests point drives at absolute temp dirs; ConfigHandler then succeeds."""
    ConfigHandler = _config_handler_cls()
    data = _load_example(code_root)
    rewritten: dict[str, str] = {}
    for name in data["drives"]:
        root = tmp_path / "drives" / name
        root.mkdir(parents=True)
        rewritten[name] = str(root.resolve())
    cfg_path = tmp_path / "YuLabDataAllocator-config.json"
    cfg_path.write_text(json.dumps({"drives": rewritten}), encoding="utf-8")
    handler = ConfigHandler(cfg_path)
    assert set(handler.get_drive_paths()) == set(rewritten)
    for path in handler.get_drive_paths().values():
        assert os.path.isabs(path) and os.path.exists(path)
