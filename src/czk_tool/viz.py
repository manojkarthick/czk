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
    """Render an open link for one media item.

    Args:
        path_value: Filesystem path for the media item.

    Returns:
        HTML actions fragment, or an empty string when no actions are available.
    """
    open_uri = _path_uri(path_value)
    links: list[str] = []
    if open_uri is not None:
        links.append(
            f'<a class="media-link" href="{_escape(open_uri)}" target="_blank" rel="noopener noreferrer" onclick="return czkOpenBackground(event)">Open</a>'
        )
    if not links:
        return ""
    return '<div class="media-actions">' + "".join(links) + "</div>"


def _file_name_for_search(path_value: str) -> str:
    """Return a normalized filename token for card search indexing.

    Args:
        path_value: File path string from a duplicate row.

    Returns:
        Lowercase filename text used for partial-match lookup.
    """
    file_name = Path(path_value).name or path_value
    return file_name.strip().lower()


def _build_search_index(row: DuplicateVisualRow) -> str:
    """Build searchable filename text for one duplicate card.

    Args:
        row: Duplicate row containing keep/remove file paths.

    Returns:
        Lowercase search text with keep and remove filenames.
    """
    names: list[str] = []
    keep_name = _file_name_for_search(row.file_to_keep)
    if keep_name:
        names.append(keep_name)
    names.extend(
        name
        for name in (_file_name_for_search(remove_path) for remove_path in row.files_to_remove)
        if name
    )
    return " ".join(names)


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


def _render_search_controls(section_dom_id: str, search_input_id: str) -> str:
    """Render filename search controls for one media section.

    Args:
        section_dom_id: DOM id for the duplicate-card container.
        search_input_id: DOM id for the section search input.

    Returns:
        HTML controls fragment for card filtering.
    """
    return (
        '<div class="search-controls">'
        f'<label class="search-label" for="{_escape(search_input_id)}">Search filenames</label>'
        f'<input id="{_escape(search_input_id)}" class="search-input" type="search" '
        'placeholder="Partial match across keep and remove files" '
        f'oninput="czkFilterCards(\'{section_dom_id}\', \'{search_input_id}\', \'{section_dom_id}-page-size\', \'{section_dom_id}-page-status\', \'{section_dom_id}-page-first\', \'{section_dom_id}-page-prev\', \'{section_dom_id}-page-next\', \'{section_dom_id}-page-last\')">'
        f'<button type="button" class="control-btn" onclick="czkClearCardSearch(\'{section_dom_id}\', \'{search_input_id}\', \'{section_dom_id}-page-size\', \'{section_dom_id}-page-status\', \'{section_dom_id}-page-first\', \'{section_dom_id}-page-prev\', \'{section_dom_id}-page-next\', \'{section_dom_id}-page-last\')">Clear</button>'
        "</div>"
    )


