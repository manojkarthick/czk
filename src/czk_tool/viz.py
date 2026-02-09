from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from .counting import MediaType
from .report import DuplicateVisualRow, MediaSummary


@dataclass(frozen=True)
class VizRunContext:
    run_mode: str
    target_dir: Path
    out_dir: Path
    timestamp: str
    media_targets: list[MediaType]


@dataclass(frozen=True)
class VizMediaSection:
    media: MediaType
    command_preview: str
    exit_code: int
    summary: MediaSummary
    json_path: Path
    csv_path: Path
    visual_rows: list[DuplicateVisualRow]
    shown_rows: int
    total_rows: int


def _escape(value: str) -> str:
    """Escape text for safe HTML rendering.

    Args:
        value: Raw string to escape.

    Returns:
        HTML-escaped string.
    """
    return html.escape(value, quote=True)


def _format_number(value: int) -> str:
    """Format an integer using thousands separators.

    Args:
        value: Integer value to format.

    Returns:
        Comma-delimited number text.
    """
    return f"{value:,}"


def _path_exists(path_value: str) -> bool:
    """Check whether a path exists.

    Args:
        path_value: Candidate filesystem path.

    Returns:
        `True` when path exists, otherwise `False`.
    """
    try:
        return Path(path_value).exists()
    except OSError:
        return False


def _path_uri(path_value: str) -> str | None:
    """Convert a path string to a `file://` URI.

    Args:
        path_value: Filesystem path string.

    Returns:
        URI string when conversion succeeds, else `None`.
    """
    try:
        return Path(path_value).expanduser().resolve(strict=False).as_uri()
    except ValueError:
        return None


def _artifact_uri(path: Path) -> str | None:
    """Convert a path object to a `file://` URI.

    Args:
        path: Path to convert.

    Returns:
        URI string when conversion succeeds, else `None`.
    """
    try:
        return path.resolve(strict=False).as_uri()
    except ValueError:
        return None


def _render_artifact_link(path: Path, label: str) -> str:
    """Render artifact text with an optional file URI link.

    Args:
        path: Artifact path.
        label: User-facing label.

    Returns:
        HTML fragment for artifact entry.
    """
    path_text = _escape(str(path))
    uri = _artifact_uri(path)
    if uri is None:
        return f"<div><strong>{_escape(label)}:</strong> <code>{path_text}</code></div>"
    return (
        f"<div><strong>{_escape(label)}:</strong> "
        f"<a href=\"{_escape(uri)}\" target=\"_blank\" rel=\"noreferrer\"><code>{path_text}</code></a></div>"
    )


def _render_media_item(path_value: str, media: MediaType) -> str:
    """Render one media preview card.

    Args:
        path_value: File path shown in the card.
        media: Media class (`images` or `videos`).

    Returns:
        HTML fragment representing the media item.
    """
    file_name = Path(path_value).name or path_value
    path_text = _escape(path_value)
    file_name_text = _escape(file_name)
    uri = _path_uri(path_value)

    preview_html = '<div class="preview-unavailable">Preview unavailable</div>'
    if uri is not None and _path_exists(path_value):
        if media == "images":
            preview_html = f'<img src="{_escape(uri)}" alt="{file_name_text}" loading="lazy">'
        else:
            preview_html = (
                '<video controls preload="metadata" muted>'
                f'<source src="{_escape(uri)}">'
                "</video>"
            )

    link_html = ""
    if uri is not None:
        link_html = (
            f'<a class="media-link" href="{_escape(uri)}" target="_blank" rel="noreferrer">open</a>'
        )

    return (
        '<div class="media-item">'
        f'<div class="media-preview">{preview_html}</div>'
        '<div class="media-meta">'
        f'<div class="media-name">{file_name_text}</div>'
        f'<div class="media-path">{path_text}</div>'
        f"{link_html}"
        "</div>"
        "</div>"
    )


