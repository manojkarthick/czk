from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .counting import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, MediaType


@dataclass(frozen=True)
class MediaInventoryRow:
    media_type: str
    path: str
    file_name: str
    extension: str
    size_bytes: int
    modified_epoch: int


@dataclass(frozen=True)
class ExpandedDuplicateRow:
    group_index: int
    file_to_keep: str
    remove_path: str
    remove_ordinal: int
    group_remove_count: int


@dataclass(frozen=True)
class JsonDuplicateRow:
    group_index: int
    item_index: int
    path: str
    size_bytes: int | None
    modified_date: int | None
    raw_item_json: str
    source_report: str


def ensure_duckdb_cli() -> str:
    """Resolve the `duckdb` executable from PATH.

    Returns:
        Absolute path to the discovered DuckDB CLI binary.

    Raises:
        RuntimeError: If DuckDB CLI is not available.
    """
    executable = shutil.which("duckdb")
    if executable is None:
        raise RuntimeError("duckdb CLI is not installed or not available in PATH.")
    return executable


def _extension(file_name: str) -> str:
    """Extract a lowercase extension without a leading dot.

    Args:
        file_name: File name or path string.

    Returns:
        Normalized extension text, or an empty string.
    """
    return Path(file_name).suffix.lower().lstrip(".")


def _media_for_extension(extension: str) -> MediaType | None:
    """Map a file extension to a media bucket.

    Args:
        extension: Lowercase file extension without dot.

    Returns:
        `images`, `videos`, or `None` when unsupported.
    """
    if extension in IMAGE_EXTENSIONS:
        return "images"
    if extension in VIDEO_EXTENSIONS:
        return "videos"
    return None


def collect_media_inventory(target_dir: Path, media_targets: list[MediaType]) -> list[MediaInventoryRow]:
    """Collect file inventory metadata for selected media classes.

    Args:
        target_dir: Root folder to scan recursively.
        media_targets: Media groups to include in the inventory.

    Returns:
        Deterministically sorted inventory rows for matching files.
    """
    selected = set(media_targets)
    rows: list[MediaInventoryRow] = []

    for root, _, file_names in os.walk(target_dir, followlinks=False):
        for file_name in file_names:
            extension = _extension(file_name)
            media_type = _media_for_extension(extension)
            if media_type is None or media_type not in selected:
                continue

            file_path = Path(root) / file_name
            try:
                stat_result = file_path.stat()
            except OSError:
                continue

            rows.append(
                MediaInventoryRow(
                    media_type=media_type,
                    path=str(file_path),
                    file_name=file_name,
                    extension=extension,
                    size_bytes=int(stat_result.st_size),
                    modified_epoch=int(stat_result.st_mtime),
                )
            )

    rows.sort(key=lambda row: (row.media_type, row.path))
    return rows


