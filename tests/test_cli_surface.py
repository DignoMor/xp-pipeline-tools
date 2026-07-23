"""Console CLI surface for buddingScripts (SPEC003 slice).

Encodes home-RC load at start, RC-driven subcommands, shared --template /
--opath/-O, single vs .list expansion on job_name, mkdir-parents for opath,
{job_name}{suffix} writes, and python -m / console-script entrypoints.

Locked picks: empty .list lines dropped; expansion only when job_name ends
with .list; CLIInputError prefix "CLI input Error: …"; nonzero exit without
traceback for CLIInputError and RC config errors.

Out of scope: SPEC002 schema field definitions, SPEC004 class APIs, sbatch,
pipeline finish-line text.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pytest


# --- helpers (public entrypoints only; no private src imports) ---


def _console_script_entry_points():
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


def _load_main() -> Callable:
    """Public CLI main via console-script entrypoint."""
    main = _budding_scripts_entrypoint().load()
    assert callable(main)
    return main


def _minimal_cli_rc() -> dict[str, Any]:
    """Minimal valid home RC with two generators for subcommand / suffix checks."""
    return {
        "script_generators": {
            "bash": {
                "variables": {
                    "job_name": {
                        "default": "job",
                        "flag": "-j",
                        "help": "job name",
                    },
                    "header1": {
                        "default": "",
                        "flag": "--h1",
                        "help": "header placeholder value",
                    },
                },
                "setting_str": {
                    "#!/bin/bash": "job_name",
                },
            },
            "slurm": {
                "variables": {
                    "job_name": {
                        "default": "job",
                        "flag": "-j",
                        "help": "job name",
                    },
                    "num_cores": {
                        "default": 1,
                        "flag": "-c",
                        "help": "cores",
                    },
                },
                "setting_str": {
                    "#!/bin/bash": "job_name",
                },
            },
        },
        "templates": {
            "#header1#": "header1",
        },
        "suffix": {
            "bash": ".sh",
            "slurm": ".slurm",
        },
    }


def _write_home_rc(home: Path, payload: dict[str, Any] | None = None) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    path = home / ".buddingScriptsRC.json"
    path.write_text(json.dumps(payload if payload is not None else _minimal_cli_rc()), encoding="utf-8")
    return path


def _write_list(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def _run_module(argv: list[str], *, home: Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Invoke `python -m buddingScripts` with a temp HOME (and optional cwd)."""
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run(
        [sys.executable, "-m", "buddingScripts", *argv],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd) if cwd is not None else None,
    )


def _run_main_inprocess(
    argv: list[str],
    *,
    monkeypatch: pytest.MonkeyPatch,
    home: Path,
) -> tuple[int | None, str]:
    """Call public main() with sys.argv; return (exit_code, combined capture note).

    Exit code is 0 / None on success, or SystemExit.code. Does not capture
    printed stderr (use subprocess helpers for traceback checks).
    """
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(sys, "argv", ["buddingScripts", *argv])
    main = _load_main()
    try:
        result = main()
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0, "SystemExit(None)"
        if isinstance(code, int):
            return code, f"SystemExit({code})"
        return 1, f"SystemExit({code!r})"
    if result in (0, None):
        return 0, "ok"
    return int(result), f"return:{result!r}"


def _assert_no_traceback(stderr: str, stdout: str = "") -> None:
    blob = (stderr or "") + (stdout or "")
    assert "Traceback (most recent call last)" not in blob
    assert "Traceback" not in blob


# --- entrypoints ---


def test_python_dash_m_buddingScripts_is_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """python -m buddingScripts is a supported alternate invocation."""
    home = tmp_path / "home"
    _write_home_rc(home)
    # --help should exit 0 and mention the prog / subcommands without needing a job.
    proc = _run_module(["--help"], home=home)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "buddingScripts" in out
    assert "bash" in out
    assert "slurm" in out


def test_console_script_invokes_same_cli_as_module(tmp_path: Path) -> None:
    """Console script buddingScripts runs the CLI (help lists RC subcommands)."""
    home = tmp_path / "home"
    _write_home_rc(home)
    env = {**os.environ, "HOME": str(home)}
    # Prefer the installed console script on PATH; fall back to entry-point load.
    script = "buddingScripts"
    which = subprocess.run(["which", script], capture_output=True, text=True, env=env)
    if which.returncode == 0 and which.stdout.strip():
        proc = subprocess.run(
            [which.stdout.strip(), "--help"],
            capture_output=True,
            text=True,
            env=env,
        )
    else:
        # entry_point load + in-process help via module still proves registration;
        # exercise argv through python -m as the alternate public surface.
        proc = _run_module(["--help"], home=home)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "bash" in out and "slurm" in out
    assert callable(_load_main())


