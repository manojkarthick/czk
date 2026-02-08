# AGENTS.md

## Project Overview

This repository contains local CLI tools for media/file workflows:

- A Python CLI (`czk`) that wraps `czkawka_cli` for image/video duplicate workflows with CSV/JSON reports.

Primary goal: safe, observable file operations with readable output and reproducible artifacts.

## Environment and Tooling

- OS target: macOS/Linux.
- Python packaging/runtime: `uv` + Python 3.11+.
- External binaries used:
  - `czkawka_cli`
  - `ffprobe`
  - `rsync`

## Python CLI (`czk`) Workflow

Install locally:

```bash
uv tool install --editable .
```

Run dry-run analysis:

```bash
czk test [directory]
```

Run deletion workflow:

```bash
czk execute [directory]
```

Current defaults:

- Runs both images and videos unless overridden.
- Image options: similarity `High`, hash-size `32`.
- Video option: tolerance `10`.
- Output artifacts are timestamped JSON/CSV files.

## Testing and Validation

Run unit tests:

```bash
uv run python -m unittest discover -s tests -v
```

Optional quick smoke test (dry-run only):

```bash
czk test /path/to/target --top 10
```

## Safety Rules

- Prefer `test` mode before any `execute` run.
- Do not assume deletion decisions without reviewing CSV/JSON outputs.
- Avoid destructive shell operations unless explicitly requested.
- For sync/transfer tasks, preserve existing safety flags (no overwrite/no delete semantics unless user asks otherwise).

## Coding and Change Guidance

- Keep changes focused; preserve existing script behavior unless requirement changes.
- For Python code:
  - maintain stdlib-only approach unless dependency is necessary.
  - keep CLI output readable and stable for downstream parsing.
- For report changes:
  - preserve CSV column contract: `#, file_to_keep, files_to_remove, count`.
  - keep artifact naming deterministic and timestamped.

## Output Style Contract (`czk`)

- Keep grouped section order stable:
  1. run header
  2. per-media sections
- Keep on-screen duplicate preview columns stable:
  - wide: `#`, `file_to_keep`, `remove_count`, `first_remove`
  - medium: `#`, `file_to_keep`, `remove_count`
  - narrow: bordered list-style preview blocks
- Keep CSV schema stable:
  - `#, file_to_keep, files_to_remove, count`
- Color behavior:
  - auto color on interactive TTY
  - plain output when not a TTY
  - `--no-color` forces plain output
- Keep all labels human-readable in terminal output (avoid internal key names).
- Keep preview display compact (filename-only), while CSV keeps full paths.

## Common Tasks for Future Agents

1. Add CLI option:
   - update `/Users/manojkarthick/code/sandbox/datahoarding/scripts/src/czk_tool/cli.py`
   - thread value into runner/report modules
   - add tests in `/Users/manojkarthick/code/sandbox/datahoarding/scripts/tests/`

2. Adjust Czkawka behavior:
   - update command construction in `/Users/manojkarthick/code/sandbox/datahoarding/scripts/src/czk_tool/czkawka.py`
   - verify with dry-run smoke test

3. Modify reporting/counting:
   - update `/Users/manojkarthick/code/sandbox/datahoarding/scripts/src/czk_tool/report.py` or `/Users/manojkarthick/code/sandbox/datahoarding/scripts/src/czk_tool/counting.py`
   - run unit tests

## Output Expectations

When making code changes, include:

- What changed and why.
- Files touched.
- Validation performed (tests/commands).
- Any known limitations or follow-up actions.