def _parse_int(value: str, default: int) -> int:
    """Parse an integer value with fallback behavior.

    Args:
        value: Raw string to parse.
        default: Fallback value when parsing fails.

    Returns:
        Parsed integer or `default`.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_remove_list(raw_value: str) -> list[str]:
    """Parse a JSON-encoded remove list from CSV content.

    Args:
        raw_value: JSON string expected to contain a list.

    Returns:
        Stringified list entries, or an empty list on parse/shape mismatch.
    """
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def build_expanded_rows(csv_path: Path, media_type: MediaType) -> list[ExpandedDuplicateRow]:
    """Expand duplicate groups into one row per removable file.

    Args:
        csv_path: Path to a duplicate CSV report.
        media_type: Media label for call-site consistency.

    Returns:
        Expanded rows containing keep/remove pairs and group metadata.
    """
    del media_type  # Media-specific tables are created by caller.
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    expanded: list[ExpandedDuplicateRow] = []
    for ordinal, row in enumerate(rows, start=1):
        group_index = _parse_int(row.get("index", row.get("#", "")), ordinal)
        file_to_keep = row.get("file_to_keep", "")
        files_to_remove = _parse_remove_list(row.get("files_to_remove", "[]"))
        group_remove_count = _parse_int(row.get("count", ""), len(files_to_remove))

        for remove_ordinal, remove_path in enumerate(files_to_remove, start=1):
            expanded.append(
                ExpandedDuplicateRow(
                    group_index=group_index,
                    file_to_keep=file_to_keep,
                    remove_path=remove_path,
                    remove_ordinal=remove_ordinal,
                    group_remove_count=group_remove_count,
                )
            )
    return expanded


def build_json_rows(report_json_path: Path) -> list[JsonDuplicateRow]:
    """Normalize raw duplicate-report JSON into flat table rows.

    Args:
        report_json_path: Path to the Czkawka pretty JSON report.

    Returns:
        Flattened row records preserving group/item ordering.

    Raises:
        RuntimeError: If report JSON is invalid or has an unexpected shape.
    """
    try:
        raw_data = json.loads(report_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON report file: {report_json_path} ({exc})") from exc

    if not isinstance(raw_data, list):
        raise RuntimeError(f"Expected top-level array in report JSON: {report_json_path}")

    json_rows: list[JsonDuplicateRow] = []
    for group_index, raw_group in enumerate(raw_data, start=1):
        if not isinstance(raw_group, list):
            raise RuntimeError(f"Expected array group at index {group_index} in {report_json_path}")

        for item_index, raw_item in enumerate(raw_group, start=1):
            if not isinstance(raw_item, dict):
                raise RuntimeError(
                    f"Expected object in group {group_index}, item {item_index} in {report_json_path}"
                )
            path_value = raw_item.get("path")
            if not isinstance(path_value, str):
                path_value = ""

            size_value = raw_item.get("size")
            if isinstance(size_value, (int, float)):
                size_bytes: int | None = int(size_value)
            else:
                size_bytes = None

            modified_value = raw_item.get("modified_date")
            if isinstance(modified_value, (int, float)):
                modified_date: int | None = int(modified_value)
            else:
                modified_date = None

            json_rows.append(
                JsonDuplicateRow(
                    group_index=group_index,
                    item_index=item_index,
                    path=path_value,
                    size_bytes=size_bytes,
                    modified_date=modified_date,
                    raw_item_json=json.dumps(raw_item, ensure_ascii=False),
                    source_report=str(report_json_path),
                )
            )

    return json_rows


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    """Write row dictionaries to CSV with a fixed header order.

    Args:
        path: Destination CSV path.
        fieldnames: Column order for the CSV header.
        rows: Row dictionaries to write.
    """
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _sql_literal(path: Path) -> str:
    """Escape a filesystem path for inclusion in SQL string literals.

    Args:
        path: Path value to embed in SQL.

    Returns:
        SQL-safe string representation with single quotes escaped.
    """
    return str(path).replace("'", "''")


def _build_init_sql(
    *,
    media_targets: list[MediaType],
    inventory_csv_path: Path,
    duplicate_csv_paths: dict[MediaType, Path],
    duplicate_json_csv_paths: dict[MediaType, Path],
    expanded_csv_paths: dict[MediaType, Path],
) -> str:
    """Build DuckDB bootstrap SQL for the analyze session.

    Args:
        media_targets: Selected media groups for this run.
        inventory_csv_path: CSV file with full media inventory rows.
        duplicate_csv_paths: CSV report path per selected media type.
        duplicate_json_csv_paths: Flattened JSON-derived CSV path per media.
        expanded_csv_paths: Expanded remove-row CSV path per media.

    Returns:
        SQL script content used to create and populate session tables.
    """
    lines = [
        "PRAGMA disable_progress_bar;",
        (
            "CREATE OR REPLACE TABLE media_inventory AS "
            f"SELECT * FROM read_csv_auto('{_sql_literal(inventory_csv_path)}', HEADER=true);"
        ),
    ]

    for media in media_targets:
        lines.append(
            f"CREATE OR REPLACE TABLE duplicates_{media} AS "
            f"SELECT * FROM read_csv_auto('{_sql_literal(duplicate_csv_paths[media])}', HEADER=true);"
        )

    for media in media_targets:
        lines.append(
            f"CREATE OR REPLACE TABLE duplicates_{media}_json AS "
            f"SELECT * FROM read_csv_auto('{_sql_literal(duplicate_json_csv_paths[media])}', HEADER=true);"
        )

    for media in media_targets:
        lines.append(
            f"CREATE OR REPLACE TABLE duplicates_{media}_expanded AS "
            f"SELECT * FROM read_csv_auto('{_sql_literal(expanded_csv_paths[media])}', HEADER=true);"
        )

    return "\n".join(lines) + "\n"


def launch_duckdb_session(
    *,
    media_targets: list[MediaType],
    duckdb_executable: str,
    duplicate_csv_paths: dict[MediaType, Path],
    duplicate_json_paths: dict[MediaType, Path],
    inventory_rows: list[MediaInventoryRow],
    expanded_rows: dict[MediaType, list[ExpandedDuplicateRow]],
) -> int:
    """Launch an interactive in-memory DuckDB shell with preloaded tables.

    Args:
        media_targets: Selected media groups for this analyze run.
        duckdb_executable: Path to DuckDB CLI binary.
        duplicate_csv_paths: Duplicate CSV report path per selected media.
        duplicate_json_paths: Raw Czkawka JSON report path per selected media.
        inventory_rows: Inventory rows for all selected media files.
        expanded_rows: Expanded duplicate rows per selected media.

    Returns:
        Exit code from the interactive DuckDB process.
    """
    with tempfile.TemporaryDirectory(prefix="czk-analyze-") as tmp_dir:
        temp_dir = Path(tmp_dir)

        inventory_csv_path = temp_dir / "media_inventory.csv"
        _write_csv(
            inventory_csv_path,
            [
                "media_type",
                "path",
                "file_name",
                "extension",
                "size_bytes",
                "modified_epoch",
            ],
            [asdict(row) for row in inventory_rows],
        )

        expanded_csv_paths: dict[MediaType, Path] = {}
        for media, rows in expanded_rows.items():
            expanded_csv_path = temp_dir / f"duplicates_{media}_expanded.csv"
            _write_csv(
                expanded_csv_path,
                [
                    "group_index",
                    "file_to_keep",
                    "remove_path",
                    "remove_ordinal",
                    "group_remove_count",
                ],
                [asdict(row) for row in rows],
            )
            expanded_csv_paths[media] = expanded_csv_path

        duplicate_json_csv_paths: dict[MediaType, Path] = {}
        for media, json_path in duplicate_json_paths.items():
            json_rows = build_json_rows(json_path)
            json_csv_path = temp_dir / f"duplicates_{media}_json.csv"
            _write_csv(
                json_csv_path,
                [
                    "group_index",
                    "item_index",
                    "path",
                    "size_bytes",
                    "modified_date",
                    "raw_item_json",
                    "source_report",
                ],
                [asdict(row) for row in json_rows],
            )
            duplicate_json_csv_paths[media] = json_csv_path

        init_sql_path = temp_dir / "duckdb_init.sql"
        init_sql_path.write_text(
            _build_init_sql(
                media_targets=media_targets,
                inventory_csv_path=inventory_csv_path,
                duplicate_csv_paths=duplicate_csv_paths,
                duplicate_json_csv_paths=duplicate_json_csv_paths,
                expanded_csv_paths=expanded_csv_paths,
            ),
            encoding="utf-8",
        )

        null_device = "NUL" if os.name == "nt" else "/dev/null"
        init_sql_arg = str(init_sql_path).replace('"', '""')
        completed = subprocess.run(
            [
                duckdb_executable,
                ":memory:",
                "-interactive",
                "-cmd",
                f".output {null_device}",
                "-cmd",
                f'.read "{init_sql_arg}"',
                "-cmd",
                ".output stdout",
            ],
            check=False,
        )
        return completed.returncode
