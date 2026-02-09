# AGENTS.md

## Project Overview

This repository is dedicated to the `czk` CLI only.

- A Python CLI (`czk`) that wraps `czkawka_cli` for image/video duplicate workflows with CSV/JSON reports.

Primary goal: safe, observable file operations with readable output and reproducible artifacts.

## Environment and Tooling

- OS target: macOS/Linux.
- Python packaging/runtime: `uv` + Python 3.11+.
- External binaries used:
  - `czkawka_cli`
  - `duckdb`

## Python CLI (`czk`) Workflow

Install locally:

```bash
uv tool install --editable .
```

Run dry-run analysis:

```bash
czk test [directory]
# alias:
czk check [directory]
```

Run deletion workflow:

```bash
czk execute [directory]
```

Run analyze workflow (interactive DuckDB shell):

```bash
czk analyze [directory]
# alias:
czk analyse [directory]
```

Current defaults:

- Runs both images and videos unless overridden.
- Image options: similarity `High`, hash-size `32`.
- Video option: tolerance `10`.
- Preview defaults to `--top 50`; `--all` overrides `--top` and shows all groups.
- Output artifacts are timestamped JSON/CSV files.
- Default reports directory (when `--out-dir` is omitted):
  - `<system-temp>/czk-reports`
- `--out-dir` overrides the default reports directory.
- Analyze mode always runs dry-run scans and opens DuckDB in-memory (`:memory:`).

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

## Coding and Change Guidance

- Keep changes focused; preserve existing script behavior unless requirement changes.
- For Python code:
  - maintain stdlib-only approach unless dependency is necessary.
  - keep CLI output readable and stable for downstream parsing.
  - add Google-style docstrings for every new or modified function/method.
- For report changes:
  - preserve CSV column contract: `index, file_to_keep, files_to_remove, count`.
  - keep artifact naming deterministic and timestamped.

## Output Style Contract (`czk`)

- Keep grouped section order stable:
  1. run header
  2. per-media sections
- Keep on-screen duplicate preview columns stable:
  - wide: `index`, `file_to_keep`, `remove_count`, `first_remove`
  - medium: `index`, `file_to_keep`, `remove_count`
  - narrow: bordered list-style preview blocks
- Keep command block copy-pasteable and accurate:
  - show the full command with real arguments as executed
  - preserve shell-safe quoting for paths/values when needed
- Keep CSV schema stable:
  - `index, file_to_keep, files_to_remove, count`
- Color behavior:
  - auto color on interactive TTY
  - plain output when not a TTY
  - `--no-color` forces plain output
- Keep all labels human-readable in terminal output (avoid internal key names).
- Keep preview display compact (filename-only), while CSV keeps full paths.
- Summary value color cues:
  - `Files Marked for Removal` value in red
  - `Estimated Files Remaining` value in green

## Analyze Contract (`czk analyze` / `czk analyse`)

- Analyze mode is non-destructive:
  - scans run in dry-run mode only
  - no duplicate deletion is performed
- DuckDB session defaults:
  - in-memory DB (`:memory:`)
  - interactive shell opened after scan/report generation
- Required loaded tables:
  - `media_inventory`
  - media-specific `duplicates_*`, `duplicates_*_json`, and `duplicates_*_expanded`
    tables are created only for the selected `--media` value
- Table contracts:
  - `duplicates_*` keep CSV schema (`index, file_to_keep, files_to_remove, count`)
  - `duplicates_*_json` columns:
    `group_index, item_index, path, size_bytes, modified_date, raw_item_json, source_report`
  - `duplicates_*_expanded` columns:
    `group_index, file_to_keep, remove_path, remove_ordinal, group_remove_count`

## Common Tasks for Future Agents

1. Add CLI option:
   - update `src/czk_tool/cli.py`
   - thread value into runner/report modules
   - add tests in `tests/`

2. Adjust Czkawka behavior:
   - update command construction in `src/czk_tool/czkawka.py`
   - verify with dry-run smoke test

3. Modify reporting/counting:
   - update `src/czk_tool/report.py` or `src/czk_tool/counting.py`
   - run unit tests

## Output Expectations

When making code changes, include:

- What changed and why.
- Files touched.
- Validation performed (tests/commands).
- Any known limitations or follow-up actions.
