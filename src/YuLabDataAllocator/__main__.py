"""Console entrypoint for YuLabDataAllocator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .allocator import Allocator
from .paths import default_config_path, default_db_path
from .storage_manager import StorageManager
from .tree_visualizer import TreeVisualizer


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="YuLabDataAllocator")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    allocate = subparsers.add_parser("allocate")
    allocate.add_argument("branch_name")

    get_cmd = subparsers.add_parser("get")
    get_cmd.add_argument("branch_name")

    delete = subparsers.add_parser("delete")
    delete.add_argument("branch_name")

    ls = subparsers.add_parser("ls")
    ls.add_argument(
        "--root",
        dest="root",
        default="",
        help="restrict tree to descendants of this abstract prefix",
    )
    ls.add_argument(
        "-s",
        "--short_tree",
        dest="short_tree",
        action="store_true",
        default=False,
        help="print basename-only node labels",
    )

    return parser


def _ensure_trailing_newline(text: str) -> str:
    """Ensure non-empty ``text`` ends with a single trailing newline."""
    if text and not text.endswith("\n"):
        return text + "\n"
    return text


def _run(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "ls":
        storage = StorageManager(default_db_path())
        visualizer = TreeVisualizer(storage)
        tree = visualizer.build_tree(args.root)
        out = visualizer.tree2str(tree, short_tree=args.short_tree)
        sys.stdout.write(_ensure_trailing_newline(out))
        return

    allocator = Allocator(default_config_path(), default_db_path())

    if args.subcommand == "allocate":
        path = allocator.allocate(args.branch_name)
        sys.stdout.write(f"{path}\n")
    elif args.subcommand == "get":
        path = allocator.get_path(args.branch_name)
        sys.stdout.write(f"{path}\n")
    elif args.subcommand == "delete":
        allocator.delete_branch(args.branch_name)


def _is_cli_process() -> bool:
    """True when this process was started as the YuLabDataAllocator CLI entry."""
    if not sys.argv:
        return False
    argv0 = Path(sys.argv[0]).as_posix()
    name = Path(argv0).name
    # Console script wrapper on PATH.
    if name == "YuLabDataAllocator":
        return True
    # ``python -m YuLabDataAllocator`` → ``.../YuLabDataAllocator/__main__.py``
    return name == "__main__.py" and "YuLabDataAllocator/" in argv0


def main(argv: list[str] | None = None) -> None:
    """Parse argv and dispatch allocate / get / delete / ls.

    When called with no ``argv`` outside a real CLI process (e.g. install
    smoke tests that only check the entrypoint is callable), return without
    parsing. Explicit ``argv`` and console-script / ``python -m`` invocations
    run the full CLI.

    Domain and config errors from the library propagate uncaught.
    """
    if argv is None and not _is_cli_process():
        return None
    _run(argv)


if __name__ == "__main__":
    main()
