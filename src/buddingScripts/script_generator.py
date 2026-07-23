"""RC-driven script generator settings and render path."""

from __future__ import annotations

import argparse
from typing import Any

from .code_generator import code_generator


class script_generator_settings:
    """Per-generator variables and header line templates from RC."""

    def __init__(self, engine_name: str) -> None:
        self.engine_name = engine_name
        self.__keys: list[str] = []
        self.__setting_strs: dict[str, str] = {}
        self.__defaults: dict[str, Any] = {}
        self.__flags: dict[str, str] = {}
        self.__helps: dict[str, str] = {}

    def add_setting_key(
        self, key: str, default: Any, flag: str, help_str: str
    ) -> None:
        """Register one variable option."""
        self.__keys.append(key)
        self.__defaults[key] = default
        self.__flags[key] = flag
        self.__helps[key] = help_str

    def load_variables_from_dict(self, variables_obj: dict[str, Any]) -> None:
        """Load SPEC002 ``variables`` map into this settings object."""
        for key, value in variables_obj.items():
            self.add_setting_key(
                key, value["default"], value["flag"], value["help"]
            )

    def load_setting_strs_from_dict(
        self, setting_str_obj: dict[str, str]
    ) -> None:
        """Load SPEC002 ``setting_str`` map (line template → option name)."""
        for line_template, option_name in setting_str_obj.items():
            self.__setting_strs[line_template] = option_name

    def get_keys(self) -> list[str]:
        """Return variable option names in load order."""
        return self.__keys

    def get_default(self, key: str) -> Any:
        """Return the default value for ``key``."""
        return self.__defaults[key]

    def get_flag(self, key: str) -> str:
        """Return the short/alternate argparse flag for ``key``."""
        return self.__flags[key]

    def get_help(self, key: str) -> str:
        """Return the argparse help text for ``key``."""
        return self.__helps[key]

    def get_setting_strs(self) -> list[str]:
        """Return header line templates in load order."""
        return list(self.__setting_strs.keys())

    def get_key_for_setting_str(self, line_template: str) -> str:
        """Return the option name for a header line template."""
        return self.__setting_strs[line_template]


class script_generator:
    """Turn one generator's RC + arg dict into rendered script text."""

    def __init__(
        self,
        name: str,
        setting_dict: dict[str, Any],
        sub_dict: dict[str, str],
    ) -> None:
        self.__settings = script_generator_settings(name)
        self.load_setting_from_dict(setting_dict)
        self.template = ""
        self.template_substitution_dict = sub_dict

    def load_setting_from_dict(self, setting_dict: dict[str, Any]) -> None:
        """Load ``variables`` and ``setting_str`` from a generator RC object."""
        self.__settings.load_variables_from_dict(setting_dict["variables"])
        self.__settings.load_setting_strs_from_dict(setting_dict["setting_str"])

    def load_template(self, text: str) -> None:
        """Set the body template string (default empty)."""
        self.template = text

    def set_argparser(self, parser: argparse.ArgumentParser) -> None:
        """Register per-variable and template dest flags on ``parser``.

        Template dests that already match a variable option name are skipped so
        ``--<dest>`` is not registered twice (RC may expose the same name as
        both a ``variables`` key and a ``templates`` dest).
        """
        variable_keys = set(self.__settings.get_keys())
        for key in self.__settings.get_keys():
            parser.add_argument(
                "--" + key,
                self.__settings.get_flag(key),
                help=self.__settings.get_help(key),
                dest=key,
                default=self.__settings.get_default(key),
            )

        for placeholder, dest in self.template_substitution_dict.items():
            if dest in variable_keys:
                continue
            parser.add_argument(
                "--" + dest,
                help="contents to substitute " + str(placeholder),
            )

    def render(self, arg_dict: dict[str, Any]) -> str:
        """Render full script text from ``arg_dict``.

        Missing keys for referenced options/placeholders raise ``KeyError``.
        """
        root = code_generator()
        header = root.add_block()
        root.add_line("")
        body = root.add_block()

        for line_template in self.__settings.get_setting_strs():
            option_name = self.__settings.get_key_for_setting_str(line_template)
            header.add_line(
                line_template.replace("<setting>", str(arg_dict[option_name]))
            )

        template = self.template
        for placeholder, dest in self.template_substitution_dict.items():
            template = template.replace(placeholder, str(arg_dict[dest]))

        body.add_line(template)
        return str(root)
