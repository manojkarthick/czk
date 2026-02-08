from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Mode = Literal["test", "execute"]

CSV_COLUMNS = ["#", "file_to_keep", "files_to_remove", "count"]


@dataclass(frozen=True)
class DuplicateRow:
    index: int
    file_to_keep: str
    files_to_remove: list[str]
    count: int


@dataclass(frozen=True)
class DuplicatePreviewRow:
    index: int
    file_to_keep: str
    remove_count: int
    first_remove: str


@dataclass(frozen=True)
class MediaSummary:
    total_found: int
    duplicate_groups: int
    duplicates_to_remove: int
    after_remove_estimate: int


def load_duplicate_groups(pretty_json_path: Path) -> list[list[dict[str, Any]]]:
    try:
        raw_data = json.loads(pretty_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {pretty_json_path} ({exc})") from exc

    if not isinstance(raw_data, list):
        raise ValueError(f"Expected top-level array in {pretty_json_path}.")

    groups: list[list[dict[str, Any]]] = []
    for index, raw_group in enumerate(raw_data, start=1):
        if not isinstance(raw_group, list):
            raise ValueError(f"Expected group #{index} to be an array in {pretty_json_path}.")
        parsed_group: list[dict[str, Any]] = []
        for item_index, raw_item in enumerate(raw_group, start=1):
            if not isinstance(raw_item, dict):
                raise ValueError(
                    f"Expected group #{index} item #{item_index} to be an object in {pretty_json_path}."
                )
            path_value = raw_item.get("path")
            if not isinstance(path_value, str) or not path_value:
                raise ValueError(
                    f"Expected string 'path' in group #{index} item #{item_index} in {pretty_json_path}."
                )
            parsed_group.append(raw_item)
        groups.append(parsed_group)
    return groups


def _path_value(item: dict[str, Any]) -> str:
    path = item.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError("Each duplicate record must include a non-empty string 'path'.")
    return path


def _size_value(item: dict[str, Any]) -> int:
    size = item.get("size")
    if isinstance(size, int):
        return size
    if isinstance(size, float):
        return int(size)
    return 0


def _modified_date_value(item: dict[str, Any]) -> int:
    modified_date = item.get("modified_date")
    if isinstance(modified_date, int):
        return modified_date
    if isinstance(modified_date, float):
        return int(modified_date)
    return 0


def _project_group_aeb(group: list[dict[str, Any]]) -> tuple[str, list[str]]:
    ordered = sorted(
        group,
        key=lambda item: (
            -_size_value(item),
            _modified_date_value(item),
            _path_value(item),
        ),
    )
    keep = _path_value(ordered[0])
    remove = [_path_value(item) for item in ordered[1:]]
    return keep, remove


def _exists(path: str) -> bool:
    try:
        return Path(path).exists()
    except OSError:
        return False


def _resolve_execute_group(group: list[dict[str, Any]]) -> tuple[str, list[str]]:
    projected_keep, projected_remove = _project_group_aeb(group)
    all_paths = [_path_value(item) for item in group]
    existing = [path for path in all_paths if _exists(path)]
    removed = [path for path in all_paths if path not in existing]

    # Only treat as authoritative when exactly one file remains and at least one is gone.
    if len(existing) == 1 and removed:
        keep = existing[0]
        remove = sorted(removed)
        return keep, remove
    return projected_keep, projected_remove


def build_rows(groups: list[list[dict[str, Any]]], mode: Mode) -> list[DuplicateRow]:
    rows: list[DuplicateRow] = []
    for group in groups:
        if not group:
            continue
        if mode == "execute":
            file_to_keep, files_to_remove = _resolve_execute_group(group)
        else:
            file_to_keep, files_to_remove = _project_group_aeb(group)

        row = DuplicateRow(
            index=0,
            file_to_keep=file_to_keep,
            files_to_remove=files_to_remove,
            count=len(files_to_remove),
        )
        rows.append(row)

    rows.sort(key=lambda row: (-row.count, row.file_to_keep))
    return [
        DuplicateRow(
            index=index,
            file_to_keep=row.file_to_keep,
            files_to_remove=row.files_to_remove,
            count=row.count,
        )
        for index, row in enumerate(rows, start=1)
    ]


def write_csv(rows: list[DuplicateRow], csv_path: Path) -> None:
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "#": row.index,
                    "file_to_keep": row.file_to_keep,
                    "files_to_remove": json.dumps(row.files_to_remove, ensure_ascii=False),
                    "count": row.count,
                }
            )


