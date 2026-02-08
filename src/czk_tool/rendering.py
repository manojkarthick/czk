from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .counting import MediaType
from .report import DuplicatePreviewRow, MediaSummary

Mode = Literal["test", "execute"]


@dataclass(frozen=True)
class RenderConfig:
    no_color: bool
    stdout_is_tty: bool
    terminal_width: int | None = None


def create_console(config: RenderConfig, file: TextIO | None = None) -> Console:
    enable_color = (not config.no_color) and config.stdout_is_tty
    return Console(
        file=file or sys.stdout,
        force_terminal=enable_color,
        color_system="auto" if enable_color else None,
        no_color=not enable_color,
        highlight=False,
        width=config.terminal_width,
    )


def _format_number(value: int) -> str:
    return f"{value:,}"


def _mode_label(mode: Mode) -> str:
    return "DRY RUN" if mode == "test" else "EXECUTE"


def _friendly_summary_rows(summary: MediaSummary) -> list[tuple[str, str]]:
    return [
        ("Total Files Scanned", _format_number(summary.total_found)),
        ("Duplicate Groups Found", _format_number(summary.duplicate_groups)),
        ("Files Marked for Removal", _format_number(summary.duplicates_to_remove)),
        ("Estimated Files Remaining", _format_number(summary.after_remove_estimate)),
    ]


def _compact_name(path_value: str) -> str:
    if path_value == "-":
        return path_value
    return Path(path_value).name or path_value


def _compact_command_value(flag: str, value: str) -> str:
    placeholders = {
        "-d": "<target-folder>",
        "--directories": "<target-folder>",
        "-p": "<json-report>",
        "--pretty-file-to-save": "<json-report>",
    }
    if flag in placeholders:
        return placeholders[flag]
    if "/" in value:
        name = Path(value).name
        return f".../{name}" if name else "<path>"
    return value


def _format_command_shell(command: list[str]) -> str:
    if not command:
        return ""
    if len(command) == 1:
        return command[0]

    executable = Path(command[0]).name or command[0]
    prefix = f"{executable} {command[1]}"
    parts = command[2:]
    if not parts:
        return prefix

    grouped: list[str] = []
    index = 0
    while index < len(parts):
        token = parts[index]
        if token.startswith("-") and index + 1 < len(parts) and not parts[index + 1].startswith("-"):
            grouped.append(f"{token} {_compact_command_value(token, parts[index + 1])}")
            index += 2
        else:
            grouped.append(token)
            index += 1

    lines = [f"{prefix} \\"]
    for offset, token in enumerate(grouped):
        suffix = " \\" if offset < len(grouped) - 1 else ""
        lines.append(f"  {token}{suffix}")
    return "\n".join(lines)


def _preview_layout(width: int) -> Literal["wide", "medium", "narrow"]:
    if width < 86:
        return "narrow"
    if width < 120:
        return "medium"
    return "wide"


class Renderer:
    def __init__(self, config: RenderConfig, file: TextIO | None = None) -> None:
        self.console = create_console(config, file=file)

    def render_run_header(
        self,
        *,
        mode: Mode,
        target_dir: Path,
        out_dir: Path,
        timestamp: str,
        media_targets: list[MediaType],
    ) -> None:
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(style="bold cyan", no_wrap=True)
        table.add_column(style="white")
        table.add_row("Run Mode", _mode_label(mode))
        table.add_row("Target Folder", str(target_dir))
        table.add_row("Reports Folder", str(out_dir))
        table.add_row("Run Timestamp", timestamp)
        table.add_row("Media Types", ", ".join(media_targets))
        self.console.print(Panel(table, title="Run Overview", border_style="cyan"))
        self.console.print("[dim]Full report paths are shown above; preview rows use compact names.[/dim]")

    def render_media_header(self, *, media: MediaType, mode: Mode, command: list[str]) -> None:
        mode_style = "yellow" if mode == "test" else "magenta"
        title = f"{media.upper()} | {_mode_label(mode)}"

        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(style="bold cyan", no_wrap=True)
        table.add_column(style="white")
        table.add_row("Command", _format_command_shell(command))

        self.console.print()
        self.console.print(Panel(table, title=title, border_style=mode_style))

    def render_exit_code(self, exit_code: int) -> None:
        style = "green" if exit_code == 0 else "yellow"
        self.console.print(f"Scanner Exit Code: {exit_code}", style=style)

    def render_summary(self, summary: MediaSummary) -> None:
        summary_table = Table(title="Summary", box=box.ROUNDED, expand=True)
        summary_table.add_column("Field", style="bold cyan")
        summary_table.add_column("Value", style="white")
        for label, value in _friendly_summary_rows(summary):
            if label == "Files Marked for Removal":
                value_text = Text(value, style="red")
            elif label == "Estimated Files Remaining":
                value_text = Text(value, style="green")
            else:
                value_text = Text(value, style="white")
            summary_table.add_row(label, value_text)
        self.console.print(summary_table)

    def render_artifacts(self, *, json_path: Path, csv_path: Path) -> None:
        artifacts = Table(title="Report Files", box=box.ROUNDED, expand=True)
        artifacts.add_column("Type", style="bold cyan", no_wrap=True)
        artifacts.add_column("Path", style="white")
        artifacts.add_row("JSON Report", str(json_path))
        artifacts.add_row("CSV Report", str(csv_path))
        self.console.print(artifacts)
        self.console.print("[dim]Full details are saved in CSV/JSON.[/dim]")

    def render_preview_table(
        self,
        *,
        preview_rows: list[DuplicatePreviewRow],
        shown_rows: int,
        total_rows: int,
    ) -> None:
        subtitle = f"Showing {shown_rows} of {total_rows} duplicate groups"
        self.console.print(subtitle, style="bold cyan")

        if not preview_rows:
            self.console.print("(no duplicate rows)")
            return

        layout = _preview_layout(self.console.size.width)
        if layout == "narrow":
            self._render_preview_list(preview_rows)
            return

        include_first_remove = layout == "wide"
        table = Table(title="Duplicate Preview", box=box.ROUNDED, expand=True)
        table.add_column("#", style="bold cyan", no_wrap=True)
        table.add_column("file_to_keep", style="white", overflow="fold")
        table.add_column("remove_count", style="yellow", no_wrap=True)
        if include_first_remove:
            table.add_column("first_remove", style="white", overflow="fold")

        for row in preview_rows:
            rendered = [
                str(row.index),
                _compact_name(row.file_to_keep),
                str(row.remove_count),
            ]
            if include_first_remove:
                rendered.append(_compact_name(row.first_remove))
            table.add_row(*rendered)

        self.console.print(table)
        self.console.print("[dim]Review preview rows before execute mode.[/dim]")

    def _render_preview_list(self, preview_rows: list[DuplicatePreviewRow]) -> None:
        self.console.print(Panel("Duplicate Preview", border_style="cyan"))
        for row in preview_rows:
            table = Table.grid(expand=True, padding=(0, 1))
            table.add_column(style="bold cyan", no_wrap=True)
            table.add_column(style="white")
            table.add_row("Group", str(row.index))
            table.add_row("Keep", _compact_name(row.file_to_keep))
            table.add_row("Remove Count", str(row.remove_count))
            table.add_row("First Remove", _compact_name(row.first_remove))
            self.console.print(Panel(table, box=box.ROUNDED))
        self.console.print("[dim]Review preview rows before execute mode.[/dim]")

    def render_error(self, message: str, details: str | None = None) -> None:
        body = message if not details else f"{message}\n\n{details}"
        self.console.print(Panel(body, title="Error", border_style="red"))