def _render_summary(summary: MediaSummary) -> str:
    """Render the summary metrics section for one media block.

    Args:
        summary: Aggregate media summary values.

    Returns:
        HTML fragment for the summary list.
    """
    rows = [
        ("Total Files Scanned", _format_number(summary.total_found)),
        ("Duplicate Groups Found", _format_number(summary.duplicate_groups)),
        ("Files Marked for Removal", _format_number(summary.duplicates_to_remove)),
        ("Estimated Files Remaining", _format_number(summary.after_remove_estimate)),
    ]
    rendered_rows = [
        (
            '<div class="summary-row">'
            f'<span class="summary-label">{_escape(label)}</span>'
            f'<span class="summary-value">{_escape(value)}</span>'
            "</div>"
        )
        for label, value in rows
    ]
    return '<div class="summary-block">' + "".join(rendered_rows) + "</div>"


def _render_duplicate_rows(rows: list[DuplicateVisualRow], media: MediaType) -> str:
    """Render duplicate table rows for one media section.

    Args:
        rows: Duplicate rows selected for visualization.
        media: Media class for preview controls.

    Returns:
        HTML table body content.
    """
    rendered_rows: list[str] = []
    for row in rows:
        keep_html = _render_media_item(row.file_to_keep, media)
        remove_items = "".join(
            _render_media_item(remove_path, media) for remove_path in row.files_to_remove
        )
        removes_html = f'<div class="remove-items">{remove_items}</div>' if remove_items else "-"
        rendered_rows.append(
            "<tr>"
            f"<td>{row.index}</td>"
            f"<td>{keep_html}</td>"
            f"<td>{row.remove_count}</td>"
            f"<td>{removes_html}</td>"
            "</tr>"
        )
    return "".join(rendered_rows)


def _render_media_section(section: VizMediaSection) -> str:
    """Render one media section in the HTML report.

    Args:
        section: Media-specific report content.

    Returns:
        HTML section markup.
    """
    subtitle = f"Showing {section.shown_rows} of {section.total_rows} duplicate groups"
    if section.visual_rows:
        table_html = (
            '<div class="table-wrap"><table class="duplicate-table">'
            "<thead>"
            "<tr>"
            "<th>index</th>"
            "<th>file_to_keep</th>"
            "<th>remove_count</th>"
            "<th>files_to_remove</th>"
            "</tr>"
            "</thead>"
            f"<tbody>{_render_duplicate_rows(section.visual_rows, section.media)}</tbody>"
            "</table></div>"
        )
    else:
        table_html = '<p class="empty">(no duplicate rows)</p>'

    return (
        '<section class="media-section">'
        f"<h2>{_escape(section.media.upper())} | {_escape('DRY RUN')}</h2>"
        f'<div class="command-block"><h3>Command</h3><pre>{_escape(section.command_preview)}</pre></div>'
        f'<p class="exit-code">Scanner Exit Code: {section.exit_code}</p>'
        f"{_render_summary(section.summary)}"
        '<div class="artifact-block">'
        f"{_render_artifact_link(section.json_path, 'JSON Report')}"
        f"{_render_artifact_link(section.csv_path, 'CSV Report')}"
        "</div>"
        f'<p class="preview-count">{_escape(subtitle)}</p>'
        f"{table_html}"
        "</section>"
    )


