"""script_generator / settings library API (SPEC004 slice).

Encodes script_generator_settings accessors, script_generator construction,
load_template, set_argparser, and render (header/body, <setting>, templates,
KeyError, multi-line body). Snake_case names preserved. No SPEC002 RC files
or SPEC003 CLI argv / .list I/O.
"""

from __future__ import annotations

import argparse
import importlib

import pytest


def _import_script_api():
    """Settings and generator must be importable without the CLI."""
    pkg = importlib.import_module("buddingScripts")
    return pkg.script_generator_settings, pkg.script_generator


def _minimal_setting_dict():
    """Minimal script_generators.<name> object: variables + setting_str."""
    return {
        "variables": {
            "job_name": {
                "default": "job",
                "flag": "-j",
                "help": "job name",
            },
            "threads": {
                "default": 1,
                "flag": "-t",
                "help": "thread count",
            },
        },
        "setting_str": {
            "#SBATCH --job-name=<setting>": "job_name",
            "#SBATCH --cpus-per-task=<setting>": "threads",
        },
    }


def _minimal_templates():
    """RC templates map: placeholder → dest option name."""
    return {
        "#BODY#": "body_text",
        "#OUT#": "outfile",
    }


# --- script_generator_settings ---


def test_script_generator_settings_snake_case_name() -> None:
    """Public class keeps legacy snake_case name script_generator_settings."""
    script_generator_settings, _ = _import_script_api()
    assert script_generator_settings.__name__ == "script_generator_settings"


def test_settings_constructor_and_load_variables() -> None:
    """Constructor takes engine_name; load_variables_from_dict fills accessors."""
    script_generator_settings, _ = _import_script_api()
    settings = script_generator_settings("engineA")
    settings.load_variables_from_dict(
        {
            "alpha": {"default": "A", "flag": "-a", "help": "alpha help"},
            "beta": {"default": 2, "flag": "-b", "help": "beta help"},
        }
    )
    assert settings.get_keys() == ["alpha", "beta"]
    assert settings.get_default("alpha") == "A"
    assert settings.get_default("beta") == 2
    assert settings.get_flag("alpha") == "-a"
    assert settings.get_flag("beta") == "-b"
    assert settings.get_help("alpha") == "alpha help"
    assert settings.get_help("beta") == "beta help"


def test_settings_load_setting_strs_preserves_order_and_lookup() -> None:
    """setting_str is line template → option name; get_setting_strs is load order."""
    script_generator_settings, _ = _import_script_api()
    settings = script_generator_settings("engineB")
    settings.load_setting_strs_from_dict(
        {
            "line-one: <setting>": "opt_one",
            "line-two: <setting>": "opt_two",
        }
    )
    assert settings.get_setting_strs() == [
        "line-one: <setting>",
        "line-two: <setting>",
    ]
    assert settings.get_key_for_setting_str("line-one: <setting>") == "opt_one"
    assert settings.get_key_for_setting_str("line-two: <setting>") == "opt_two"


# --- script_generator ---


def test_script_generator_snake_case_name() -> None:
    """Public class keeps legacy snake_case name script_generator."""
    _, script_generator = _import_script_api()
    assert script_generator.__name__ == "script_generator"


def test_script_generator_load_template_default_empty() -> None:
    """load_template sets body template; default template is empty."""
    _, script_generator = _import_script_api()
    setting_dict = {
        "variables": {
            "n": {"default": "n", "flag": "-n", "help": "n"},
        },
        "setting_str": {
            "H=<setting>": "n",
        },
    }
    gen = script_generator("demo", setting_dict, {})
    # Default empty body → header, blank line, empty body entry.
    assert gen.render({"n": "v"}) == "H=v\n\n"
    gen.load_template("hello")
    assert gen.render({"n": "v"}) == "H=v\n\nhello"


def test_set_argparser_registers_variable_and_template_options() -> None:
    """set_argparser adds --<key>+short for variables; --<dest> for templates."""
    _, script_generator = _import_script_api()
    gen = script_generator("demo", _minimal_setting_dict(), _minimal_templates())
    parser = argparse.ArgumentParser(prog="test")
    gen.set_argparser(parser)

    help_text = parser.format_help()
    assert "--job_name" in help_text
    assert "-j" in help_text
    assert "--threads" in help_text
    assert "-t" in help_text

    # Template dests: long options only (no short flags required by SPEC).
    assert "--body_text" in help_text
    assert "--outfile" in help_text

    ns = parser.parse_args([])
    assert ns.job_name == "job"
    assert ns.threads == 1


