"""Shipped example RC under code/example_configs/ (SPEC002 slice).

Normative shape: slurm + bash + plainPy; #header1#…#header5#; mem/gpu/conda;
bash only (no plainScript); conda setting_str without lab-absolute paths.
"""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Any


def _example_rc_path(code_root: Path) -> Path:
    return code_root / "example_configs" / "buddingScriptsRC.json"


def _load_example(code_root: Path) -> dict[str, Any]:
    path = _example_rc_path(code_root)
    assert path.is_file(), f"expected shipped example RC at {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _load_rc():
    pkg = importlib.import_module("buddingScripts")
    assert hasattr(pkg, "load_rc")
    return pkg.load_rc


def test_shipped_example_rc_exists(code_root: Path) -> None:
    """Package ships example_configs/buddingScriptsRC.json under code/."""
    path = _example_rc_path(code_root)
    assert path.is_file()


def test_shipped_example_passes_load_rc(code_root: Path) -> None:
    """Shipped example is valid under the RC schema (load_rc succeeds)."""
    load_rc = _load_rc()
    data = load_rc(_example_rc_path(code_root))
    assert set(data) >= {"script_generators", "templates", "suffix"}


def test_example_generators_are_slurm_bash_plainPy(code_root: Path) -> None:
    """Example includes slurm, bash, and plainPy generators."""
    data = _load_example(code_root)
    names = set(data["script_generators"])
    assert names == {"slurm", "bash", "plainPy"}


def test_example_uses_bash_not_plainScript(code_root: Path) -> None:
    """Locked v1 pick: shipped example uses bash only (no plainScript alias)."""
    data = _load_example(code_root)
    assert "bash" in data["script_generators"]
    assert "plainScript" not in data["script_generators"]
    assert "plainScript" not in data["suffix"]


def test_example_suffix_matches_generators(code_root: Path) -> None:
    """Matching suffix entries: .slurm, .sh, .py for the three generators."""
    data = _load_example(code_root)
    assert set(data["suffix"]) == set(data["script_generators"])
    assert data["suffix"]["slurm"] == ".slurm"
    assert data["suffix"]["bash"] == ".sh"
    assert data["suffix"]["plainPy"] == ".py"


def test_example_templates_are_headerN_placeholders(code_root: Path) -> None:
    """Product default templates map #header1#…#header5# → header1…header5."""
    data = _load_example(code_root)
    expected = {
        "#header1#": "header1",
        "#header2#": "header2",
        "#header3#": "header3",
        "#header4#": "header4",
        "#header5#": "header5",
    }
    assert data["templates"] == expected


def test_example_templates_dests_are_unique(code_root: Path) -> None:
    """templates values (dest names) are unique."""
    data = _load_example(code_root)
    values = list(data["templates"].values())
    assert len(values) == len(set(values))


def test_example_slurm_variables_cover_required_set(code_root: Path) -> None:
    """slurm variables cover interpreter, job_name, nodes/cores, mem, gpu, walltime, queue, conda."""
    data = _load_example(code_root)
    variables = data["script_generators"]["slurm"]["variables"]
    keys = set(variables)
    assert "job_name" in keys
    assert "conda_environment" in keys
    assert variables["conda_environment"]["flag"] == "--conda"
    joined = " ".join(keys).lower()
    assert "mem" in joined or "memory" in joined
    assert "gpu" in joined
    assert any(
        k for k in keys if "time" in k.lower() or "hour" in k.lower() or "wall" in k.lower()
    )
    assert any(
        k
        for k in keys
        if any(tok in k.lower() for tok in ("partition", "queue", "cluster", "account"))
    )
    assert any(
        k
        for k in keys
        if any(tok in k.lower() for tok in ("node", "ntask", "cpu", "core", "task"))
    )
    assert any(
        k
        for k in keys
        if any(tok in k.lower() for tok in ("python", "interpreter", "exec", "bin"))
    )

def test_example_slurm_setting_str_has_sbatch_and_conda(code_root: Path) -> None:
    """slurm setting_str emits SBATCH header lines plus optional conda activate block."""
    data = _load_example(code_root)
    setting_str = data["script_generators"]["slurm"]["setting_str"]
    assert isinstance(setting_str, dict) and setting_str
    keys_blob = "\n".join(setting_str)
    assert "#SBATCH" in keys_blob or "SBATCH" in keys_blob
    assert "<setting>" in keys_blob
    assert "conda" in keys_blob.lower()
    # Every setting_str value names a variables key.
    var_keys = set(data["script_generators"]["slurm"]["variables"])
    for opt in setting_str.values():
        assert opt in var_keys


def test_example_bash_and_plainPy_are_minimal_job_name_headers(code_root: Path) -> None:
    """bash and plainPy have minimal job_name-oriented headers."""
    data = _load_example(code_root)
    for name in ("bash", "plainPy"):
        gen = data["script_generators"][name]
        assert "job_name" in gen["variables"]
        assert gen["setting_str"]
        for opt in gen["setting_str"].values():
            assert opt in gen["variables"]


def test_example_allows_numeric_defaults(code_root: Path) -> None:
    """Locked pick: numeric default values appear in the shipped example JSON."""
    data = _load_example(code_root)
    defaults = []
    for gen in data["script_generators"].values():
        for opt in gen["variables"].values():
            defaults.append(opt["default"])
    assert any(isinstance(d, (int, float)) and not isinstance(d, bool) for d in defaults)


def test_example_conda_setting_str_avoids_lab_absolute_paths(code_root: Path) -> None:
    """Example conda setting_str must not embed lab-absolute filesystem paths."""
    data = _load_example(code_root)
    setting_str = data["script_generators"]["slurm"]["setting_str"]
    conda_lines = [
        line
        for line, opt in setting_str.items()
        if "conda" in line.lower() or opt == "conda_environment"
    ]
    assert conda_lines, "expected at least one conda-related setting_str line"
    abs_path = re.compile(r"(^|[\s\"'=])/[\w.-]+/")
    for line in conda_lines:
        assert not abs_path.search(line), (
            f"conda setting_str must avoid lab-absolute paths; found in: {line!r}"
        )


def test_example_each_variable_has_default_flag_help(code_root: Path) -> None:
    """Every variables.<option> in the example has default, flag, and help."""
    data = _load_example(code_root)
    for gen_name, gen in data["script_generators"].items():
        for opt_name, opt in gen["variables"].items():
            assert "default" in opt, f"{gen_name}.{opt_name} missing default"
            assert "flag" in opt, f"{gen_name}.{opt_name} missing flag"
            assert "help" in opt, f"{gen_name}.{opt_name} missing help"
            assert isinstance(opt["default"], (str, int, float))
            assert isinstance(opt["flag"], str) and opt["flag"]
            assert isinstance(opt["help"], str)
