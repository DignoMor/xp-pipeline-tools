"""Install / runtime behavior for buddingScripts (SPEC001 slice).

After install from code/: buddingScripts is on PATH as a console script,
import buddingScripts works, Python floor is 3.10+, and a stub main is OK.
No RC / CLI flags / render contracts (SPEC002–004).
"""

from __future__ import annotations

import importlib
import importlib.metadata
import sys
from typing import Callable

import pytest


def _console_script_entry_points():
    """Return console_scripts entry points (Python 3.10+ compatible)."""
    eps = importlib.metadata.entry_points()
    if hasattr(eps, "select"):
        return list(eps.select(group="console_scripts"))
    return list(eps.get("console_scripts", []))  # type: ignore[arg-type]


def _budding_scripts_entrypoint():
    matches = [ep for ep in _console_script_entry_points() if ep.name == "buddingScripts"]
    assert matches, (
        "console script 'buddingScripts' is not registered; "
        "install the distribution built from code/ (e.g. pip install -e .)"
    )
    return matches[0]


def test_runtime_python_meets_310_floor() -> None:
    """Python version floor for the product is 3.10+."""
    assert sys.version_info >= (3, 10)


def test_buddingScripts_is_importable() -> None:
    """After install, import buddingScripts is available."""
    module = importlib.import_module("buddingScripts")
    assert module is not None
    assert module.__name__ == "buddingScripts"


def test_import_does_not_require_home_rc(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Missing per-CLI home RC must not block importing the package."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Ensure a fresh import path observation; package may already be loaded.
    if "buddingScripts" in sys.modules:
        del sys.modules["buddingScripts"]
    module = importlib.import_module("buddingScripts")
    assert module is not None
    assert not (tmp_path / ".buddingScriptsRC.json").exists()


def test_console_script_buddingScripts_is_registered() -> None:
    """After install, the buddingScripts console script is registered."""
    ep = _budding_scripts_entrypoint()
    assert ep.name == "buddingScripts"


def test_console_script_name_matches_importable_package() -> None:
    """Package name matches the console-script entrypoint name (legacy pattern)."""
    ep = _budding_scripts_entrypoint()
    assert ep.name == "buddingScripts"
    module = importlib.import_module("buddingScripts")
    assert module.__name__ == ep.name


def test_console_script_entrypoint_loads_callable_main() -> None:
    """Entrypoint loads a callable main (stub main is OK for this slice)."""
    ep = _budding_scripts_entrypoint()
    main = ep.load()
    assert callable(main)


def test_stub_main_invokable_without_cli_contract() -> None:
    """Stub main may no-op or exit 0; no RC/CLI/render contract is asserted."""
    ep = _budding_scripts_entrypoint()
    main: Callable = ep.load()
    try:
        result = main()
    except SystemExit as exc:
        assert exc.code in (0, None)
    else:
        assert result in (0, None)