def test_render_header_body_algorithm() -> None:
    """render: header setting_str lines, blank line, then substituted body."""
    _, script_generator = _import_script_api()
    gen = script_generator("demo", _minimal_setting_dict(), _minimal_templates())
    gen.load_template("run #BODY# > #OUT#")
    result = gen.render(
        {
            "job_name": "demoJob",
            "threads": 8,
            "body_text": "cmd",
            "outfile": "out.txt",
        }
    )
    expected = (
        "#SBATCH --job-name=demoJob\n"
        "#SBATCH --cpus-per-task=8\n"
        "\n"
        "run cmd > out.txt"
    )
    assert result == expected


def test_render_uses_setting_token_not_header_placeholders() -> None:
    """Header injection uses only the <setting> token inside setting_str keys."""
    _, script_generator = _import_script_api()
    setting_dict = {
        "variables": {
            "x": {"default": "v", "flag": "-x", "help": "x"},
        },
        "setting_str": {
            "prefix-<setting>-suffix": "x",
        },
    }
    gen = script_generator("tok", setting_dict, {})
    gen.load_template("body")
    result = gen.render({"x": "VAL"})
    assert result == "prefix-VAL-suffix\n\nbody"
    assert "#header" not in result


def test_render_body_substitution_uses_templates_map_only() -> None:
    """Body substitution uses only the RC templates map (placeholder → dest)."""
    _, script_generator = _import_script_api()
    setting_dict = {
        "variables": {
            "opt": {"default": "o", "flag": "-o", "help": "opt"},
        },
        "setting_str": {
            "H=<setting>": "opt",
        },
    }
    templates = {"{{A}}": "a_dest", "{{B}}": "b_dest"}
    gen = script_generator("t", setting_dict, templates)
    gen.load_template("A={{A}} B={{B}}")
    result = gen.render({"opt": "1", "a_dest": "aa", "b_dest": "bb"})
    assert result == "H=1\n\nA=aa B=bb"


def test_render_multiline_body_preserved_as_single_add_line() -> None:
    """Substituted body may contain newlines; add_line does not split them."""
    _, script_generator = _import_script_api()
    setting_dict = {
        "variables": {
            "n": {"default": "n", "flag": "-n", "help": "n"},
        },
        "setting_str": {
            "name=<setting>": "n",
        },
    }
    templates = {"#BLOCK#": "block"}
    gen = script_generator("ml", setting_dict, templates)
    gen.load_template("line1\n#BLOCK#\nline3")
    result = gen.render({"n": "z", "block": "mid"})
    assert result == "name=z\n\nline1\nmid\nline3"


def test_render_missing_setting_arg_raises_keyerror() -> None:
    """Missing arg_dict key for a setting_str option raises KeyError."""
    _, script_generator = _import_script_api()
    gen = script_generator("demo", _minimal_setting_dict(), {})
    gen.load_template("body")
    with pytest.raises(KeyError):
        gen.render({"threads": 1})  # missing job_name


def test_render_missing_template_dest_raises_keyerror() -> None:
    """Missing arg_dict key for a templates dest raises KeyError."""
    _, script_generator = _import_script_api()
    gen = script_generator("demo", _minimal_setting_dict(), _minimal_templates())
    gen.load_template("#BODY# / #OUT#")
    with pytest.raises(KeyError):
        gen.render(
            {
                "job_name": "n",
                "threads": 1,
                "body_text": "x",
                # missing outfile
            }
        )


def test_render_is_deterministic_for_same_args() -> None:
    """str render output is deterministic for the same add order and args."""
    _, script_generator = _import_script_api()
    gen = script_generator("demo", _minimal_setting_dict(), _minimal_templates())
    gen.load_template("#BODY#:#OUT#")
    args = {
        "job_name": "j",
        "threads": 2,
        "body_text": "b",
        "outfile": "o",
    }
    assert gen.render(args) == gen.render(args)
