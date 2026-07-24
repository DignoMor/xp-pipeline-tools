"""Console CLI surface for YuLabDataAllocator (SPEC006 slice).

Encodes console script / python -m entrypoints, fixed subcommands allocate /
get / delete / ls, ls --root and -s/--short_tree, stdout contracts (path
lines; ls trailing newline), default SPEC005 config/DB wiring, pyproject
entrypoint, and typed error propagation (no catch-and-swallow).

Out of scope: SPEC005/007 library behavior changes, skill updates, interactive
confirm prompts.
"""

from __future__ import annotations

import importlib.metadata
import io
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Callable, NamedTuple

import pytest


# --- helpers (public entrypoints only; no private src imports) ---


def _console_script_entry_points():
    eps = importlib.metadata.entry_points()
    if hasattr(eps, "select"):
        return list(eps.select(group="console_scripts"))
    return list(eps.get("console_scripts", []))  # type: ignore[arg-type]


def _yulab_entrypoint():
    matches = [ep for ep in _console_script_entry_points() if ep.name == "YuLabDataAllocator"]
    assert matches, (
        "console script 'YuLabDataAllocator' is not registered; "
        "install the distribution built from code/ (e.g. pip install -e .)"
    )
    return matches[0]


def _load_main() -> Callable:
    """Public CLI main via console-script entrypoint."""
    main = _yulab_entrypoint().load()
    assert callable(main)
    return main


class _EnvRoots(NamedTuple):
    home: Path
    yuhome: Path
    drives: dict[str, str]
    config_path: Path
    db_path: Path


def _make_drives(base: Path, names: tuple[str, ...] = ("drive1", "drive2")) -> dict[str, str]:
    drives: dict[str, str] = {}
    for name in names:
        root = base / "drives" / name
        root.mkdir(parents=True, exist_ok=True)
        drives[name] = str(root.resolve())
    return drives


def _write_config(path: Path, drives: dict[str, str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"drives": drives}), encoding="utf-8")
    return path


def _prepare_env(tmp_path: Path) -> _EnvRoots:
    """Install SPEC005 default config under $YUHOME and leave $HOME ready for DB."""
    home = tmp_path / "home"
    yuhome = tmp_path / "yuhome"
    home.mkdir()
    yuhome.mkdir()
    drives = _make_drives(tmp_path)
    config_path = _write_config(
        yuhome / ".YuLabDataAllocator" / "config.json",
        drives,
    )
    db_path = home / ".YuLabDataAllocator" / "YuLabDataAllocator.db"
    return _EnvRoots(
        home=home,
        yuhome=yuhome,
        drives=drives,
        config_path=config_path,
        db_path=db_path,
    )


def _env_dict(roots: _EnvRoots) -> dict[str, str]:
    env = {**os.environ, "HOME": str(roots.home), "YUHOME": str(roots.yuhome)}
    return env


