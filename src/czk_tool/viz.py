from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .counting import MediaType
from .report import DuplicateVisualRow, MediaSummary


@dataclass(frozen=True)
class MediaItemMetadata:
    size_bytes: int | None = None
    modified_epoch: int | None = None
    width: int | None = None
    height: int | None = None


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
    metadata_by_path: dict[str, MediaItemMetadata]


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
    if not path_value:
        return False
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
    if not path_value:
        return None
    try:
        return Path(path_value).expanduser().resolve(strict=False).as_uri()
    except ValueError:
        return None


def _parent_uri(path_value: str) -> str | None:
    """Convert the parent directory of a path to a `file://` URI.

    Args:
        path_value: Filesystem path string.

    Returns:
        Parent folder URI when conversion succeeds, else `None`.
    """
    if not path_value:
        return None
    try:
        return Path(path_value).expanduser().resolve(strict=False).parent.as_uri()
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
        f'<a href="{_escape(uri)}" target="_blank" rel="noreferrer"><code>{path_text}</code></a></div>'
    )


def _format_size(size_bytes: int | None) -> str:
    """Format bytes into a compact human-readable string.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Human-readable size string, or `-` when unavailable.
    """
    if size_bytes is None or size_bytes < 0:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size_bytes)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(value):,} {units[unit_index]}"
    return f"{value:.1f} {units[unit_index]}"


def _format_modified(modified_epoch: int | None) -> str:
    """Format a unix epoch into local readable datetime text.

    Args:
        modified_epoch: Unix epoch seconds (or milliseconds).

    Returns:
        Formatted datetime string, or `-` when unavailable/invalid.
    """
    if modified_epoch is None or modified_epoch <= 0:
        return "-"
    timestamp = float(modified_epoch)
    if timestamp > 10_000_000_000:
        timestamp /= 1000
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return "-"


def _format_resolution(media: MediaType, metadata: MediaItemMetadata | None) -> str:
    """Format the resolution text for one media item.

    Args:
        media: Media class (`images` or `videos`).
        metadata: Optional metadata payload for the item.

    Returns:
        Resolution text for images when available, otherwise `-`.
    """
    if media != "images" or metadata is None:
        return "-"
    if metadata.width is None or metadata.height is None:
        return "-"
    if metadata.width <= 0 or metadata.height <= 0:
        return "-"
    return f"{metadata.width}x{metadata.height}"


def _render_media_metadata(media: MediaType, metadata: MediaItemMetadata | None) -> str:
    """Render metadata lines for one media item.

    Args:
        media: Media class (`images` or `videos`).
        metadata: Optional metadata payload for the item.

    Returns:
        HTML metadata fragment.
    """
    size_text = _escape(_format_size(None if metadata is None else metadata.size_bytes))
    modified_text = _escape(_format_modified(None if metadata is None else metadata.modified_epoch))
    resolution_text = _escape(_format_resolution(media, metadata))
    return (
        '<div class="media-details">'
        f"<span><strong>Size:</strong> {size_text}</span>"
        f"<span><strong>Modified:</strong> {modified_text}</span>"
        f"<span><strong>Resolution:</strong> {resolution_text}</span>"
        "</div>"
    )


def _render_media_actions(path_value: str) -> str:
    """Render open/reveal links for one media item.

    Args:
        path_value: Filesystem path for the media item.

    Returns:
        HTML actions fragment, or an empty string when no actions are available.
    """
    open_uri = _path_uri(path_value)
    reveal_uri = _parent_uri(path_value)
    links: list[str] = []
    if open_uri is not None:
        links.append(
            f'<a class="media-link" href="{_escape(open_uri)}" target="_blank" rel="noreferrer">Open</a>'
        )
    if reveal_uri is not None:
        links.append(
            f'<a class="media-link" href="{_escape(reveal_uri)}" target="_blank" rel="noreferrer">Reveal</a>'
        )
    if not links:
        return ""
    return '<div class="media-actions">' + "".join(links) + "</div>"


