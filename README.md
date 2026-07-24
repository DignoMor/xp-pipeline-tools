# xp-pipeline-tools

Pip-installable multi-entrypoint tools distribution:

- `buddingScripts` — generate bash / Slurm / Python job scripts from a home RC
  and optional body templates
- `YuLabDataAllocator` — allocate and look up abstract branch paths across
  configured drives

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

## YuLabDataAllocator

Requires `YUHOME` and a config at `$YUHOME/.YuLabDataAllocator/config.json`.
An example is in `example_configs/YuLabDataAllocator-config.json`. The SQLite
DB defaults to `~/.YuLabDataAllocator/YuLabDataAllocator.db`.

```bash
# console script (or: python -m YuLabDataAllocator)
YuLabDataAllocator --help
YuLabDataAllocator allocate 3-AD/0-raw
YuLabDataAllocator get 3-AD/0-raw
YuLabDataAllocator delete 3-AD/0-raw
YuLabDataAllocator ls --root 8-Reporter -s
```

Library import:

```python
import YuLabDataAllocator
from YuLabDataAllocator import Allocator, StorageManager, TreeVisualizer
```
