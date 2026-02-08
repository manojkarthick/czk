from __future__ import annotations

import argparse
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal, Sequence, cast

from .counting import MediaType, count_media_files
from .czkawka import (
    build_czkawka_command,
    ensure_czkawka_cli,
    run_czkawka,
)
from .duckdb_shell import (
    ExpandedDuplicateRow,
    build_expanded_rows,
    collect_media_inventory,
    ensure_duckdb_cli,
    launch_duckdb_session,
)
from .rendering import RenderConfig, Renderer
from .report import build_preview_rows_from_csv, build_rows, build_summary, load_duplicate_groups, write_csv

Mode = Literal["test", "execute", "analyze"]

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
    """Parse a strictly positive integer argparse value.

    Args:
        value: Raw CLI value.

    Returns:
        Parsed integer when greater than zero.

    Raises:
        argparse.ArgumentTypeError: If the value is not greater than zero.
    """
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than 0.")
    return parsed


def _video_tolerance(value: str) -> int:
    """Parse and validate video tolerance in the inclusive range [0, 20].

    Args:
        value: Raw CLI value.

    Returns:
        Parsed tolerance value.

    Raises:
        argparse.ArgumentTypeError: If the value is outside [0, 20].
    """
    parsed = int(value)
    if parsed < 0 or parsed > 20:
        raise argparse.ArgumentTypeError("Video tolerance must be in range [0, 20].")
    return parsed


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach shared CLI arguments used by all subcommands.

    Args:
        parser: Subparser instance to modify in place.
    """
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
        default=None,
        help="Directory where JSON and CSV artifacts are written. Defaults to shared temp reports folder when omitted.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output.",
    )


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level `czk` argument parser.

    Returns:
        Fully configured parser with all subcommands and aliases.
    """
    parser = argparse.ArgumentParser(
        prog="czk",
        description="Run Czkawka duplicate workflows for images/videos with CSV reports.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    test_parser = subparsers.add_parser(
        "test",
        aliases=["check"],
        help="Run dry-run duplicate analysis.",
    )
    _add_common_arguments(test_parser)

    execute_parser = subparsers.add_parser("execute", help="Run duplicate deletion.")
    _add_common_arguments(execute_parser)

    analyze_parser = subparsers.add_parser(
        "analyze",
        aliases=["analyse"],
        help="Run dry-run analysis then open an interactive DuckDB shell.",
    )
    _add_common_arguments(analyze_parser)

    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments and normalize subcommand aliases.

    Args:
        argv: Optional argument sequence; defaults to `sys.argv[1:]`.

    Returns:
        Parsed namespace with canonical command names.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "command", "") == "check":
        args.command = "test"
    if getattr(args, "command", "") == "analyse":
        args.command = "analyze"
    return args


def _selected_media(media: str) -> list[MediaType]:
    """Expand CLI media selector into explicit media targets.

    Args:
        media: CLI media argument (`both`, `images`, or `videos`).

    Returns:
        Ordered list of media targets for downstream loops.
    """
    if media == "both":
        return ["images", "videos"]
    return [cast(MediaType, media)]


def _sanitize_name(value: str) -> str:
    """Normalize a value for safe file-name usage.

    Args:
        value: Raw input text.

    Returns:
        Sanitized basename containing only safe characters.
    """
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return sanitized or "root"


def _default_reports_dir() -> Path:
    """Return the default shared reports directory in system temp storage.

    Returns:
        Default reports directory path.
    """
    return Path(tempfile.gettempdir()) / "czk-reports"


def _resolve_out_dir(raw_out_dir: str | None) -> Path:
    """Resolve output directory from explicit option or default temp location.

    Args:
        raw_out_dir: Optional `--out-dir` value.

    Returns:
        Absolute path where reports should be written.
    """
    if raw_out_dir:
        return Path(raw_out_dir).expanduser().resolve()
    return _default_reports_dir().resolve()


