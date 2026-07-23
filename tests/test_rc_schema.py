"""RC JSON schema load / validate (SPEC002 slice).

Encodes top-level keys, per-generator required fields, invariants, and
config-error conditions. Does not wire home-RC load at CLI startup (SPEC003)
or render (SPEC004).
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest


def _load_rc():
    """RC loader/validator must be importable without going through the CLI."""
    pkg = importlib.import_module("buddingScripts")
    assert hasattr(pkg, "load_rc"), (
        "expected buddingScripts.load_rc to load and validate an RC JSON file"
    )
    return pkg.load_rc


def _config_error_type():
    """Config errors raise BuddingScriptsError (or a subclass)."""
    pkg = importlib.import_module("buddingScripts")
    return pkg.BuddingScriptsError


def _write_rc(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid_minimal_rc() -> dict[str, Any]:
    """Minimal valid RC: one generator, matching suffix, one template."""
    return {
        "script_generators": {
            "bash": {
                "variables": {
                    "job_name": {
                        "default": "job",
                        "flag": "-j",
                        "help": "job name",
                    }
                },
                "setting_str": {
                    "#!/bin/bash": "job_name",
                },
            }
        },
        "templates": {
            "#header1#": "header1",
        },
        "suffix": {
            "bash": ".sh",
        },
    }


# --- successful load / top-level schema ---


def test_load_rc_returns_top_level_required_keys(tmp_path: Path) -> None:
    """Loaded RC is an object with script_generators, templates, and suffix."""
    load_rc = _load_rc()
    path = _write_rc(tmp_path / "ok.json", _valid_minimal_rc())
    data = load_rc(path)
    assert isinstance(data, dict)
    assert set(data) >= {"script_generators", "templates", "suffix"}
    assert isinstance(data["script_generators"], dict)
    assert isinstance(data["templates"], dict)
    assert isinstance(data["suffix"], dict)


def test_load_rc_ignores_unknown_top_level_keys(tmp_path: Path) -> None:
    """Unknown top-level keys are ignored (forward-compatible)."""
    load_rc = _load_rc()
    payload = _valid_minimal_rc()
    payload["future_extension"] = {"x": 1}
    path = _write_rc(tmp_path / "extra.json", payload)
    data = load_rc(path)
    assert "script_generators" in data
    assert "templates" in data
    assert "suffix" in data


def test_load_rc_allows_numeric_variable_defaults(tmp_path: Path) -> None:
    """variables.<option>.default may be a JSON number (not only string)."""
    load_rc = _load_rc()
    payload = _valid_minimal_rc()
    payload["script_generators"]["bash"]["variables"]["threads"] = {
        "default": 4,
        "flag": "-t",
        "help": "threads",
    }
    payload["script_generators"]["bash"]["setting_str"]["# threads=<setting>"] = "threads"
    path = _write_rc(tmp_path / "numeric.json", payload)
    data = load_rc(path)
    assert data["script_generators"]["bash"]["variables"]["threads"]["default"] == 4
    assert isinstance(data["script_generators"]["bash"]["variables"]["threads"]["default"], int)


def test_load_rc_preserves_setting_str_key_order(tmp_path: Path) -> None:
    """setting_str insertion order is preserved after load (header line order)."""
    load_rc = _load_rc()
    payload = _valid_minimal_rc()
    ordered = {
        "line-a: <setting>": "job_name",
        "line-b: <setting>": "job_name",
        "line-c: <setting>": "job_name",
    }
    payload["script_generators"]["bash"]["setting_str"] = ordered
    path = _write_rc(tmp_path / "order.json", payload)
    data = load_rc(path)
    assert list(data["script_generators"]["bash"]["setting_str"]) == list(ordered)


# --- invariants ---


def test_suffix_and_script_generators_are_bijective(tmp_path: Path) -> None:
    """suffix keys and script_generators keys form a bijection."""
    load_rc = _load_rc()
    payload = {
        "script_generators": {
            "slurm": {
                "variables": {
                    "job_name": {"default": "j", "flag": "-J", "help": "name"},
                },
                "setting_str": {"#SBATCH -J <setting>": "job_name"},
            },
            "bash": {
                "variables": {
                    "job_name": {"default": "j", "flag": "-j", "help": "name"},
                },
                "setting_str": {"#!/bin/bash": "job_name"},
            },
        },
        "templates": {"#header1#": "header1"},
        "suffix": {"slurm": ".slurm", "bash": ".sh"},
    }
    path = _write_rc(tmp_path / "bij.json", payload)
    data = load_rc(path)
    assert set(data["suffix"]) == set(data["script_generators"])


def test_setting_str_values_must_name_variables_keys(tmp_path: Path) -> None:
    """Every setting_str value must be a key in that generator's variables."""
    load_rc = _load_rc()
    Err = _config_error_type()
    payload = _valid_minimal_rc()
    payload["script_generators"]["bash"]["setting_str"] = {
        "bad: <setting>": "not_a_variable",
    }
    path = _write_rc(tmp_path / "bad_setting.json", payload)
    with pytest.raises(Err):
        load_rc(path)


