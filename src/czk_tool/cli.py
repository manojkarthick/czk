from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Sequence

from .counting import MediaType, count_media_files
from .czkawka import (
    build_czkawka_command,
    ensure_czkawka_cli,
    format_command,
    run_czkawka,
)
from .report import (
    MediaSummary,
    build_pretty_table_from_csv,
    build_rows,
    build_summary,
    load_duplicate_groups,
    write_csv,
)

Mode = Literal["test", "execute"]

IMAGE_SIMILARITY_CHOICES = (
    "Minimal",
    "VeryLow",
    "Low",
    "Medium",
    "High",
    "VeryHigh",
    "None",
)


@dataclass(frozen=True)
class MediaRunResult:
    media: MediaType
    summary: MediaSummary
    json_path: Path
    csv_path: Path


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than 0.")
    return parsed


def _video_tolerance(value: str) -> int:
    parsed = int(value)
    if parsed < 0 or parsed > 20:
        raise argparse.ArgumentTypeError("Video tolerance must be in range [0, 20].")
    return parsed


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("directory", nargs="?", default=".")
    parser.add_argument(
        "--media",
        choices=("both", "images", "videos"),
        default="both",
        help="Select which media scans to run.",
    )
    parser.add_argument(
        "--hash-size",
        type=int,
        choices=(8, 16, 32, 64),
        default=32,
        help="Image perceptual hash size.",
    )
    parser.add_argument(
        "--image-similarity",
        choices=IMAGE_SIMILARITY_CHOICES,
        default="High",
        help="Image similarity preset passed to Czkawka.",
    )
    parser.add_argument(
        "--video-tolerance",
        type=_video_tolerance,
        default=10,
        help="Video tolerance in range [0, 20].",
    )
    parser.add_argument(
        "--top",
        type=_positive_int,
        default=50,
        help="Number of CSV rows to pretty print.",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Directory where JSON and CSV artifacts are written.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="czk",
        description="Run Czkawka duplicate workflows for images/videos with CSV reports.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    test_parser = subparsers.add_parser("test", help="Run dry-run duplicate analysis.")
    _add_common_arguments(test_parser)

    execute_parser = subparsers.add_parser("execute", help="Run duplicate deletion.")
    _add_common_arguments(execute_parser)

    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    return parser.parse_args(argv)


def _selected_media(media: str) -> list[MediaType]:
    if media == "both":
        return ["images", "videos"]
    return [media]  # type: ignore[return-value]


def _sanitize_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return sanitized or "root"


def _build_artifact_paths(
    *,
    out_dir: Path,
    base_name: str,
    media: MediaType,
    timestamp: str,
) -> tuple[Path, Path]:
    counter = 0
    while True:
        suffix = f"-{counter}" if counter else ""
        json_path = out_dir / f"{base_name}-{media}-{timestamp}{suffix}.json"
        csv_path = out_dir / f"{base_name}-{media}-{timestamp}{suffix}.csv"
        if not json_path.exists() and not csv_path.exists():
            return json_path, csv_path
        counter += 1


def _run_one_media(
    *,
    mode: Mode,
    media: MediaType,
    target_dir: Path,
    out_dir: Path,
    timestamp: str,
    base_name: str,
    czkawka_executable: str,
    hash_size: int,
    image_similarity: str,
    video_tolerance: int,
    top: int,
) -> MediaRunResult:
    dry_run = mode == "test"
    total_found = count_media_files(target_dir, media)
    json_path, csv_path = _build_artifact_paths(
        out_dir=out_dir,
        base_name=base_name,
        media=media,
        timestamp=timestamp,
    )

    command = build_czkawka_command(
        executable=czkawka_executable,
        media=media,
        target_dir=target_dir,
        pretty_json_path=json_path,
        dry_run=dry_run,
        image_similarity=image_similarity,
        hash_size=hash_size,
        video_tolerance=video_tolerance,
    )

    print("")
    print(f"== {media.upper()} ({'DRY RUN' if dry_run else 'EXECUTE'}) ==")
    print(f"Command: {format_command(command)}")
    completed = run_czkawka(command)
    print(f"Czkawka exit code: {completed.returncode}")

    groups = load_duplicate_groups(json_path)
    rows = build_rows(groups, mode=mode)
    write_csv(rows, csv_path)

    summary = build_summary(total_found=total_found, duplicate_groups=len(groups), rows=rows)
    print(f"total_found: {summary.total_found}")
    print(f"duplicate_groups: {summary.duplicate_groups}")
    print(f"duplicates_to_remove: {summary.duplicates_to_remove}")
    print(f"after_remove_estimate: {summary.after_remove_estimate}")
    print(f"json: {json_path}")
    print(f"csv: {csv_path}")

    table, total_rows, shown_rows = build_pretty_table_from_csv(csv_path, top=top)
    print(f"table_rows_shown: {shown_rows}/{total_rows}")
    print(table)

    return MediaRunResult(media=media, summary=summary, json_path=json_path, csv_path=csv_path)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    mode: Mode = args.command

    try:
        czkawka_executable = ensure_czkawka_cli()
        target_dir = Path(args.directory).expanduser().resolve()
        if not target_dir.exists() or not target_dir.is_dir():
            raise RuntimeError(f"Directory does not exist or is not a directory: {target_dir}")

        out_dir = Path(args.out_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        media_targets = _selected_media(args.media)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base_name = _sanitize_name(target_dir.name)

        print(f"mode: {mode}")
        print(f"target_dir: {target_dir}")
        print(f"out_dir: {out_dir}")
        print(f"timestamp: {timestamp}")
        print(f"media: {', '.join(media_targets)}")

        results: list[MediaRunResult] = []
        for media in media_targets:
            result = _run_one_media(
                mode=mode,
                media=media,
                target_dir=target_dir,
                out_dir=out_dir,
                timestamp=timestamp,
                base_name=base_name,
                czkawka_executable=czkawka_executable,
                hash_size=args.hash_size,
                image_similarity=args.image_similarity,
                video_tolerance=args.video_tolerance,
                top=args.top,
            )
            results.append(result)

        combined_total = sum(result.summary.total_found for result in results)
        combined_groups = sum(result.summary.duplicate_groups for result in results)
        combined_remove = sum(result.summary.duplicates_to_remove for result in results)
        combined_after = sum(result.summary.after_remove_estimate for result in results)

        print("")
        print("== COMBINED SUMMARY ==")
        print(f"total_found: {combined_total}")
        print(f"duplicate_groups: {combined_groups}")
        print(f"duplicates_to_remove: {combined_remove}")
        print(f"after_remove_estimate: {combined_after}")
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
