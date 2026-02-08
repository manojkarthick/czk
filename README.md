# Datahoarding Scripts

CLI utilities in this folder for file analysis, deduplication, syncing, and directory transforms.

## Requirements

- macOS or Linux shell environment
- `czkawka_cli` for duplicate detection/removal
- `python` + `uv` for the `czk` wrapper CLI

## Quick Start

- Install the Python CLI wrapper:

```bash
uv tool install --editable .
```

- Then run:

```bash
czk test [directory]
czk execute [directory]
```

## czk (Python CLI Wrapper)

High-level wrapper over `czkawka_cli` for image/video duplicate workflows with readable summaries and CSV reports.

### Commands

- `czk test [directory]`
  - Dry run (no deletion)
  - Generates JSON + CSV reports
  - Prints counts and a table preview

- `czk execute [directory]`
  - Performs actual duplicate deletion via Czkawka (`AEB` strategy)
  - Generates JSON + CSV reports
  - Prints counts and a table preview

### Default behavior

- Scans both images and videos (`--media both`)
- Image mode uses:
  - `--image-similarity High`
  - `--hash-size 32`
- Video mode uses:
  - `--video-tolerance 10`
- Writes timestamped artifacts in current working directory (or `--out-dir`)

### Useful options

- `--media {both,images,videos}`
- `--hash-size {8,16,32,64}`
- `--image-similarity {Minimal,VeryLow,Low,Medium,High,VeryHigh,None}`
- `--video-tolerance 0..20`
- `--top N` (table rows to print; default 50)
- `--out-dir <path>`

### Output files

Per media type, per run:

- JSON: `<base-folder>-<media>-<YYYYMMDD-HHMMSS>.json`
- CSV: `<base-folder>-<media>-<YYYYMMDD-HHMMSS>.csv`

CSV columns:

1. `#`
2. `file_to_keep`
3. `files_to_remove` (JSON array string)
4. `count` (number of files to remove)

### Reported metrics

Per media type and combined summary:

- `total_found`
- `duplicate_groups`
- `duplicates_to_remove`
- `after_remove_estimate`

## check_codecs.sh

Scans video files in a directory, detects codecs with `ffprobe`, and prints summary counts by extension and codec.

Usage:

```bash
./check_codecs.sh [options] [target_dir]
```

Options:

- `-v`, `--verbose`: print per-file details
- `--no-h264`: print per-file details only for non-H.264 files

Notes:

- Default directory: current directory (`.`)
- Uses CPU-parallel processing

## deduplicate_collection.sh

Runs image deduplication per immediate subfolder of a collection directory using `czkawka_cli`.

Usage:

```bash
./deduplicate_collection.sh [collection_dir] [--dry-run]
```

Behavior:

- Default directory: `./Collection`
- `--dry-run`: prints duplicate candidates without deleting
- Normal mode: deletes duplicates using `AEO` (keep oldest)

## diagnose_inflation.sh

Diagnoses rsync size inflation risks from hard links and sparse files.

Usage:

```bash
./diagnose_inflation.sh <directory>
```

It reports:

- Actual disk usage (`du -sh`)
- Hard-link-expanded usage (`du -slh`) -> indicates when `rsync -H` is needed
- Apparent size (`du --apparent-size`) -> indicates when `rsync -S` is needed

## flatten.sh

Moves all files from a source directory tree into one target directory, with collision-safe renaming.

Usage:

```bash
./flatten.sh <source_directory> <target_directory>
```

Behavior:

- Creates target directory if missing
- Moves files (does not copy)
- On collisions, appends counter suffixes: `file.txt`, `file_1.txt`, `file_2.txt`, ...

## safe_sync.sh

Safe `rsync` wrapper to copy from source to target without deleting or overwriting existing target files.

Usage:

```bash
./safe_sync.sh <source_directory> <target_directory>
```

Behavior:

- Uses: `-a -h -H -S --partial --ignore-existing --stats`
- Uses modern progress (`--info=progress2`) when supported, else legacy `--progress`
- Guards against recursive sync if target is inside source

## test_harness.sh

Creates a temporary test environment and validates `safe_sync.sh` behavior.

Usage:

```bash
./test_harness.sh
```

Validates:

- basic copy
- nested copy
- filenames with spaces
- no overwrite of existing target files
- no deletion of extra target files

## Development

Run tests for the Python CLI:

```bash
uv run python -m unittest discover -s tests -v
```