def _render_media_item(
    *,
    path_value: str,
    media: MediaType,
    metadata_by_path: dict[str, MediaItemMetadata],
) -> str:
    """Render one media preview card.

    Args:
        path_value: File path shown in the card.
        media: Media class (`images` or `videos`).
        metadata_by_path: Metadata lookup keyed by absolute file path.

    Returns:
        HTML fragment representing the media item.
    """
    metadata = metadata_by_path.get(path_value)
    file_name = Path(path_value).name or "(missing file name)"
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

    actions_html = _render_media_actions(path_value)
    metadata_html = _render_media_metadata(media, metadata)
    return (
        '<div class="media-item">'
        f'<div class="media-preview">{preview_html}</div>'
        '<div class="media-meta">'
        f'<div class="media-name">{file_name_text}</div>'
        f"{actions_html}"
        f"{metadata_html}"
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


def _render_card_controls(section_dom_id: str) -> str:
    """Render Show all / Collapse all controls for one media section.

    Args:
        section_dom_id: DOM id for the duplicate-card container.

    Returns:
        HTML controls fragment.
    """
    return (
        '<div class="card-controls">'
        f'<button type="button" class="control-btn" onclick="czkToggleCards(\'{section_dom_id}\', true)">Show all</button>'
        f'<button type="button" class="control-btn" onclick="czkToggleCards(\'{section_dom_id}\', false)">Collapse all</button>'
        "</div>"
    )


def _render_duplicate_cards(
    *,
    section_dom_id: str,
    rows: list[DuplicateVisualRow],
    media: MediaType,
    metadata_by_path: dict[str, MediaItemMetadata],
) -> str:
    """Render duplicate groups as collapsible cards.

    Args:
        section_dom_id: DOM id for the card container.
        rows: Duplicate rows selected for visualization.
        media: Media class for preview controls.
        metadata_by_path: Metadata lookup keyed by absolute file path.

    Returns:
        HTML content containing all duplicate cards.
    """
    cards: list[str] = []
    for row in rows:
        keep_name = _escape(Path(row.file_to_keep).name or row.file_to_keep or "-")
        keep_html = _render_media_item(
            path_value=row.file_to_keep,
            media=media,
            metadata_by_path=metadata_by_path,
        )
        remove_items = "".join(
            _render_media_item(
                path_value=remove_path,
                media=media,
                metadata_by_path=metadata_by_path,
            )
            for remove_path in row.files_to_remove
        )
        remove_html = (
            f'<div class="remove-items">{remove_items}</div>'
            if remove_items
            else '<p class="empty-inline">No files marked for removal.</p>'
        )
        cards.append(
            '<details class="dup-card">'
            '<summary class="dup-card-summary">'
            f'<span class="summary-chip"><strong>Group:</strong> {row.index}</span>'
            f'<span class="summary-chip"><strong>Keep File:</strong> {keep_name}</span>'
            f'<span class="summary-chip"><strong>Marked for Removal:</strong> {row.remove_count}</span>'
            "</summary>"
            '<div class="dup-card-body">'
            '<div class="dup-card-section">'
            "<h4>Keep File</h4>"
            f"{keep_html}"
            "</div>"
            '<div class="dup-card-section">'
            "<h4>Files to Remove</h4>"
            f"{remove_html}"
            "</div>"
            "</div>"
            "</details>"
        )
    return f'<div id="{_escape(section_dom_id)}" class="dup-cards">{"".join(cards)}</div>'


def _render_media_section(section: VizMediaSection, section_index: int) -> str:
    """Render one media section in the HTML report.

    Args:
        section: Media-specific report content.
        section_index: 1-based section index for stable DOM ids.

    Returns:
        HTML section markup.
    """
    subtitle = f"Showing {section.shown_rows} of {section.total_rows} duplicate groups"
    section_dom_id = f"dup-cards-{section.media}-{section_index}"
    cards_html = _render_duplicate_cards(
        section_dom_id=section_dom_id,
        rows=section.visual_rows,
        media=section.media,
        metadata_by_path=section.metadata_by_path,
    )
    controls_html = _render_card_controls(section_dom_id)
    if not section.visual_rows:
        cards_html = '<p class="empty">(no duplicate rows)</p>'
        controls_html = ""

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
        f"{controls_html}"
        f"{cards_html}"
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
    rendered_sections = "".join(
        _render_media_section(section, index) for index, section in enumerate(media_sections, start=1)
    )
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
        "h4{margin:0 0 8px;font-size:14px;color:#243447;}"
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
        ".card-controls{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 12px;}"
        ".control-btn{border:1px solid #ccd5e1;background:#f8fafc;color:#0f2742;border-radius:8px;padding:6px 10px;font-size:13px;cursor:pointer;}"
        ".control-btn:hover{background:#edf2f8;}"
        ".dup-cards{display:grid;gap:10px;}"
        ".dup-card{border:1px solid #d7dee8;border-radius:10px;background:#fdfefe;overflow:hidden;}"
        ".dup-card-summary{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:10px 12px;cursor:pointer;background:#f6f9fc;}"
        ".summary-chip{border:1px solid #d7dee8;border-radius:999px;padding:3px 8px;background:#ffffff;font-size:12px;line-height:1.4;}"
        ".dup-card-body{padding:12px;display:grid;gap:12px;}"
        ".dup-card-section{display:grid;gap:8px;}"
        ".media-item{display:grid;grid-template-columns:160px minmax(220px,1fr);gap:10px;padding:8px;border:1px solid #e3e8ef;border-radius:8px;background:#fcfdff;}"
        ".media-preview{width:160px;height:110px;background:#f0f3f7;border-radius:6px;display:flex;align-items:center;justify-content:center;overflow:hidden;}"
        ".media-preview img,.media-preview video{width:100%;height:100%;object-fit:cover;display:block;}"
        ".preview-unavailable{font-size:12px;color:#44566a;padding:8px;text-align:center;}"
        ".media-meta{min-width:0;display:grid;gap:6px;align-content:start;}"
        ".media-name{font-weight:700;word-break:break-word;}"
        ".media-actions{display:flex;gap:10px;flex-wrap:wrap;}"
        ".media-link{font-size:12px;}"
        ".media-details{display:grid;gap:4px;font-size:12px;color:#33495f;}"
        ".remove-items{display:grid;gap:8px;}"
        ".empty{padding:12px;border:1px dashed #b8c4d3;border-radius:8px;background:#f9fbfd;color:#44566a;}"
        ".empty-inline{margin:0;padding:8px;border:1px dashed #b8c4d3;border-radius:8px;background:#f9fbfd;color:#44566a;}"
        "@media (max-width:900px){"
        "main{padding:12px;}"
        ".overview-grid{grid-template-columns:1fr;}"
        ".media-item{grid-template-columns:1fr;}"
        ".media-preview{width:100%;height:220px;}"
        "}"
        "</style>"
        "</head>"
        "<body>"
        "<main>"
        '<section class="overview">'
        "<h1>czk viz report</h1>"
        '<div class="overview-grid">'
        f'<div class="label">Run Mode</div><div class="value">{_escape(run_context.run_mode)}</div>'
        f'<div class="label">Target Folder</div><div class="value">{_escape(str(run_context.target_dir))}</div>'
        f'<div class="label">Reports Folder</div><div class="value">{_escape(str(run_context.out_dir))}</div>'
        f'<div class="label">Run Timestamp</div><div class="value">{_escape(run_context.timestamp)}</div>'
        f'<div class="label">Media Types</div><div class="value">{_escape(media_labels)}</div>'
        "</div>"
        "</section>"
        f"{rendered_sections}"
        "</main>"
        "<script>"
        "function czkToggleCards(sectionId, shouldOpen) {"
        "  const container = document.getElementById(sectionId);"
        "  if (!container) { return; }"
        "  container.querySelectorAll('.dup-card').forEach((card) => { card.open = shouldOpen; });"
        "}"
        "</script>"
        "</body>"
        "</html>"
    )