# --- home RC at start / RC-driven subcommands ---


def test_cli_loads_home_rc_at_start_and_builds_subcommands(tmp_path: Path) -> None:
    """Subcommand set ≡ keys of script_generators from ${HOME}/.buddingScriptsRC.json."""
    home = tmp_path / "home"
    payload = _minimal_cli_rc()
    # Rename generators to prove RC drives the surface, not hard-coded names.
    payload["script_generators"] = {
        "alphaGen": payload["script_generators"]["bash"],
        "betaGen": payload["script_generators"]["slurm"],
    }
    payload["suffix"] = {"alphaGen": ".sh", "betaGen": ".slurm"}
    _write_home_rc(home, payload)
    proc = _run_module(["--help"], home=home)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert "alphaGen" in out
    assert "betaGen" in out
    # Subcommand choices come from this RC only (not the default bash/slurm names).
    assert re.search(r"\{[^}]*alphaGen[^}]*betaGen[^}]*\}", out) or (
        "alphaGen" in out and "betaGen" in out and "slurm" not in out
    )


def test_missing_home_rc_fails_before_parse_nonzero_no_traceback(tmp_path: Path) -> None:
    """RC load failure (missing home RC) aborts before parse: nonzero, no traceback."""
    home = tmp_path / "empty_home"
    home.mkdir()
    assert not (home / ".buddingScriptsRC.json").exists()
    proc = _run_module(["bash", "--job_name", "x"], home=home)
    assert proc.returncode != 0
    _assert_no_traceback(proc.stderr, proc.stdout)


def test_invalid_home_rc_fails_before_parse_nonzero_no_traceback(tmp_path: Path) -> None:
    """Invalid home RC JSON/config aborts before parse: nonzero, no traceback."""
    home = tmp_path / "home"
    home.mkdir()
    (home / ".buddingScriptsRC.json").write_text("{ not json", encoding="utf-8")
    proc = _run_module(["--help"], home=home)
    assert proc.returncode != 0
    _assert_no_traceback(proc.stderr, proc.stdout)


def test_no_subcommand_is_usage_exit_not_keyerror(tmp_path: Path) -> None:
    """No subcommand → argparse/usage exit, not a raw KeyError."""
    home = tmp_path / "home"
    _write_home_rc(home)
    proc = _run_module([], home=home)
    assert proc.returncode != 0
    blob = (proc.stdout or "") + (proc.stderr or "")
    assert "KeyError" not in blob
    _assert_no_traceback(proc.stderr, proc.stdout)


def test_unknown_subcommand_is_usage_exit_not_keyerror(tmp_path: Path) -> None:
    """Unknown subcommand → argparse/usage exit, not a raw KeyError."""
    home = tmp_path / "home"
    _write_home_rc(home)
    proc = _run_module(["not_a_generator"], home=home)
    assert proc.returncode != 0
    blob = (proc.stdout or "") + (proc.stderr or "")
    assert "KeyError" not in blob
    _assert_no_traceback(proc.stderr, proc.stdout)


# --- shared flags / help ---


def test_subcommand_help_includes_template_and_opath(tmp_path: Path) -> None:
    """buddingScripts <subcommand> --help lists shared --template and --opath/-O."""
    home = tmp_path / "home"
    _write_home_rc(home)
    proc = _run_module(["bash", "--help"], home=home)
    assert proc.returncode == 0
    out = (proc.stdout or "") + (proc.stderr or "")
    assert re.search(r"--template", out)
    assert re.search(r"--opath|-O", out)
    # Generator flag from RC variables also appears.
    assert "--job_name" in out or "-j" in out


# --- single mode / output path ---


