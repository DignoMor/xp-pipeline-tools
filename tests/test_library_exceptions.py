"""Exception types for the buddingScripts library API (SPEC004 slice).

Encodes BuddingScriptsError / CLIInputError hierarchy, construction, and
stable str(). SPEC003 locks str(CLIInputError) to 'CLI input Error: …';
CLI argv / .list I/O conditions live in test_cli_surface.py.
"""

from __future__ import annotations

import importlib


def _import_exceptions():
    """Library exceptions must be importable without going through the CLI."""
    pkg = importlib.import_module("buddingScripts")
    return pkg.BuddingScriptsError, pkg.CLIInputError


def test_buddingScriptsError_is_exception_not_baseexception() -> None:
    """BuddingScriptsError is an Exception (usable with except Exception)."""
    BuddingScriptsError, _ = _import_exceptions()
    assert issubclass(BuddingScriptsError, Exception)
    # Not a bare BaseException-only type: Exception is required.
    assert issubclass(BuddingScriptsError, BaseException)


def test_cliInputError_subclasses_buddingScriptsError() -> None:
    """CLIInputError subclasses BuddingScriptsError."""
    BuddingScriptsError, CLIInputError = _import_exceptions()
    assert issubclass(CLIInputError, BuddingScriptsError)
    assert issubclass(CLIInputError, Exception)


def test_cliInputError_stores_message_default_empty() -> None:
    """CLIInputError(message='') stores message; default is empty string."""
    _, CLIInputError = _import_exceptions()
    err_default = CLIInputError()
    assert err_default.message == ""
    err_explicit = CLIInputError(message="")
    assert err_explicit.message == ""
    err_msg = CLIInputError(message="bad input")
    assert err_msg.message == "bad input"


def test_cliInputError_str_is_stable_prefixed_form() -> None:
    """str(CLIInputError) keeps locked prefix 'CLI input Error: …' (SPEC003 pick)."""
    _, CLIInputError = _import_exceptions()
    err = CLIInputError(message="missing flag")
    text = str(err)
    assert text == str(err)  # stable
    assert text == "CLI input Error: missing flag"
    assert text.startswith("CLI input Error:")


def test_cliInputError_empty_message_str_stable() -> None:
    """Empty-message CLIInputError still has the locked prefixed str form."""
    _, CLIInputError = _import_exceptions()
    err = CLIInputError(message="")
    assert str(err) == "CLI input Error: "
    assert str(err) == str(err)
