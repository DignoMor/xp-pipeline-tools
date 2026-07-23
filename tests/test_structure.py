"""Structure invariants for the first Planned component (SPEC001 slice).

Encodes the code/ top-level layout for buddingScripts only: packaging root,
src/buddingScripts/, and tests/. Does not require TBD sibling CLI packages.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_packaging_root_has_pyproject(code_root: Path) -> None:
    """Packaging lives at the code/ repo root (e.g. pyproject.toml)."""
    assert (code_root / "pyproject.toml").is_file()


def test_tests_directory_exists(code_root: Path) -> None:
    """Unit tests for all components live under code/tests/."""
    assert (code_root / "tests").is_dir()
    assert Path(__file__).resolve().is_relative_to(code_root / "tests")


def test_first_cli_package_directory_exists(code_root: Path) -> None:
    """One top-level package directory per CLI; buddingScripts is first."""
    pkg_dir = code_root / "src" / "buddingScripts"
    assert pkg_dir.is_dir(), (
        "expected code/src/buddingScripts/ as the first CLI package directory"
    )


def test_packaging_assets_are_under_code_not_specs_or_docs(code_root: Path) -> None:
    """Packaging and deployment assets live only under code/."""
    workspace = code_root.parent
    assert not (workspace / "specs" / "pyproject.toml").exists()
    assert not (workspace / "docs" / "pyproject.toml").exists()
    assert (code_root / "pyproject.toml").is_file()


def test_pyproject_declares_python_310_floor(code_root: Path) -> None:
    """Product Python version floor is 3.10+ (packaging detail of the floor)."""
    text = (code_root / "pyproject.toml").read_text(encoding="utf-8")
    assert "requires-python" in text.lower() or "requires_python" in text.lower()
    # Accept common TOML forms that encode >=3.10
    assert ">=3.10" in text or ">=3.10.0" in text


def test_pyproject_registers_buddingScripts_console_script(code_root: Path) -> None:
    """Packaging registers the buddingScripts console-script entrypoint."""
    text = (code_root / "pyproject.toml").read_text(encoding="utf-8")
    assert "buddingScripts" in text
    # Entrypoint wiring section (setuptools / PEP 621 scripts)
    assert "[project.scripts]" in text or "console_scripts" in text