def test_single_mode_writes_job_name_plus_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Single mode writes {opath}/{job_name}{suffix[subcommand]}."""
    home = tmp_path / "home"
    _write_home_rc(home)
    work = tmp_path / "work"
    work.mkdir()
    opath = work / "out"
    code, _ = _run_main_inprocess(
        ["bash", "--job_name", "myjob", "-O", str(opath)],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    assert (opath / "myjob.sh").is_file()
    assert not (opath / "myjob.slurm").exists()


def test_single_mode_slurm_uses_slurm_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Suffix comes from RC suffix map for the chosen subcommand."""
    home = tmp_path / "home"
    _write_home_rc(home)
    opath = tmp_path / "out"
    code, _ = _run_main_inprocess(
        ["slurm", "--job_name", "sjob", "-O", str(opath)],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    assert (opath / "sjob.slurm").is_file()


def test_opath_default_is_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--opath / -O defaults to '.' (write under cwd when omitted)."""
    home = tmp_path / "home"
    _write_home_rc(home)
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    code, _ = _run_main_inprocess(
        ["bash", "--job_name", "here"],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    assert (work / "here.sh").is_file()


def test_opath_mkdir_parents_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Port creates opath (mkdir parents) when the output directory is missing."""
    home = tmp_path / "home"
    _write_home_rc(home)
    opath = tmp_path / "deep" / "nested" / "out"
    assert not opath.exists()
    code, _ = _run_main_inprocess(
        ["bash", "--job_name", "nested", "-O", str(opath)],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    assert (opath / "nested.sh").is_file()


def test_opath_does_not_delete_sibling_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writing into opath must not delete other files already present."""
    home = tmp_path / "home"
    _write_home_rc(home)
    opath = tmp_path / "out"
    opath.mkdir()
    sibling = opath / "keep_me.txt"
    sibling.write_text("preserve", encoding="utf-8")
    code, _ = _run_main_inprocess(
        ["bash", "--job_name", "newjob", "-O", str(opath)],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    assert (opath / "newjob.sh").is_file()
    assert sibling.read_text(encoding="utf-8") == "preserve"


def test_output_file_is_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Create/overwrite the target file on repeat runs."""
    home = tmp_path / "home"
    _write_home_rc(home)
    opath = tmp_path / "out"
    opath.mkdir()
    target = opath / "job.sh"
    target.write_text("OLD", encoding="utf-8")
    code, _ = _run_main_inprocess(
        ["bash", "--job_name", "job", "-O", str(opath)],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    assert target.is_file()
    assert target.read_text(encoding="utf-8") != "OLD"


def test_template_flag_reads_body_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When --template is set, the template file is read as the body source."""
    home = tmp_path / "home"
    _write_home_rc(home)
    opath = tmp_path / "out"
    template = tmp_path / "body.template.sh"
    marker = "UNIQUE_TEMPLATE_BODY_MARKER_42"
    template.write_text(f"echo {marker}\n", encoding="utf-8")
    code, _ = _run_main_inprocess(
        [
            "bash",
            "--job_name",
            "tjob",
            "--template",
            str(template),
            "-O",
            str(opath),
        ],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    written = (opath / "tjob.sh").read_text(encoding="utf-8")
    assert marker in written


def test_template_unset_still_writes_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When --template is unset, CLI still writes the output file (empty body)."""
    home = tmp_path / "home"
    _write_home_rc(home)
    opath = tmp_path / "out"
    code, _ = _run_main_inprocess(
        ["bash", "--job_name", "nobody", "-O", str(opath)],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    assert (opath / "nobody.sh").is_file()


def test_unreadable_template_raises_os_error(tmp_path: Path) -> None:
    """Template path set but unreadable → standard OS/IO error with path."""
    home = tmp_path / "home"
    _write_home_rc(home)
    missing = tmp_path / "no_such_template.sh"
    assert not missing.exists()
    proc = _run_module(
        ["bash", "--job_name", "x", "--template", str(missing), "-O", str(tmp_path / "o")],
        home=home,
    )
    assert proc.returncode != 0
    blob = (proc.stdout or "") + (proc.stderr or "")
    assert str(missing) in blob or missing.name in blob


# --- expansion (.list) mode ---


def test_expansion_when_job_name_endswith_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expansion is selected when the string form of job_name ends with .list."""
    home = tmp_path / "home"
    _write_home_rc(home)
    lists = tmp_path / "lists"
    job_list = _write_list(lists / "jobs.list", ["alpha", "beta"])
    opath = tmp_path / "out"
    code, _ = _run_main_inprocess(
        ["bash", "--job_name", str(job_list), "-O", str(opath)],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    assert (opath / "alpha.sh").is_file()
    assert (opath / "beta.sh").is_file()
    # Must not write a single file literally named after the list path stem+suffix oddly;
    # each job_name line gets its own file.
    assert not (opath / "jobs.sh").exists()


def test_list_detection_is_suffix_based_not_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """.list detection is endswith('.list') on the argument string, not file content."""
    home = tmp_path / "home"
    _write_home_rc(home)
    opath = tmp_path / "out"
    # job_name does not end with .list → single mode even if value looks like a path.
    code, _ = _run_main_inprocess(
        ["bash", "--job_name", "not_a_list_file", "-O", str(opath)],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    assert (opath / "not_a_list_file.sh").is_file()


def test_expansion_only_if_job_name_ends_with_list_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Locked: expansion only when job_name ends with .list (not other .list flags alone)."""
    home = tmp_path / "home"
    _write_home_rc(home)
    lists = tmp_path / "lists"
    header_list = _write_list(lists / "headers.list", ["h1", "h2"])
    opath = tmp_path / "out"
    # Scalar job_name; header1 ends with .list → still single mode (one output file).
    code, _ = _run_main_inprocess(
        [
            "bash",
            "--job_name",
            "scalar_job",
            "--header1",
            str(header_list),
            "-O",
            str(opath),
        ],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    assert (opath / "scalar_job.sh").is_file()
    assert not (opath / "h1.sh").exists()
    assert not (opath / "h2.sh").exists()


def test_empty_list_lines_are_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Locked: empty lines in .list files are dropped (not kept, not errors)."""
    home = tmp_path / "home"
    _write_home_rc(home)
    lists = tmp_path / "lists"
    job_list = lists / "jobs.list"
    job_list.parent.mkdir(parents=True, exist_ok=True)
    job_list.write_text("one\n\n\ntwo\n\n", encoding="utf-8")
    opath = tmp_path / "out"
    code, _ = _run_main_inprocess(
        ["bash", "--job_name", str(job_list), "-O", str(opath)],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    assert (opath / "one.sh").is_file()
    assert (opath / "two.sh").is_file()
    written = sorted(p.name for p in opath.iterdir() if p.is_file())
    assert written == ["one.sh", "two.sh"]


def test_parallel_list_flags_must_match_job_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Other .list argparse values must have the same length as job_name list."""
    home = tmp_path / "home"
    _write_home_rc(home)
    lists = tmp_path / "lists"
    job_list = _write_list(lists / "jobs.list", ["a", "b"])
    header_list = _write_list(lists / "headers.list", ["h1", "h2"])
    opath = tmp_path / "out"
    code, _ = _run_main_inprocess(
        [
            "bash",
            "--job_name",
            str(job_list),
            "--header1",
            str(header_list),
            "-O",
            str(opath),
        ],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    assert (opath / "a.sh").is_file()
    assert (opath / "b.sh").is_file()


def test_list_length_mismatch_is_cli_input_error_nonzero_no_traceback(
    tmp_path: Path,
) -> None:
    """Disagreeing .list lengths → CLIInputError; CLI exits nonzero without traceback."""
    home = tmp_path / "home"
    _write_home_rc(home)
    lists = tmp_path / "lists"
    job_list = _write_list(lists / "jobs.list", ["a", "b"])
    header_list = _write_list(lists / "headers.list", ["only_one"])
    proc = _run_module(
        [
            "bash",
            "--job_name",
            str(job_list),
            "--header1",
            str(header_list),
            "-O",
            str(tmp_path / "out"),
        ],
        home=home,
    )
    assert proc.returncode != 0
    _assert_no_traceback(proc.stderr, proc.stdout)
    blob = (proc.stdout or "") + (proc.stderr or "")
    assert "CLI input Error:" in blob
    # Message indicates list lengths do not match.
    assert re.search(r"length|lengths|match", blob, re.IGNORECASE)


def test_scalars_and_opath_broadcast_across_expanded_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-.list values (including opath) broadcast to every expanded job."""
    home = tmp_path / "home"
    _write_home_rc(home)
    lists = tmp_path / "lists"
    job_list = _write_list(lists / "jobs.list", ["j1", "j2", "j3"])
    opath = tmp_path / "shared_out"
    template = tmp_path / "body.template.sh"
    template.write_text("BODY\n", encoding="utf-8")
    code, _ = _run_main_inprocess(
        [
            "bash",
            "--job_name",
            str(job_list),
            "--header1",
            "same_header",
            "--template",
            str(template),
            "-O",
            str(opath),
        ],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    for name in ("j1", "j2", "j3"):
        path = opath / f"{name}.sh"
        assert path.is_file()
        assert "BODY" in path.read_text(encoding="utf-8")


def test_each_expanded_job_writes_exactly_one_output_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every expanded job writes exactly one output file named job_name + suffix."""
    home = tmp_path / "home"
    _write_home_rc(home)
    lists = tmp_path / "lists"
    names = ["x", "y", "z"]
    job_list = _write_list(lists / "jobs.list", names)
    opath = tmp_path / "out"
    code, _ = _run_main_inprocess(
        ["slurm", "--job_name", str(job_list), "-O", str(opath)],
        monkeypatch=monkeypatch,
        home=home,
    )
    assert code == 0
    files = sorted(p.name for p in opath.iterdir() if p.is_file())
    assert files == [f"{n}.slurm" for n in names]