def _run_module(
    argv: list[str],
    *,
    roots: _EnvRoots,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke `python -m YuLabDataAllocator` with SPEC005 path env."""
    env = _env_dict(roots)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "YuLabDataAllocator", *argv],
        capture_output=True,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,
    )


def _run_console_script(
    argv: list[str],
    *,
    roots: _EnvRoots,
) -> subprocess.CompletedProcess[str]:
    """Prefer PATH console script; fall back to python -m."""
    env = _env_dict(roots)
    which = subprocess.run(
        ["which", "YuLabDataAllocator"],
        capture_output=True,
        text=True,
        env=env,
    )
    if which.returncode == 0 and which.stdout.strip():
        return subprocess.run(
            [which.stdout.strip(), *argv],
            capture_output=True,
            text=True,
            env=env,
            stdin=subprocess.DEVNULL,
        )
    return _run_module(argv, roots=roots)


class _FakeUsage(NamedTuple):
    total: int
    used: int
    free: int


def _force_drive2_preferred(monkeypatch: pytest.MonkeyPatch, drives: dict[str, str]) -> None:
    """Make disk_usage report more free space on drive2 (deterministic allocate)."""
    free_map = {drives["drive1"]: 10, drives["drive2"]: 999}

    def fake_disk_usage(path: str | os.PathLike[str]) -> _FakeUsage:
        p = os.path.normpath(str(path))
        for configured, free in free_map.items():
            if p == os.path.normpath(configured):
                return _FakeUsage(total=free + 1, used=1, free=free)
        # Nested paths under a drive still resolve to that drive's free space.
        for configured, free in free_map.items():
            if p.startswith(os.path.normpath(configured) + os.sep):
                return _FakeUsage(total=free + 1, used=1, free=free)
        return _FakeUsage(total=100, used=0, free=50)

    monkeypatch.setattr(shutil, "disk_usage", fake_disk_usage)


def _assert_single_path_line(stdout: str) -> str:
    """allocate/get stdout is exactly one path line plus a trailing newline."""
    assert stdout.endswith("\n"), f"expected trailing newline, got {stdout!r}"
    assert stdout.count("\n") == 1, f"expected exactly one line, got {stdout!r}"
    path = stdout[:-1]
    assert path, "path line must be non-empty"
    assert "\n" not in path
    return path


def _assert_traceback(stderr: str, stdout: str = "") -> None:
    blob = (stderr or "") + (stdout or "")
    assert "Traceback (most recent call last)" in blob


def _run_main_capture(
    argv: list[str],
    *,
    monkeypatch: pytest.MonkeyPatch,
    roots: _EnvRoots,
) -> tuple[int, str]:
    """Call public main() with sys.argv under SPEC005 env; return (code, stdout)."""
    monkeypatch.setenv("HOME", str(roots.home))
    monkeypatch.setenv("YUHOME", str(roots.yuhome))
    monkeypatch.setattr(sys, "argv", ["YuLabDataAllocator", *argv])
    main = _load_main()
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            result = main()
        except SystemExit as exc:
            code = exc.code
            if code is None:
                return 0, buf.getvalue()
            if isinstance(code, int):
                return code, buf.getvalue()
            return 1, buf.getvalue()
    if result in (0, None):
        return 0, buf.getvalue()
    return int(result), buf.getvalue()


# --- packaging / entrypoints ---


def test_pyproject_registers_YuLabDataAllocator_console_script(code_root: Path) -> None:
    """Packaging registers the YuLabDataAllocator console-script entrypoint (no .py)."""
    text = (code_root / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project.scripts]" in text or "console_scripts" in text
    assert "YuLabDataAllocator" in text
    assert "YuLabDataAllocator.py" not in text


def test_console_script_YuLabDataAllocator_is_registered() -> None:
    """After install, console script YuLabDataAllocator is registered (no .py suffix)."""
    ep = _yulab_entrypoint()
    assert ep.name == "YuLabDataAllocator"
    assert not ep.name.endswith(".py")


def test_console_script_entrypoint_loads_callable_main() -> None:
    """Entrypoint loads a callable main for the CLI."""
    assert callable(_load_main())


def test_python_dash_m_YuLabDataAllocator_is_supported(tmp_path: Path) -> None:
    """python -m YuLabDataAllocator is a supported alternate invocation."""
    roots = _prepare_env(tmp_path)
    proc = _run_module(["--help"], roots=roots)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "YuLabDataAllocator" in out


def test_console_script_invokes_same_cli_as_module(tmp_path: Path) -> None:
    """Console script YuLabDataAllocator runs the CLI (help lists fixed subcommands)."""
    roots = _prepare_env(tmp_path)
    proc = _run_console_script(["--help"], roots=roots)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    for name in ("allocate", "get", "delete", "ls"):
        assert name in out


def test_help_prog_is_YuLabDataAllocator(tmp_path: Path) -> None:
    """Help uses prog='YuLabDataAllocator'."""
    roots = _prepare_env(tmp_path)
    proc = _run_module(["--help"], roots=roots)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "YuLabDataAllocator" in out
    assert "YuLabDataAllocator.py" not in out


# --- fixed subcommand set / usage ---


def test_help_lists_fixed_subcommands(tmp_path: Path) -> None:
    """Subcommand set is fixed: allocate, get, delete, ls (not RC-driven)."""
    roots = _prepare_env(tmp_path)
    proc = _run_module(["--help"], roots=roots)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    for name in ("allocate", "get", "delete", "ls"):
        assert name in out


def test_no_subcommand_is_usage_exit_nonzero(tmp_path: Path) -> None:
    """No subcommand → argparse usage exit (nonzero)."""
    roots = _prepare_env(tmp_path)
    proc = _run_module([], roots=roots)
    assert proc.returncode != 0


def test_unknown_subcommand_is_usage_exit_nonzero(tmp_path: Path) -> None:
    """Unknown subcommand → argparse usage exit (nonzero)."""
    roots = _prepare_env(tmp_path)
    proc = _run_module(["not_a_command"], roots=roots)
    assert proc.returncode != 0


def test_allocate_help_lists_branch_name_positional(tmp_path: Path) -> None:
    """YuLabDataAllocator allocate --help documents the branch_name positional."""
    roots = _prepare_env(tmp_path)
    proc = _run_module(["allocate", "--help"], roots=roots)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "branch_name" in out or "branch" in out.lower()


def test_get_help_lists_branch_name_positional(tmp_path: Path) -> None:
    """YuLabDataAllocator get --help documents the branch_name positional."""
    roots = _prepare_env(tmp_path)
    proc = _run_module(["get", "--help"], roots=roots)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "branch_name" in out or "branch" in out.lower()


def test_delete_help_lists_branch_name_positional(tmp_path: Path) -> None:
    """YuLabDataAllocator delete --help documents the branch_name positional."""
    roots = _prepare_env(tmp_path)
    proc = _run_module(["delete", "--help"], roots=roots)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "branch_name" in out or "branch" in out.lower()


def test_ls_help_lists_root_and_short_tree_flags(tmp_path: Path) -> None:
    """YuLabDataAllocator ls --help lists --root and -s/--short_tree."""
    roots = _prepare_env(tmp_path)
    proc = _run_module(["ls", "--help"], roots=roots)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "--root" in out
    assert re.search(r"-s\b|--short_tree", out)
    assert "short_tree" in out or "-s" in out


def test_v1_has_no_config_or_db_override_flags(tmp_path: Path) -> None:
    """v1 has no global --config / --db overrides (SPEC005 paths only)."""
    roots = _prepare_env(tmp_path)
    proc = _run_module(["--help"], roots=roots)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "--config" not in out
    assert "--db" not in out


# --- allocate / get / delete stdout & behavior ---


def test_allocate_prints_single_path_line_and_creates_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """allocate success: stdout is exactly one filesystem path line + newline."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    code, stdout = _run_main_capture(
        ["allocate", "proj/run1"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0
    path = _assert_single_path_line(stdout)
    assert Path(path).is_dir()
    assert path.startswith(roots.drives["drive2"])


def test_allocate_passes_branch_name_separators_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abstract branch_name is passed through without rewriting separators."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    branch = "3-AD/0-raw"
    code, stdout = _run_main_capture(
        ["allocate", branch], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0
    path = _assert_single_path_line(stdout)
    assert branch in path or path.endswith(os.path.join(*branch.split("/")))
    assert "3-AD" in path and "0-raw" in path


def test_get_prints_single_path_line_for_existing_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get success: stdout is exactly one filesystem path line + newline."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    code, stdout = _run_main_capture(
        ["allocate", "a/b"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0
    allocated = _assert_single_path_line(stdout)

    code, stdout = _run_main_capture(
        ["get", "a/b"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0
    assert _assert_single_path_line(stdout) == allocated


def test_get_intermediate_prefix_not_resolvable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prefixes that appear only in ls (never allocated) are not resolvable via get."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    code, _ = _run_main_capture(
        ["allocate", "a/b/c"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0

    proc = _run_module(["get", "a"], roots=roots)
    assert proc.returncode != 0
    _assert_traceback(proc.stderr, proc.stdout)
    blob = (proc.stderr or "") + (proc.stdout or "")
    assert "BranchNotFoundError" in blob


def test_delete_success_is_silent_and_removes_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """delete success: no stdout requirement (silent OK); branch is gone afterward."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    code, stdout = _run_main_capture(
        ["allocate", "to/delete"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0
    allocated = _assert_single_path_line(stdout)
    assert Path(allocated).is_dir()

    code, stdout = _run_main_capture(
        ["delete", "to/delete"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0
    assert stdout.strip() == ""
    assert not Path(allocated).exists()

    proc = _run_module(["get", "to/delete"], roots=roots)
    assert proc.returncode != 0
    _assert_traceback(proc.stderr, proc.stdout)


def test_allocate_and_delete_do_not_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI does not prompt for confirmation (stdin closed / unused)."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    code, stdout = _run_main_capture(
        ["allocate", "no/prompt"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0
    assert _assert_single_path_line(stdout)

    # Subprocess with DEVNULL stdin must complete without hanging.
    proc = _run_module(["delete", "no/prompt"], roots=roots)
    assert proc.returncode == 0


# --- ls flags / stdout ---


def test_ls_writes_tree_with_trailing_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ls success: tree string to stdout; product ensures trailing newline when non-empty."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    for branch in ("proj/a", "proj/b", "other"):
        code, _ = _run_main_capture(
            ["allocate", branch], monkeypatch=monkeypatch, roots=roots
        )
        assert code == 0

    proc = _run_module(["ls"], roots=roots)
    assert proc.returncode == 0
    out = proc.stdout or ""
    assert out, "expected non-empty tree output"
    assert out.endswith("\n")
    assert "proj/a" in out or "proj" in out
    assert "other" in out


def test_ls_root_restricts_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ls --root ROOT restricts the tree to descendants of that abstract prefix."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    for branch in ("8-Reporter/x", "8-Reporter/y", "other/z"):
        code, _ = _run_main_capture(
            ["allocate", branch], monkeypatch=monkeypatch, roots=roots
        )
        assert code == 0

    proc = _run_module(["ls", "--root", "8-Reporter"], roots=roots)
    assert proc.returncode == 0
    out = proc.stdout or ""
    assert out.endswith("\n")
    assert "8-Reporter" in out
    assert "other" not in out


def test_ls_short_tree_flag_uses_basename_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ls -s / --short_tree prints basename-only node labels."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    code, _ = _run_main_capture(
        ["allocate", "proj/run"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0

    for flag in ("-s", "--short_tree"):
        proc = _run_module(["ls", flag], roots=roots)
        assert proc.returncode == 0, flag
        out = proc.stdout or ""
        assert out.endswith("\n"), flag
        assert "proj/run" not in out, flag
        assert "run" in out, flag


def test_ls_root_passed_through_without_separator_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ls --root abstract values are passed through without rewriting separators."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    code, _ = _run_main_capture(
        ["allocate", "9-NewProject/0-raw"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0

    proc = _run_module(["ls", "--root", "9-NewProject"], roots=roots)
    assert proc.returncode == 0
    out = proc.stdout or ""
    assert "9-NewProject" in out
    assert "0-raw" in out


def test_ls_does_not_require_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ls needs DB only — does not load drive config (matching legacy ls_root)."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    code, _ = _run_main_capture(
        ["allocate", "only/ls"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0

    # Remove config; ls must still succeed using the HOME DB alone.
    roots.config_path.unlink()
    proc = _run_module(["ls"], roots=roots)
    assert proc.returncode == 0
    assert (proc.stdout or "").endswith("\n")


# --- default SPEC005 path wiring ---


def test_allocate_uses_yuhome_config_and_home_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """allocate wires SPEC005 defaults: config under $YUHOME, DB under $HOME."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    code, stdout = _run_main_capture(
        ["allocate", "wired"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0
    path = _assert_single_path_line(stdout)
    assert Path(path).is_dir()
    assert roots.db_path.is_file(), "DB must be created at SPEC005 $HOME default path"
    assert roots.config_path.is_file()


def test_get_and_delete_require_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get / delete need config (SPEC005); missing config propagates a typed config error."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    code, _ = _run_main_capture(
        ["allocate", "need/cfg"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0

    roots.config_path.unlink()
    for cmd in ("get", "delete"):
        proc = _run_module([cmd, "need/cfg"], roots=roots)
        assert proc.returncode != 0, cmd
        _assert_traceback(proc.stderr, proc.stdout)
        blob = (proc.stderr or "") + (proc.stdout or "")
        assert "ConfigError" in blob or "ConfigFileError" in blob, cmd


# --- typed errors propagate (no catch-and-swallow) ---


def test_yuhome_unset_propagates_with_traceback(tmp_path: Path) -> None:
    """Config / YUHOME failures propagate typed errors (nonzero + traceback)."""
    roots = _prepare_env(tmp_path)
    env = _env_dict(roots)
    env.pop("YUHOME", None)
    proc = subprocess.run(
        [sys.executable, "-m", "YuLabDataAllocator", "allocate", "x"],
        capture_output=True,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,
    )
    assert proc.returncode != 0
    _assert_traceback(proc.stderr, proc.stdout)
    blob = (proc.stderr or "") + (proc.stdout or "")
    assert "YuhomeUnsetError" in blob or "ConfigError" in blob
    assert "YUHOME" in blob


def test_missing_get_propagates_branch_not_found_with_traceback(
    tmp_path: Path,
) -> None:
    """Missing get raises SPEC007 BranchNotFoundError; CLI does not catch-and-swallow."""
    roots = _prepare_env(tmp_path)
    proc = _run_module(["get", "never/allocated"], roots=roots)
    assert proc.returncode != 0
    _assert_traceback(proc.stderr, proc.stdout)
    blob = (proc.stderr or "") + (proc.stdout or "")
    assert "BranchNotFoundError" in blob


def test_duplicate_allocate_propagates_with_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Duplicate allocate raises DuplicateBranchError; CLI propagates with traceback."""
    roots = _prepare_env(tmp_path)
    _force_drive2_preferred(monkeypatch, roots.drives)
    code, _ = _run_main_capture(
        ["allocate", "dup"], monkeypatch=monkeypatch, roots=roots
    )
    assert code == 0

    proc = _run_module(["allocate", "dup"], roots=roots)
    assert proc.returncode != 0
    _assert_traceback(proc.stderr, proc.stdout)
    blob = (proc.stderr or "") + (proc.stdout or "")
    assert "DuplicateBranchError" in blob


def test_delete_missing_propagates_branch_not_found_with_traceback(
    tmp_path: Path,
) -> None:
    """delete on unknown branch propagates BranchNotFoundError (traceback OK)."""
    roots = _prepare_env(tmp_path)
    proc = _run_module(["delete", "missing/branch"], roots=roots)
    assert proc.returncode != 0
    _assert_traceback(proc.stderr, proc.stdout)
    blob = (proc.stderr or "") + (proc.stdout or "")
    assert "BranchNotFoundError" in blob


def test_cli_does_not_translate_domain_errors_to_soft_stderr_exit(
    tmp_path: Path,
) -> None:
    """CLI must not turn domain errors into soft stderr-only / no-traceback exits."""
    roots = _prepare_env(tmp_path)
    proc = _run_module(["get", "nope"], roots=roots)
    assert proc.returncode != 0
    # Soft swallow would print a bare [ERROR] line without a Python traceback.
    _assert_traceback(proc.stderr, proc.stdout)
    # Exact legacy [ERROR] string compatibility is not required.
