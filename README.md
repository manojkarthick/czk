# czk

A CLI wrapper around [`czkawka_cli`](https://github.com/qarmin/czkawka) focused on usability and easier analysis of duplicate images and videos.

## Features

- Dry-run and live deletion modes with colorized, grouped terminal output
- CSV and JSON reports per run
- Interactive SQL analysis via DuckDB
- Self-contained HTML visual report with inline image/video previews, search, and pagination

## Requirements

- macOS or Linux
- [`czkawka_cli`](https://github.com/qarmin/czkawka) — duplicate detection engine
- [`duckdb`](https://duckdb.org/) CLI — required for `czk analyze`
- Python + [`uv`](https://github.com/astral-sh/uv)

## Installation

```bash
uv tool install --editable .
```

## Usage

```bash
czk test <directory>      # Dry run — scan for duplicates, no deletion
czk execute <directory>   # Delete duplicates (AEB strategy)
czk analyze <directory>   # Interactive DuckDB SQL session over scan results
czk viz <directory>       # Generate a self-contained HTML visual report
```

`czk check` is an alias for `czk test`; `czk analyse` is an alias for `czk analyze`.

## Options

| Flag | Description |
|---|---|
| `--media {both,images,videos}` | Media type to scan (default: `both`) |
| `-s, --similarity-preset` | Image similarity preset: `Original`, `VeryHigh`, `High`, `Medium`, `Small`, `VerySmall`, `Minimal` (default: `High`) |
| `-c, --hash-size {8,16,32,64}` | Perceptual hash size for images (default: `32`) |
| `-g, --hash-alg` | Hash algorithm for images: `Mean`, `Gradient`, `Blockhash`, `VertGradient`, `DoubleGradient`, `Median` (default: `Gradient`) |
| `-z, --image-filter` | Resize filter for images: `Lanczos3`, `Nearest`, `Triangle`, `Faussian`, `Catmullrom` (default: `Nearest`) |
| `-t, --tolerance 0..20` | Similarity tolerance for videos (default: `10`) |
| `--top N` | Limit duplicate groups in previews (default: `50`) |
| `--all` | Show all duplicate groups, overrides `--top` |
| `--out-dir <path>` | Output directory (default: `<system-temp>/czk-reports`) |
| `--no-color` | Disable colored output |

## Output

Each run writes timestamped artifacts to the output directory:

- `<base>-<media>-<YYYYMMDD-HHMMSS>.json`
- `<base>-<media>-<YYYYMMDD-HHMMSS>.csv`
- `<base>-viz-<YYYYMMDD-HHMMSS>.html` (`czk viz` only)

CSV columns: `index`, `file_to_keep`, `files_to_remove`, `count`

## Disclaimer

Parts of this project were assisted by AI tooling. Review all commands carefully before running, especially deletion workflows. This software is provided "as is" without warranties of any kind. The authors are not liable for any data loss or other damages resulting from use.
