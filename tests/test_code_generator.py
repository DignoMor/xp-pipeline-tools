"""code_generator library API (SPEC004 slice).

Encodes construction, indent helpers, add_line/add_block, str joining,
multi-line add_line (no split), negative indent (legacy allow), and omission
of replace. Snake_case class name preserved.
"""

from __future__ import annotations

import importlib


def _code_generator():
    """code_generator must be importable without going through the CLI."""
    pkg = importlib.import_module("buddingScripts")
    return pkg.code_generator


def test_code_generator_is_snake_case_class() -> None:
    """Public class keeps legacy snake_case name code_generator."""
    cg = _code_generator()
    assert cg.__name__ == "code_generator"


def test_code_generator_constructor_defaults() -> None:
    """Constructor defaults: indent_level=0, indent_str four spaces."""
    code_generator = _code_generator()
    gen = code_generator()
    gen.add_line("x")
    assert str(gen) == "x"
    gen2 = code_generator(indent_level=2, indent_str="\t")
    gen2.add_line("y")
    assert str(gen2) == "\t\ty"


def test_add_line_applies_current_indent() -> None:
    """add_line(text) appends indent_str * indent_level + text."""
    code_generator = _code_generator()
    gen = code_generator(indent_level=1, indent_str="  ")
    gen.add_line("a")
    gen.add_line("b")
    assert str(gen) == "  a\n  b"


def test_set_add_decrease_indent_affect_subsequent_lines_only() -> None:
    """Indent helpers affect subsequent add_line calls on that generator only."""
    code_generator = _code_generator()
    gen = code_generator(indent_str="    ")
    gen.add_line("zero")
    gen.add_indent_level()
    gen.add_line("one")
    gen.set_indent_level(2)
    gen.add_line("two")
    gen.decrease_indent_level()
    gen.add_line("back")
    assert str(gen) == "zero\n    one\n        two\n    back"


def test_add_block_shares_indent_settings_and_nests_in_str() -> None:
    """add_block appends a child sharing indent settings; str is recursive."""
    code_generator = _code_generator()
    root = code_generator(indent_level=1, indent_str="..")
    root.add_line("root")
    child = root.add_block()
    assert child is not root
    child.add_line("child")
    child.add_indent_level()
    child.add_line("deeper")
    # Child started at indent_level=1; after add_indent_level, deeper is 2.
    assert str(root) == "..root\n..child\n....deeper"
    # Parent indent unchanged by child's add_indent_level.
    root.add_line("root-again")
    assert str(root).endswith("\n..root-again")


def test_str_joins_contents_with_newline_deterministically() -> None:
    """str(code_generator) joins contents with \\n; same order → same result."""
    code_generator = _code_generator()
    a = code_generator()
    a.add_line("1")
    a.add_line("2")
    b = code_generator()
    b.add_line("1")
    b.add_line("2")
    assert str(a) == str(b) == "1\n2"


def test_add_line_multiline_does_not_split() -> None:
    """Multi-line add_line keeps one content entry; no per-line indent split."""
    code_generator = _code_generator()
    gen = code_generator(indent_level=1, indent_str="    ")
    gen.add_line("first\nsecond\nthird")
    text = str(gen)
    # Indent applied once at the start of the whole entry, not each line.
    assert text == "    first\nsecond\nthird"
    assert text.count("    ") == 1


def test_decrease_indent_below_zero_allowed() -> None:
    """decrease_indent_level below 0 is allowed (legacy; negative indent ok)."""
    code_generator = _code_generator()
    gen = code_generator(indent_level=0, indent_str="    ")
    gen.decrease_indent_level()
    # Must not raise; subsequent add_line uses indent_str * negative level.
    gen.add_line("neg")
    assert str(gen) == ("    " * -1) + "neg"


def test_code_generator_omits_replace() -> None:
    """Public surface omits code_generator.replace (legacy replace is buggy)."""
    code_generator = _code_generator()
    gen = code_generator()
    assert not hasattr(gen, "replace")
    assert not hasattr(code_generator, "replace")