def _render_pagination_controls(section_dom_id: str, total_cards: int) -> str:
    """Render pagination controls for one media section.

    Args:
        section_dom_id: DOM id for the duplicate-card container.
        total_cards: Number of duplicate-group cards in the section.

    Returns:
        HTML controls fragment for pagination.
    """
    default_page_size = 25
    total_pages = max(1, (total_cards + default_page_size - 1) // default_page_size)
    prev_disabled_attr = " disabled"
    next_disabled_attr = " disabled" if total_pages <= 1 else ""
    page_size_id = f"{section_dom_id}-page-size"
    page_status_id = f"{section_dom_id}-page-status"
    page_first_id = f"{section_dom_id}-page-first"
    page_prev_id = f"{section_dom_id}-page-prev"
    page_next_id = f"{section_dom_id}-page-next"
    page_last_id = f"{section_dom_id}-page-last"
    return (
        '<div class="pagination-controls">'
        f'<label class="search-label" for="{_escape(page_size_id)}">Items per page</label>'
        f'<select id="{_escape(page_size_id)}" class="page-size-select" '
        f'onchange="czkFilterCards(\'{section_dom_id}\', \'{section_dom_id}-search\', \'{page_size_id}\', \'{page_status_id}\', \'{page_first_id}\', \'{page_prev_id}\', \'{page_next_id}\', \'{page_last_id}\')">'
        '<option value="25" selected>25</option>'
        '<option value="50">50</option>'
        '<option value="100">100</option>'
        "</select>"
        f'<button type="button" id="{_escape(page_first_id)}" class="control-btn" '
        f'onclick="czkJumpPage(\'{section_dom_id}\', \'{section_dom_id}-search\', \'{page_size_id}\', \'{page_status_id}\', \'{page_first_id}\', \'{page_prev_id}\', \'{page_next_id}\', \'{page_last_id}\', \'first\')"{prev_disabled_attr}>First</button>'
        f'<button type="button" id="{_escape(page_prev_id)}" class="control-btn" '
        f'onclick="czkChangePage(\'{section_dom_id}\', \'{section_dom_id}-search\', \'{page_size_id}\', \'{page_status_id}\', \'{page_first_id}\', \'{page_prev_id}\', \'{page_next_id}\', \'{page_last_id}\', -1)"{prev_disabled_attr}>Previous</button>'
        f'<button type="button" id="{_escape(page_next_id)}" class="control-btn" '
        f'onclick="czkChangePage(\'{section_dom_id}\', \'{section_dom_id}-search\', \'{page_size_id}\', \'{page_status_id}\', \'{page_first_id}\', \'{page_prev_id}\', \'{page_next_id}\', \'{page_last_id}\', 1)"{next_disabled_attr}>Next</button>'
        f'<button type="button" id="{_escape(page_last_id)}" class="control-btn" '
        f'onclick="czkJumpPage(\'{section_dom_id}\', \'{section_dom_id}-search\', \'{page_size_id}\', \'{page_status_id}\', \'{page_first_id}\', \'{page_prev_id}\', \'{page_next_id}\', \'{page_last_id}\', \'last\')"{next_disabled_attr}>Last</button>'
        f'<span id="{_escape(page_status_id)}" class="page-status">Page 1 of {total_pages}</span>'
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
    for card_position, row in enumerate(rows, start=1):
        keep_name = _escape(Path(row.file_to_keep).name or row.file_to_keep or "-")
        search_index = _escape(_build_search_index(row))
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
        hidden_attr = " hidden" if card_position > 25 else ""
        cards.append(
            f'<details class="dup-card" data-group-index="{row.index}" data-search="{search_index}"{hidden_attr}>'
            '<summary class="dup-card-summary">'
            f'<span class="summary-chip"><strong>Group:</strong> {row.index}</span>'
            f'<span class="summary-chip"><strong>File to Keep:</strong> {keep_name}</span>'
            f'<span class="summary-chip"><strong>Marked for Removal:</strong> {row.remove_count}</span>'
            "</summary>"
            '<div class="dup-card-body">'
            '<div class="dup-card-section">'
            "<h4>File to Keep</h4>"
            f"{keep_html}"
            "</div>"
            '<div class="dup-card-section">'
            "<h4>Files to Remove</h4>"
            f"{remove_html}"
            "</div>"
            "</div>"
            "</details>"
        )
    return (
        f'<div id="{_escape(section_dom_id)}" class="dup-cards" data-page="1">'
        f'{"".join(cards)}'
        '<p class="search-empty" hidden>No duplicate groups match this search.</p>'
        "</div>"
    )


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
    search_input_id = f"{section_dom_id}-search"
    cards_html = _render_duplicate_cards(
        section_dom_id=section_dom_id,
        rows=section.visual_rows,
        media=section.media,
        metadata_by_path=section.metadata_by_path,
    )
    controls_html = _render_card_controls(section_dom_id)
    search_html = _render_search_controls(section_dom_id, search_input_id)
    pagination_html = _render_pagination_controls(section_dom_id, len(section.visual_rows))
    if not section.visual_rows:
        cards_html = '<p class="empty">(no duplicate rows)</p>'
        controls_html = ""
        search_html = ""
        pagination_html = ""
    results_block_html = (
        '<section class="results-section">'
        "<h2>Results</h2>"
        f'<p class="preview-count">{_escape(subtitle)}</p>'
        f"{search_html}"
        f"{pagination_html}"
        f"{controls_html}"
        f"{cards_html}"
        "</section>"
    )

    return (
        '<section class="media-section">'
        "<h2>Overview</h2>"
        f'<div class="command-block"><h3>Command</h3><pre>{_escape(section.command_preview)}</pre></div>'
        f'<p class="exit-code">Scanner Exit Code: {section.exit_code}</p>'
        f"{_render_summary(section.summary)}"
        '<div class="artifact-block">'
        f"{_render_artifact_link(section.json_path, 'JSON Report')}"
        f"{_render_artifact_link(section.csv_path, 'CSV Report')}"
        "</div>"
        "</section>"
        f"{results_block_html}"
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
        ":root{color-scheme:dark light;}"
        "body[data-theme='dark']{--bg:#0f141a;--surface:#151d24;--surface-muted:#1a2430;--surface-soft:#111922;--text:#e8edf3;--text-muted:#9fb0c3;--accent:#8bb9ff;--border:#324253;--border-soft:#2a3847;--chip-bg:#1f2b38;--button-bg:#1d2a38;--button-hover:#25364a;}"
        "body[data-theme='light']{--bg:#f4f6f8;--surface:#ffffff;--surface-muted:#f6f9fc;--surface-soft:#fcfdff;--text:#1a1a1a;--text-muted:#44566a;--accent:#0f2742;--border:#d7dee8;--border-soft:#e3e8ef;--chip-bg:#ffffff;--button-bg:#f8fafc;--button-hover:#edf2f8;}"
        "body{margin:0;background:var(--bg);color:var(--text);font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;}"
        "a{color:var(--accent);}"
        "main{max-width:1280px;margin:0 auto;padding:24px;}"
        "h1{margin:0;font-size:28px;}"
        "h2{margin:0 0 12px;font-size:20px;}"
        "h3{margin:0 0 8px;font-size:14px;color:var(--accent);text-transform:uppercase;letter-spacing:0.04em;}"
        "h4{margin:0 0 8px;font-size:14px;color:var(--accent);}"
        ".overview,.media-section,.results-section{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 18px;margin-bottom:16px;}"
        ".overview-header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px;}"
        ".theme-toggle{border:1px solid var(--border);background:var(--button-bg);color:var(--text);border-radius:8px;padding:6px 10px;font-size:13px;cursor:pointer;}"
        ".theme-toggle:hover{background:var(--button-hover);}"
        ".overview-grid{display:grid;grid-template-columns:220px 1fr;gap:8px 12px;align-items:start;}"
        ".label{font-weight:700;color:var(--accent);}"
        ".value{word-break:break-word;}"
        ".command-block pre{margin:0;padding:10px;border-radius:8px;background:var(--surface-muted);border:1px solid var(--border);overflow:auto;}"
        ".exit-code,.preview-count{font-weight:600;color:var(--accent);}"
        ".summary-block{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;margin:12px 0;}"
        ".summary-row{display:flex;justify-content:space-between;gap:8px;padding:8px 10px;border:1px solid var(--border);border-radius:8px;background:var(--surface-soft);}"
        ".summary-label{font-weight:600;}"
        ".summary-value{font-weight:700;}"
        ".artifact-block{display:flex;flex-direction:column;gap:6px;margin:8px 0 12px;}"
        ".search-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0 10px;}"
        ".search-label{font-size:13px;font-weight:600;color:var(--accent);}"
        ".search-input{min-width:280px;max-width:520px;flex:1;padding:7px 10px;border-radius:8px;border:1px solid var(--border);background:var(--surface-soft);color:var(--text);}"
        ".search-input::placeholder{color:var(--text-muted);}"
        ".pagination-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 10px;}"
        ".page-size-select{padding:6px 10px;border-radius:8px;border:1px solid var(--border);background:var(--surface-soft);color:var(--text);}"
        ".page-status{font-size:13px;color:var(--text-muted);}"
        ".card-controls{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 12px;}"
        ".control-btn{border:1px solid var(--border);background:var(--button-bg);color:var(--text);border-radius:8px;padding:6px 10px;font-size:13px;cursor:pointer;}"
        ".control-btn:hover{background:var(--button-hover);}"
        ".dup-cards{display:grid;gap:10px;}"
        ".dup-card{border:1px solid var(--border);border-radius:10px;background:var(--surface-soft);overflow:hidden;}"
        ".dup-card-summary{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:10px 12px;cursor:pointer;background:var(--surface-muted);}"
        ".summary-chip{border:1px solid var(--border);border-radius:999px;padding:3px 8px;background:var(--chip-bg);font-size:12px;line-height:1.4;}"
        ".dup-card-body{padding:12px;display:grid;gap:12px;}"
        ".dup-card-section{display:grid;gap:8px;}"
        ".media-item{display:grid;grid-template-columns:160px minmax(220px,1fr);gap:10px;padding:8px;border:1px solid var(--border-soft);border-radius:8px;background:var(--surface);}"
        ".media-preview{width:160px;height:110px;background:var(--surface-muted);border-radius:6px;display:flex;align-items:center;justify-content:center;overflow:hidden;}"
        ".media-preview img,.media-preview video{width:100%;height:100%;object-fit:cover;display:block;}"
        ".preview-unavailable{font-size:12px;color:var(--text-muted);padding:8px;text-align:center;}"
        ".media-meta{min-width:0;display:grid;gap:6px;align-content:start;}"
        ".media-name{font-weight:700;word-break:break-word;}"
        ".media-actions{display:flex;gap:10px;flex-wrap:wrap;}"
        ".media-link{font-size:12px;}"
        ".media-details{display:grid;gap:4px;font-size:12px;color:var(--text-muted);}"
        ".remove-items{display:grid;gap:8px;}"
        ".search-empty{margin:0;padding:10px;border:1px dashed var(--border);border-radius:8px;background:var(--surface-muted);color:var(--text-muted);}"
        ".empty{padding:12px;border:1px dashed var(--border);border-radius:8px;background:var(--surface-muted);color:var(--text-muted);}"
        ".empty-inline{margin:0;padding:8px;border:1px dashed var(--border);border-radius:8px;background:var(--surface-muted);color:var(--text-muted);}"
        "@media (max-width:900px){"
        "main{padding:12px;}"
        ".overview-header{align-items:flex-start;flex-direction:column;}"
        ".overview-grid{grid-template-columns:1fr;}"
        ".media-item{grid-template-columns:1fr;}"
        ".media-preview{width:100%;height:220px;}"
        "}"
        "</style>"
        "</head>"
        '<body data-theme="dark">'
        "<main>"
        '<section class="overview">'
        '<div class="overview-header">'
        "<h1>czk viz report</h1>"
        '<button id="theme-toggle" type="button" class="theme-toggle" onclick="czkToggleTheme()">Light mode</button>'
        "</div>"
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
        "function czkToggleTheme() {"
        "  const body = document.body;"
        "  const button = document.getElementById('theme-toggle');"
        "  if (!body) { return; }"
        "  const current = body.getAttribute('data-theme') || 'dark';"
        "  const next = current === 'dark' ? 'light' : 'dark';"
        "  body.setAttribute('data-theme', next);"
        "  if (button) { button.textContent = next === 'dark' ? 'Light mode' : 'Dark mode'; }"
        "}"
        "function czkToggleCards(sectionId, shouldOpen) {"
        "  const container = document.getElementById(sectionId);"
        "  if (!container) { return; }"
        "  container.querySelectorAll('.dup-card').forEach((card) => { card.open = shouldOpen; });"
        "}"
        "function czkApplyCardView(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId, pageDelta) {"
        "  const container = document.getElementById(sectionId);"
        "  const input = document.getElementById(inputId);"
        "  const sizeSelect = document.getElementById(sizeSelectId);"
        "  const pageStatus = document.getElementById(pageStatusId);"
        "  const firstBtn = document.getElementById(firstBtnId);"
        "  const prevBtn = document.getElementById(prevBtnId);"
        "  const nextBtn = document.getElementById(nextBtnId);"
        "  const lastBtn = document.getElementById(lastBtnId);"
        "  if (!container || !input || !sizeSelect) { return; }"
        "  const query = input.value.trim().toLowerCase();"
        "  const parsedSize = Number.parseInt(sizeSelect.value, 10);"
        "  const pageSize = [25, 50, 100].includes(parsedSize) ? parsedSize : 25;"
        "  let page = Number.parseInt(container.dataset.page || '1', 10);"
        "  if (!Number.isFinite(page) || page < 1) { page = 1; }"
        "  if (pageDelta === 0) { page = 1; }"
        "  if (typeof pageDelta === 'number' && pageDelta !== 0) { page += pageDelta; }"
        "  const allCards = Array.from(container.querySelectorAll('.dup-card'));"
        "  const matchedCards = [];"
        "  allCards.forEach((card) => {"
        "    const searchText = (card.dataset.search || '').toLowerCase();"
        "    const matched = query === '' || searchText.includes(query);"
        "    if (matched) {"
        "      matchedCards.push(card);"
        "      if (query !== '') { card.open = true; }"
        "    } else {"
        "      card.hidden = true;"
        "    }"
        "  });"
        "  const matches = matchedCards.length;"
        "  const totalPages = matches === 0 ? 1 : Math.ceil(matches / pageSize);"
        "  if (page > totalPages) { page = totalPages; }"
        "  if (page < 1) { page = 1; }"
        "  const start = (page - 1) * pageSize;"
        "  const end = start + pageSize;"
        "  matchedCards.forEach((card, index) => {"
        "    card.hidden = index < start || index >= end;"
        "  });"
        "  container.dataset.page = String(page);"
        "  const emptyMessage = container.querySelector('.search-empty');"
        "  if (emptyMessage) { emptyMessage.hidden = matches !== 0; }"
        "  if (pageStatus) {"
        "    pageStatus.textContent = matches === 0 ? 'Page 0 of 0' : `Page ${page} of ${totalPages}`;"
        "  }"
        "  if (firstBtn) { firstBtn.disabled = matches === 0 || page <= 1; }"
        "  if (prevBtn) { prevBtn.disabled = matches === 0 || page <= 1; }"
        "  if (nextBtn) { nextBtn.disabled = matches === 0 || page >= totalPages; }"
        "  if (lastBtn) { lastBtn.disabled = matches === 0 || page >= totalPages; }"
        "}"
        "function czkFilterCards(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId) {"
        "  czkApplyCardView(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId, 0);"
        "}"
        "function czkChangePage(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId, pageDelta) {"
        "  czkApplyCardView(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId, pageDelta);"
        "}"
        "function czkJumpPage(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId, target) {"
        "  const container = document.getElementById(sectionId);"
        "  if (!container) { return; }"
        "  if (target === 'first') { container.dataset.page = '1'; }"
        "  if (target === 'last') { container.dataset.page = '999999999'; }"
        "  czkApplyCardView(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId, null);"
        "}"
        "function czkClearCardSearch(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId) {"
        "  const input = document.getElementById(inputId);"
        "  if (!input) { return; }"
        "  input.value = '';"
        "  czkFilterCards(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId);"
        "}"
        "function czkOpenBackground(event) {"
        "  if (!event) { return true; }"
        "  event.preventDefault();"
        "  const anchor = event.currentTarget;"
        "  if (!anchor) { return false; }"
        "  const href = anchor.getAttribute('href');"
        "  if (!href) { return false; }"
        "  const popup = window.open(href, '_blank', 'noopener,noreferrer');"
        "  if (popup) { popup.blur(); }"
        "  window.focus();"
        "  return false;"
        "}"
        "</script>"
        "</body>"
        "</html>"
    )
