"""RC path helpers and schema validation for buddingScriptsRC.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .exceptions import BuddingScriptsError

DEFAULT_RC_FILENAME = ".buddingScriptsRC.json"
REQUIRED_TOP_LEVEL_KEYS = ("script_generators", "templates", "suffix")
REQUIRED_GENERATOR_KEYS = ("variables", "setting_str")
REQUIRED_VARIABLE_FIELDS = ("default", "flag", "help")


class RCConfigError(BuddingScriptsError):
    """Raised when an RC file is missing, unreadable, or fails schema checks."""

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


def default_rc_path() -> Path:
    """Return the v1 default RC path: ``~/.buddingScriptsRC.json``."""
    return Path.home() / DEFAULT_RC_FILENAME


def validate_rc(data: Any) -> dict[str, Any]:
    """Validate an RC object against the SPEC002 schema invariants.

    Returns ``data`` unchanged when valid. Raises ``RCConfigError`` on failure.
    Unknown top-level keys are ignored (forward-compatible).
    """
    if not isinstance(data, dict):
        raise RCConfigError("RC must be a JSON object")

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in data:
            raise RCConfigError(f"Missing required top-level key: {key}")

    script_generators = data["script_generators"]
    templates = data["templates"]
    suffix = data["suffix"]

    if not isinstance(script_generators, dict):
        raise RCConfigError("'script_generators' must be an object")
    if not isinstance(templates, dict):
        raise RCConfigError("'templates' must be an object")
    if not isinstance(suffix, dict):
        raise RCConfigError("'suffix' must be an object")

    gen_names = set(script_generators.keys())
    suffix_names = set(suffix.keys())
    if gen_names != suffix_names:
        missing_in_suffix = sorted(gen_names - suffix_names)
        missing_in_gens = sorted(suffix_names - gen_names)
        parts: list[str] = []
        if missing_in_suffix:
            parts.append(
                "generators missing from suffix: "
                + ", ".join(missing_in_suffix)
            )
        if missing_in_gens:
            parts.append(
                "suffix keys missing from script_generators: "
                + ", ".join(missing_in_gens)
            )
        raise RCConfigError(
            "suffix / script_generators key mismatch; " + "; ".join(parts)
        )

    dests: list[str] = []
    for placeholder, dest in templates.items():
        if not isinstance(dest, str) or not dest:
            raise RCConfigError(
                f"templates[{placeholder!r}] must be a non-empty string dest"
            )
        dests.append(dest)
    if len(dests) != len(set(dests)):
        raise RCConfigError("templates values (CLI dests) must be unique")

    for name, generator in script_generators.items():
        if not isinstance(name, str) or not name or " " in name:
            raise RCConfigError(
                f"Invalid generator name {name!r}: "
                "must be a non-empty string with no spaces"
            )
        if not isinstance(generator, dict):
            raise RCConfigError(
                f"script_generators[{name!r}] must be an object"
            )
        for key in REQUIRED_GENERATOR_KEYS:
            if key not in generator:
                raise RCConfigError(
                    f"script_generators[{name!r}] missing required key: {key}"
                )

        variables = generator["variables"]
        setting_str = generator["setting_str"]
        if not isinstance(variables, dict):
            raise RCConfigError(
                f"script_generators[{name!r}].variables must be an object"
            )
        if not isinstance(setting_str, dict):
            raise RCConfigError(
                f"script_generators[{name!r}].setting_str must be an object"
            )

        for option, fields in variables.items():
            if not isinstance(fields, dict):
                raise RCConfigError(
                    f"script_generators[{name!r}].variables[{option!r}] "
                    "must be an object"
                )
            for field in REQUIRED_VARIABLE_FIELDS:
                if field not in fields:
                    raise RCConfigError(
                        f"script_generators[{name!r}].variables[{option!r}] "
                        f"missing required field: {field}"
                    )
            default = fields["default"]
            if not isinstance(default, (str, int, float)) or isinstance(
                default, bool
            ):
                raise RCConfigError(
                    f"script_generators[{name!r}].variables[{option!r}]"
                    ".default must be a string or number"
                )

        for line_template, option_name in setting_str.items():
            if option_name not in variables:
                raise RCConfigError(
                    f"script_generators[{name!r}].setting_str "
                    f"references unknown variable {option_name!r} "
                    f"(line template {line_template!r})"
                )

        if name not in suffix or not isinstance(suffix[name], str):
            raise RCConfigError(
                f"suffix[{name!r}] must be a string (including leading '.')"
            )

    return data


def load_rc(path: Path | None = None) -> dict[str, Any]:
    """Load and validate an RC JSON file.

    ``path`` defaults to :func:`default_rc_path`. Does not accept a CLI
    ``--rc`` override (v1 has a single default path); callers may pass an
    explicit path for tests or tooling.
    """
    rc_path = Path(path) if path is not None else default_rc_path()
    try:
        text = rc_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RCConfigError(f"RC file not found: {rc_path}") from exc
    except OSError as exc:
        raise RCConfigError(f"RC file unreadable: {rc_path}: {exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RCConfigError(
            f"RC file is not valid JSON: {rc_path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise RCConfigError(f"RC file must contain a JSON object: {rc_path}")

    return validate_rc(data)
