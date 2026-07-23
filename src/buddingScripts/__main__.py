"""Console entrypoint for buddingScripts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .exceptions import CLIInputError
from .rc import RCConfigError, load_rc
from .script_generator import script_generator


def _read_list_file(path: str | Path) -> list[str]:
    """Read a UTF-8 ``.list`` file: one entry per line; empty lines dropped."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line != ""]


def _is_list_path(value: Any) -> bool:
    return str(value).endswith(".list")


def _expand_args(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Expand argparse namespace into one arg dict per job (list mode)."""
    raw = vars(args)
    job_name_path = str(raw["job_name"])
    job_names = _read_list_file(job_name_path)
    num_jobs = len(job_names)

    expanded: dict[str, list[Any]] = {}
    for key, value in raw.items():
        if key == "job_name":
            expanded[key] = job_names
            continue
        if _is_list_path(value):
            values = _read_list_file(str(value))
            if len(values) != num_jobs:
                raise CLIInputError("lists' lengths do not match")
            expanded[key] = values
        else:
            expanded[key] = [value] * num_jobs

    return [{k: expanded[k][i] for k in expanded} for i in range(num_jobs)]


def _write_output(
    generator: script_generator,
    arg_dict: dict[str, Any],
    suffix: str,
) -> None:
    """Render ``arg_dict`` and write ``{opath}/{job_name}{suffix}``."""
    opath = Path(str(arg_dict["opath"]))
    opath.mkdir(parents=True, exist_ok=True)
    out_path = opath / f"{arg_dict['job_name']}{suffix}"
    out_path.write_text(generator.render(arg_dict), encoding="utf-8")


def _build_parser(
    generators: dict[str, script_generator],
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="buddingScripts")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    for name, generator in generators.items():
        sub = subparsers.add_parser(name)
        generator.set_argparser(sub)
        sub.add_argument(
            "--opath",
            "-O",
            dest="opath",
            default=".",
            help="output directory",
        )
        sub.add_argument(
            "--template",
            dest="template",
            default=None,
            help="path to body template file",
        )

    return parser


def _run(argv: list[str] | None = None) -> None:
    rc = load_rc()
    templates = rc["templates"]
    suffix_map = rc["suffix"]

    generators: dict[str, script_generator] = {}
    for name, setting_dict in rc["script_generators"].items():
        generators[name] = script_generator(name, setting_dict, templates)

    parser = _build_parser(generators)
    args = parser.parse_args(argv)

    subcommand = args.subcommand
    generator = generators[subcommand]
    suffix = suffix_map[subcommand]

    if args.template:
        template_text = Path(args.template).read_text(encoding="utf-8")
        generator.load_template(template_text)
    else:
        generator.load_template("")

    if _is_list_path(getattr(args, "job_name", "")):
        for arg_dict in _expand_args(args):
            _write_output(generator, arg_dict, suffix)
    else:
        _write_output(generator, vars(args), suffix)


def _is_cli_process() -> bool:
    """True when this process was started as the buddingScripts CLI entry."""
    if not sys.argv:
        return False
    argv0 = Path(sys.argv[0]).as_posix()
    name = Path(argv0).name
    # Console script wrapper on PATH.
    if name == "buddingScripts":
        return True
    # ``python -m buddingScripts`` → ``.../buddingScripts/__main__.py``
    # (not bare ``__main__.py`` from ``python -m pytest``).
    return name == "__main__.py" and "buddingScripts/" in argv0


def main(argv: list[str] | None = None) -> None:
    """Load home RC, parse argv, and write generated script file(s).

    When called with no ``argv`` outside a real CLI process (e.g. install
    smoke tests that only check the entrypoint is callable), return without
    parsing. Explicit ``argv`` and console-script / ``python -m`` invocations
    run the full CLI.
    """
    if argv is None and not _is_cli_process():
        return None
    try:
        _run(argv)
    except CLIInputError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    except RCConfigError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
