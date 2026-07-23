"""Indenting code block builder used by script rendering."""

from __future__ import annotations


class code_generator:
    """Ordered collection of indented lines and nested blocks."""

    def __init__(
        self, indent_level: int = 0, indent_str: str = "    "
    ) -> None:
        self.__contents: list[str | code_generator] = []
        self.indent_level = indent_level
        self.indent_str = indent_str

    def set_indent_level(self, indent_level: int) -> None:
        """Set the indentation level for subsequent lines."""
        self.indent_level = indent_level

    def add_indent_level(self) -> None:
        """Increase the current indentation level by 1."""
        self.indent_level += 1

    def decrease_indent_level(self) -> None:
        """Decrease the current indentation level by 1.

        Negative levels are allowed (legacy behavior): subsequent lines
        receive a negative multiple of ``indent_str``.
        """
        self.indent_level -= 1

    def add_line(self, text: str) -> None:
        """Append ``text`` prefixed by the current indent.

        Multi-line ``text`` is kept as a single content entry (no split).
        """
        self.__contents.append(self.indent_str * self.indent_level + text)

    def add_block(self) -> code_generator:
        """Append a child generator sharing current indent settings."""
        block = code_generator(
            indent_level=self.indent_level,
            indent_str=self.indent_str,
        )
        self.__contents.append(block)
        return block

    def __str__(self) -> str:
        return "\n".join(str(c) for c in self.__contents)
