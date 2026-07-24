"""Default config and DB path resolution for YuLabDataAllocator."""

from __future__ import annotations

import os
from pathlib import Path

from .exceptions import YuhomeUnsetError

CONFIG_DIRNAME = ".YuLabDataAllocator"
CONFIG_FILENAME = "config.json"
DB_FILENAME = "YuLabDataAllocator.db"


def default_config_path() -> Path:
    """Return ``$YUHOME/.YuLabDataAllocator/config.json``.

    Raises ``YuhomeUnsetError`` if ``YUHOME`` is unset or empty.
    Does not create the file or its parent directory.
    """
    yuhome = os.environ.get("YUHOME", "")
    if not yuhome:
        raise YuhomeUnsetError(
            "YUHOME is unset or empty; required to resolve the "
            "YuLabDataAllocator config path"
        )
    return Path(yuhome) / CONFIG_DIRNAME / CONFIG_FILENAME


def default_db_path() -> Path:
    """Return ``~/.YuLabDataAllocator/YuLabDataAllocator.db`` (under ``$HOME``)."""
    return Path.home() / CONFIG_DIRNAME / DB_FILENAME