def build_html_report(
    *,
    run_context: VizRunContext,
    media_sections: list[VizMediaSection],
) -> str:
    """Build the complete self-contained HTML report document.

    Args:
        run_context: Run-level metadata rendered in the overview section.
        media_sections: Media-specific sections rendered in order.

    Returns:
        Full HTML content.
    """
    media_labels = ", ".join(run_context.media_targets)
    rendered_sections = "".join(_render_media_section(section) for section in media_sections)
    return (
        "<!doctype html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>czk viz report</title>"
        "<style>"
        "body{margin:0;background:#f4f6f8;color:#1a1a1a;font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;}"
        "main{max-width:1280px;margin:0 auto;padding:24px;}"
        "h1{margin:0 0 16px;font-size:28px;}"
        "h2{margin:0 0 12px;font-size:20px;}"
        "h3{margin:0 0 8px;font-size:14px;color:#243447;text-transform:uppercase;letter-spacing:0.04em;}"
        ".overview,.media-section{background:#fff;border:1px solid #dde3ea;border-radius:12px;padding:16px 18px;margin-bottom:16px;}"
        ".overview-grid{display:grid;grid-template-columns:220px 1fr;gap:8px 12px;align-items:start;}"
        ".label{font-weight:700;color:#0f2742;}"
        ".value{word-break:break-word;}"
        ".command-block pre{margin:0;padding:10px;border-radius:8px;background:#f2f5f9;border:1px solid #d7dee8;overflow:auto;}"
        ".exit-code,.preview-count{font-weight:600;color:#0f2742;}"
        ".summary-block{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;margin:12px 0;}"
        ".summary-row{display:flex;justify-content:space-between;gap:8px;padding:8px 10px;border:1px solid #d7dee8;border-radius:8px;background:#fbfcfd;}"
        ".summary-label{font-weight:600;}"
        ".summary-value{font-weight:700;}"
        ".artifact-block{display:flex;flex-direction:column;gap:6px;margin:8px 0 12px;}"
        ".table-wrap{overflow:auto;border:1px solid #d7dee8;border-radius:10px;}"
        ".duplicate-table{width:100%;border-collapse:collapse;min-width:980px;}"
        ".duplicate-table th,.duplicate-table td{padding:10px;border-bottom:1px solid #e6ebf1;vertical-align:top;text-align:left;}"
        ".duplicate-table th{background:#f7f9fc;font-weight:700;position:sticky;top:0;}"
        ".media-item{display:grid;grid-template-columns:160px minmax(220px,1fr);gap:10px;padding:8px;border:1px solid #e3e8ef;border-radius:8px;background:#fcfdff;}"
        ".media-preview{width:160px;height:110px;background:#f0f3f7;border-radius:6px;display:flex;align-items:center;justify-content:center;overflow:hidden;}"
        ".media-preview img,.media-preview video{width:100%;height:100%;object-fit:cover;display:block;}"
        ".preview-unavailable{font-size:12px;color:#44566a;padding:8px;text-align:center;}"
        ".media-meta{min-width:0;}"
        ".media-name{font-weight:700;word-break:break-word;}"
        ".media-path{font-size:12px;color:#44566a;word-break:break-word;margin:4px 0;}"
        ".media-link{font-size:12px;}"
        ".remove-items{display:grid;gap:8px;}"
        ".empty{padding:12px;border:1px dashed #b8c4d3;border-radius:8px;background:#f9fbfd;color:#44566a;}"
        "@media (max-width:900px){"
        "main{padding:12px;}"
        ".overview-grid{grid-template-columns:1fr;}"
        ".media-item{grid-template-columns:1fr;}"
        ".media-preview{width:100%;height:220px;}"
        ".duplicate-table{min-width:760px;}"
        "}"
        "</style>"
        "</head>"
        "<body>"
        "<main>"
        "<section class=\"overview\">"
        "<h1>czk viz report</h1>"
        "<div class=\"overview-grid\">"
        f'<div class="label">Run Mode</div><div class="value">{_escape(run_context.run_mode)}</div>'
        f'<div class="label">Target Folder</div><div class="value">{_escape(str(run_context.target_dir))}</div>'
        f'<div class="label">Reports Folder</div><div class="value">{_escape(str(run_context.out_dir))}</div>'
        f'<div class="label">Run Timestamp</div><div class="value">{_escape(run_context.timestamp)}</div>'
        f'<div class="label">Media Types</div><div class="value">{_escape(media_labels)}</div>'
        "</div>"
        "</section>"
        f"{rendered_sections}"
        "</main>"
        "</body>"
        "</html>"
    )
