# xp-pipeline-tools

Pip-installable multi-entrypoint tools distribution. First entrypoint:
`buddingScripts` — generate bash / Slurm / Python job scripts from a home RC
and optional body templates.

## Install

```bash
pip install -e .
# or with test extras:
pip install -e ".[dev]"
```

## buddingScripts

Requires a home RC at `~/.buddingScriptsRC.json`. An example is in
`example_configs/buddingScriptsRC.json`.

```bash
# console script (or: python -m buddingScripts)
buddingScripts --help
buddingScripts slurm -N myjob --opath ./out
buddingScripts bash -N jobs.list --opath ./out   # .list on job_name expands rows
```

Shared flags: `--opath` / `-O` (output directory), `--template` (body template
file). Subcommands and their flags come from the RC `script_generators` map.
Output files are `{opath}/{job_name}{suffix}` using the RC `suffix` map.

Library import:

```python
import buddingScripts
from buddingScripts import load_rc, script_generator, validate_rc
```