def _build_artifact_paths(
    *,
    out_dir: Path,
    base_name: str,
    media: MediaType,
    timestamp: str,
) -> tuple[Path, Path]:
    """Build unique JSON and CSV report paths for a media run.

    Args:
        out_dir: Target directory for generated reports.
        base_name: Sanitized base folder name.
        media: Media type (`images` or `videos`).
        timestamp: Run timestamp string.

    Returns:
        Tuple of `(json_path, csv_path)` guaranteed not to collide.
    """
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
) -> tuple[Path, Path]:
    """Run one media workflow from scan through rendered reporting.

    Args:
        renderer: Renderer used for terminal output.
        mode: Workflow mode (`test`, `execute`, or `analyze`).
        media: Media target for this run.
        target_dir: Directory being scanned.
        out_dir: Directory to write report artifacts.
        timestamp: Run timestamp suffix.
        base_name: Sanitized target folder name.
        czkawka_executable: Path to Czkawka CLI binary.
        hash_size: Image hash size.
        image_similarity: Image similarity preset.
        video_tolerance: Video tolerance value.
        top: Preview row limit for terminal output.

    Returns:
        Tuple of report paths `(json_path, csv_path)` for this media run.
    """
    dry_run = mode in {"test", "analyze"}
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
    report_mode = "test" if mode == "analyze" else mode
    rows = build_rows(groups, mode=report_mode)
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

    return json_path, csv_path


def _run_analyze(
    *,
    renderer: Renderer,
    media_targets: list[MediaType],
    target_dir: Path,
    out_dir: Path,
    timestamp: str,
    base_name: str,
    czkawka_executable: str,
    hash_size: int,
    image_similarity: str,
    video_tolerance: int,
    top: int,
) -> int:
    """Run analyze workflow and start interactive DuckDB session.

    Args:
        renderer: Renderer used for terminal output.
        media_targets: Media groups selected by CLI args.
        target_dir: Directory to scan.
        out_dir: Artifact output directory.
        timestamp: Run timestamp suffix.
        base_name: Sanitized target folder name.
        czkawka_executable: Path to Czkawka CLI binary.
        hash_size: Image hash size.
        image_similarity: Image similarity preset.
        video_tolerance: Video tolerance value.
        top: Preview row limit for terminal output.

    Returns:
        Exit code from the DuckDB interactive shell process.
    """
    duckdb_executable = ensure_duckdb_cli()
    duplicate_json_paths: dict[MediaType, Path] = {}
    duplicate_csv_paths: dict[MediaType, Path] = {}
    expanded_rows: dict[MediaType, list[ExpandedDuplicateRow]] = {}

    for media in media_targets:
        json_path, csv_path = _run_one_media(
            renderer=renderer,
            mode="analyze",
            media=media,
            target_dir=target_dir,
            out_dir=out_dir,
            timestamp=timestamp,
            base_name=base_name,
            czkawka_executable=czkawka_executable,
            hash_size=hash_size,
            image_similarity=image_similarity,
            video_tolerance=video_tolerance,
            top=top,
        )
        duplicate_json_paths[media] = json_path
        duplicate_csv_paths[media] = csv_path
        expanded_rows[media] = build_expanded_rows(csv_path, media)

    inventory_rows = collect_media_inventory(target_dir, media_targets)
    renderer.render_duckdb_intro(media_targets)
    return launch_duckdb_session(
        media_targets=media_targets,
        duckdb_executable=duckdb_executable,
        duplicate_csv_paths=duplicate_csv_paths,
        duplicate_json_paths=duplicate_json_paths,
        inventory_rows=inventory_rows,
        expanded_rows=expanded_rows,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the `czk` CLI entrypoint.

    Args:
        argv: Optional argument sequence; defaults to `sys.argv[1:]`.

    Returns:
        Process-style exit code (`0` on success, non-zero on failure).
    """
    args = parse_args(argv)
    mode = cast(Mode, args.command)
    render_config = RenderConfig(no_color=args.no_color, stdout_is_tty=sys.stdout.isatty())
    renderer = Renderer(render_config)

    try:
        czkawka_executable = ensure_czkawka_cli()
        target_dir = Path(args.directory).expanduser().resolve()
        if not target_dir.exists() or not target_dir.is_dir():
            raise RuntimeError(f"Directory does not exist or is not a directory: {target_dir}")

        out_dir = _resolve_out_dir(args.out_dir)
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

        if mode == "analyze":
            return _run_analyze(
                renderer=renderer,
                media_targets=media_targets,
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
