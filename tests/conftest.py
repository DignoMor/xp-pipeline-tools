"""Shared fixtures for code/ unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def code_root() -> Path:
    """Absolute path to the code/ packaging root (parent of tests/)."""
    return Path(__file__).resolve().parent.parent