def test_templates_values_must_be_unique(tmp_path: Path) -> None:
    """Every templates value (CLI dest) must be unique."""
    load_rc = _load_rc()
    Err = _config_error_type()
    payload = _valid_minimal_rc()
    payload["templates"] = {
        "#header1#": "header1",
        "#header2#": "header1",  # duplicate dest
    }
    path = _write_rc(tmp_path / "dup_tmpl.json", payload)
    with pytest.raises(Err):
        load_rc(path)


def test_generator_names_reject_spaces(tmp_path: Path) -> None:
    """Generator names must be non-empty and suitable as subcommands (no spaces)."""
    load_rc = _load_rc()
    Err = _config_error_type()
    payload = _valid_minimal_rc()
    payload["script_generators"] = {
        "bad name": {
            "variables": {
                "job_name": {"default": "j", "flag": "-j", "help": "n"},
            },
            "setting_str": {"x=<setting>": "job_name"},
        }
    }
    payload["suffix"] = {"bad name": ".sh"}
    path = _write_rc(tmp_path / "space.json", payload)
    with pytest.raises(Err):
        load_rc(path)


def test_generator_requires_variables_and_setting_str(tmp_path: Path) -> None:
    """Each script_generators.<name> requires variables and setting_str objects."""
    load_rc = _load_rc()
    Err = _config_error_type()
    payload = _valid_minimal_rc()
    payload["script_generators"]["bash"] = {
        "variables": {
            "job_name": {"default": "j", "flag": "-j", "help": "n"},
        }
        # missing setting_str
    }
    path = _write_rc(tmp_path / "no_setting_str.json", payload)
    with pytest.raises(Err):
        load_rc(path)


def test_variable_requires_default_flag_help(tmp_path: Path) -> None:
    """Each variables.<option> requires default, flag, and help."""
    load_rc = _load_rc()
    Err = _config_error_type()
    payload = _valid_minimal_rc()
    payload["script_generators"]["bash"]["variables"]["job_name"] = {
        "default": "j",
        "flag": "-j",
        # missing help
    }
    path = _write_rc(tmp_path / "no_help.json", payload)
    with pytest.raises(Err):
        load_rc(path)


# --- errors ---


def test_missing_rc_file_raises_with_path_message(tmp_path: Path) -> None:
    """Missing RC file fails with a clear path message."""
    load_rc = _load_rc()
    Err = _config_error_type()
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises(Err) as excinfo:
        load_rc(missing)
    assert str(missing) in str(excinfo.value)


def test_unreadable_rc_file_raises_with_path_message(tmp_path: Path) -> None:
    """Unreadable RC file fails with a clear path message."""
    load_rc = _load_rc()
    Err = _config_error_type()
    path = _write_rc(tmp_path / "unreadable.json", _valid_minimal_rc())
    path.chmod(0o000)
    try:
        with pytest.raises(Err) as excinfo:
            load_rc(path)
        assert str(path) in str(excinfo.value)
    finally:
        path.chmod(0o644)


def test_invalid_json_raises_config_error(tmp_path: Path) -> None:
    """RC that is not valid JSON fails as a config error."""
    load_rc = _load_rc()
    Err = _config_error_type()
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(Err):
        load_rc(path)


def test_rc_non_object_raises_config_error(tmp_path: Path) -> None:
    """RC JSON that is not a single object fails as a config error."""
    load_rc = _load_rc()
    Err = _config_error_type()
    path = _write_rc(tmp_path / "list.json", [1, 2, 3])
    with pytest.raises(Err):
        load_rc(path)


def test_missing_required_top_level_key_raises(tmp_path: Path) -> None:
    """Missing required top-level key is a hard config error."""
    load_rc = _load_rc()
    Err = _config_error_type()
    for key in ("script_generators", "templates", "suffix"):
        payload = _valid_minimal_rc()
        del payload[key]
        path = _write_rc(tmp_path / f"missing_{key}.json", payload)
        with pytest.raises(Err):
            load_rc(path)


def test_suffix_generators_key_mismatch_raises(tmp_path: Path) -> None:
    """suffix / script_generators key mismatch is a config error."""
    load_rc = _load_rc()
    Err = _config_error_type()
    payload = _valid_minimal_rc()
    payload["suffix"] = {"other": ".sh"}  # not bijective with generators
    path = _write_rc(tmp_path / "mismatch.json", payload)
    with pytest.raises(Err):
        load_rc(path)


def test_load_rc_default_path_when_omitted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Calling load_rc() with no path uses the default home RC path (not --rc)."""
    load_rc = _load_rc()
    monkeypatch.setenv("HOME", str(tmp_path))
    home_rc = tmp_path / ".buddingScriptsRC.json"
    _write_rc(home_rc, _valid_minimal_rc())
    data = load_rc()
    assert "script_generators" in data
