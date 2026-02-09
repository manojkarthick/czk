# Czk

Wrapper around `czkawka_cli` with a focus on usability and easier analysis.

This repository is intentionally scoped to the `czk` CLI only.

## Requirements

- macOS or Linux shell environment
- `czkawka_cli` for duplicate detection/removal
- `duckdb` CLI for `czk analyze` interactive SQL sessions
- `python` + `uv` for the `czk` wrapper CLI

## Quick Start

- Install the Python CLI wrapper:

```bash
uv tool install --editable .
```

- Then run:

```bash
czk test [directory]
# alias:
czk check [directory]
czk execute [directory]
czk analyze [directory]
# alias:
czk analyse [directory]
czk viz [directory]
```

## czk (Python CLI Wrapper)

High-level wrapper over `czkawka_cli` for image/video duplicate workflows with grouped, colorized terminal output plus CSV reports.

### Commands

- `czk test [directory]`
  - Alias: `czk check [directory]`
  - Dry run (no deletion)
  - Generates JSON + CSV reports
  - Prints counts and a table preview

- `czk execute [directory]`
  - Performs actual duplicate deletion via Czkawka (`AEB` strategy)
  - Generates JSON + CSV reports
  - Prints counts and a table preview

- `czk analyze [directory]` (alias: `czk analyse [directory]`)
  - Runs dry-run scans (no deletion) for selected media
  - Generates JSON + CSV reports
  - Loads reports + media inventory into an in-memory DuckDB session
  - Opens interactive DuckDB shell for arbitrary SQL queries

- `czk viz [directory]`
  - Runs dry-run scans (no deletion) for selected media
  - Generates JSON + CSV reports (same schema/contracts as other modes)
  - Generates a self-contained HTML report with inline image/video previews
  - Attempts to auto-open the HTML report in the default browser
  - `--top N` limits duplicate groups rendered in the HTML visual preview

### Default behavior

- Scans both images and videos (`--media both`)
- Image mode uses:
  - `--image-similarity High`
  - `--hash-size 32`
- Video mode uses:
  - `--video-tolerance 10`
- Writes timestamped artifacts in shared temp folder by default:
  - `<system-temp>/czk-reports`
- `--out-dir` overrides the default output location

### Useful options

- `--media {both,images,videos}`
- `--hash-size {8,16,32,64}`
- `--image-similarity {Minimal,VeryLow,Low,Medium,High,VeryHigh,None}`
- `--video-tolerance 0..20`
- `--top N` (preview groups to render; default 50)
- `--out-dir <path>` (override default shared temp reports folder)
- `--no-color` (force plain output; default is auto-color on TTY)

### Output files

Per media type, per run:

- JSON: `<base-folder>-<media>-<YYYYMMDD-HHMMSS>.json`
- CSV: `<base-folder>-<media>-<YYYYMMDD-HHMMSS>.csv`

For `czk viz`, per run:

- HTML: `<base-folder>-viz-<YYYYMMDD-HHMMSS>.html`
- JSON/CSV artifacts are still generated per selected media type

Default location when `--out-dir` is omitted:

- `<system-temp>/czk-reports`

CSV columns:

1. `index`
2. `file_to_keep`
3. `files_to_remove` (JSON array string)
4. `count` (number of files to remove)

### Reported metrics

Per media section (human-readable labels in terminal):

- `Total Files Scanned`
- `Duplicate Groups Found`
- `Files Marked for Removal` (red value)
- `Estimated Files Remaining` (green value)

### Output structure (concise)

Each run prints grouped sections in this order:

1. Run header (`mode`, `target_dir`, `out_dir`, `timestamp`, `media`)
2. Per-media section (`images`, `videos`):
   - compact command representation + exit code
   - summary table (human-readable labels)
   - artifact paths
   - duplicate preview:
     - wide terminals: `index`, `file_to_keep`, `remove_count`, `first_remove`
     - medium terminals: `index`, `file_to_keep`, `remove_count`
     - narrow terminals: bordered list-style groups

Command display notes:

- Command output is intentionally compact and readable (representation, not exact shell replay).
- Long path values are shortened to placeholders such as `<target-folder>` and `<json-report>`.

### Analyze mode: DuckDB tables

`czk analyze`/`czk analyse` preloads these tables before opening shell.
Media tables are created only for the selected media (`--media`):

- `media_inventory`
  - `media_type`, `path`, `file_name`, `extension`, `size_bytes`, `modified_epoch`
- `duplicates_images`, `duplicates_videos`
  - `index`, `file_to_keep`, `files_to_remove`, `count`
- `duplicates_images_json`, `duplicates_videos_json`
  - JSON-derived rows with columns:
    `group_index`, `item_index`, `path`, `size_bytes`, `modified_date`, `raw_item_json`, `source_report`
- `duplicates_images_expanded`, `duplicates_videos_expanded`
  - `group_index`, `file_to_keep`, `remove_path`, `remove_ordinal`, `group_remove_count`

Starter queries:

```sql
SELECT COUNT(*) FROM media_inventory;
SELECT * FROM duplicates_images LIMIT 10;
SELECT * FROM duplicates_images_json LIMIT 10;
SELECT * FROM duplicates_images_expanded LIMIT 10;
```

## AI Disclosure and Liability

- Parts of this project were generated or assisted by AI tooling.
- You are responsible for reviewing and validating all commands before running them, especially deletion workflows.
- This software is provided "as is", without warranties of any kind.
- By using this project, you accept full responsibility for any outcomes, including data loss.
- The authors/maintainers are not liable for any direct or indirect damages resulting from use of this project.
