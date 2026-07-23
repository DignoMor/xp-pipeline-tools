"""Planned public surface importability (SPEC004 slice).

Symbols must be importable from the buddingScripts package for unit tests
without going through the CLI. Exact submodule layout is an implementation
detail.
"""

from __future__ import annotations

import importlib


_PLANNED_SYMBOLS = (
    "BuddingScriptsError",
    "CLIInputError",
    "code_generator",
    "script_generator_settings",
    "script_generator",
)


def test_planned_public_surface_importable_from_package() -> None:
    """All Planned SPEC004 symbols are importable from buddingScripts."""
    pkg = importlib.import_module("buddingScripts")
    for name in _PLANNED_SYMBOLS:
        assert hasattr(pkg, name), f"missing public symbol: {name}"
        assert getattr(pkg, name) is not None
