from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal, Sequence, cast

from .counting import MediaType, count_media_files
from .czkawka import (
    build_czkawka_command,
    ensure_czkawka_cli,
    run_czkawka,
)
from .rendering import RenderConfig, Renderer
from .report import build_preview_rows_from_csv, build_rows, build_summary, load_duplicate_groups, write_csv

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
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output.",
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
    return [cast(MediaType, media)]


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
    renderer: Renderer,
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
) -> None:
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

    renderer.render_media_header(media=media, mode=mode, command=command)

    completed = run_czkawka(command)
    renderer.render_exit_code(completed.returncode)

    groups = load_duplicate_groups(json_path)
    rows = build_rows(groups, mode=mode)
    write_csv(rows, csv_path)

    summary = build_summary(total_found=total_found, duplicate_groups=len(groups), rows=rows)
    renderer.render_summary(summary)
    renderer.render_artifacts(json_path=json_path, csv_path=csv_path)

    preview_rows, total_rows, shown_rows = build_preview_rows_from_csv(csv_path, top=top)
    renderer.render_preview_table(
        preview_rows=preview_rows,
        shown_rows=shown_rows,
        total_rows=total_rows,
    )

    return None


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    mode: Mode = args.command
    render_config = RenderConfig(no_color=args.no_color, stdout_is_tty=sys.stdout.isatty())
    renderer = Renderer(render_config)

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

        renderer.render_run_header(
            mode=mode,
            target_dir=target_dir,
            out_dir=out_dir,
            timestamp=timestamp,
            media_targets=media_targets,
        )

        for media in media_targets:
            _run_one_media(
                renderer=renderer,
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
        return 0
    except (RuntimeError, ValueError) as exc:
        renderer.render_error("Run failed", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