def preview_row_from_duplicate_row(row: DuplicateRow) -> DuplicatePreviewRow:
    first_remove = row.files_to_remove[0] if row.files_to_remove else "-"
    return DuplicatePreviewRow(
        index=row.index,
        file_to_keep=row.file_to_keep,
        remove_count=row.count,
        first_remove=first_remove,
    )


def build_summary(total_found: int, duplicate_groups: int, rows: list[DuplicateRow]) -> MediaSummary:
    duplicates_to_remove = sum(row.count for row in rows)
    after_remove_estimate = max(0, total_found - duplicates_to_remove)
    return MediaSummary(
        total_found=total_found,
        duplicate_groups=duplicate_groups,
        duplicates_to_remove=duplicates_to_remove,
        after_remove_estimate=after_remove_estimate,
    )


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_remove_list(raw_value: str) -> list[str]:
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def build_preview_rows_from_csv(
    csv_path: Path,
    top: int,
) -> tuple[list[DuplicatePreviewRow], int, int]:
    rows = _read_csv_rows(csv_path)
    total_rows = len(rows)
    shown_rows = rows[: max(0, top)]

    preview_rows: list[DuplicatePreviewRow] = []
    for ordinal, row in enumerate(shown_rows, start=1):
        files_to_remove = _parse_remove_list(row.get("files_to_remove", "[]"))
        parsed_row = DuplicateRow(
            index=_parse_int(row.get("#", ""), ordinal),
            file_to_keep=row.get("file_to_keep", ""),
            files_to_remove=files_to_remove,
            count=_parse_int(row.get("count", ""), len(files_to_remove)),
        )
        preview_rows.append(preview_row_from_duplicate_row(parsed_row))

    return preview_rows, total_rows, len(preview_rows)


def _clip(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 3:
        return value[:width]
    return f"{value[: width - 3]}..."


def build_pretty_table_from_csv(csv_path: Path, top: int) -> tuple[str, int, int]:
    rows = _read_csv_rows(csv_path)
    total_rows = len(rows)
    shown_rows = rows[: max(0, top)]

    if not shown_rows:
        return "(no duplicate rows)", total_rows, 0

    widths = {
        "#": 4,
        "file_to_keep": 70,
        "files_to_remove": 90,
        "count": 6,
    }
    for row in shown_rows:
        widths["#"] = max(widths["#"], min(6, len(row["#"])))
        widths["file_to_keep"] = max(
            widths["file_to_keep"], min(100, len(row["file_to_keep"]))
        )
        widths["files_to_remove"] = max(
            widths["files_to_remove"], min(140, len(row["files_to_remove"]))
        )
        widths["count"] = max(widths["count"], min(10, len(row["count"])))

    def format_row(values: dict[str, str]) -> str:
        return (
            f"{_clip(values['#'], widths['#']):<{widths['#']}} | "
            f"{_clip(values['file_to_keep'], widths['file_to_keep']):<{widths['file_to_keep']}} | "
            f"{_clip(values['files_to_remove'], widths['files_to_remove']):<{widths['files_to_remove']}} | "
            f"{_clip(values['count'], widths['count']):<{widths['count']}}"
        )

    header_values = {
        "#": "#",
        "file_to_keep": "file_to_keep",
        "files_to_remove": "files_to_remove",
        "count": "count",
    }
    header = format_row(header_values)
    separator = (
        f"{'-' * widths['#']}-+-"
        f"{'-' * widths['file_to_keep']}-+-"
        f"{'-' * widths['files_to_remove']}-+-"
        f"{'-' * widths['count']}"
    )
    body = [format_row(row) for row in shown_rows]
    table = "\n".join([header, separator, *body])
    return table, total_rows, len(shown_rows)
