from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .counting import MediaType
from .report import DuplicatePreviewRow, MediaSummary

Mode = Literal["test", "execute"]


@dataclass(frozen=True)
class RenderConfig:
    no_color: bool
    stdout_is_tty: bool


def create_console(config: RenderConfig, file: TextIO | None = None) -> Console:
    enable_color = (not config.no_color) and config.stdout_is_tty
    return Console(
        file=file or sys.stdout,
        force_terminal=enable_color,
        color_system="auto" if enable_color else None,
        no_color=not enable_color,
        highlight=False,
    )


def _format_number(value: int) -> str:
    return f"{value:,}"


def _mode_label(mode: Mode) -> str:
    return "DRY RUN" if mode == "test" else "EXECUTE"


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
        table.add_column(justify="right", style="bold cyan", no_wrap=True)
        table.add_column(style="white")
        table.add_row("mode", _mode_label(mode))
        table.add_row("target_dir", str(target_dir))
        table.add_row("out_dir", str(out_dir))
        table.add_row("timestamp", timestamp)
        table.add_row("media", ", ".join(media_targets))
        self.console.print(Panel(table, title="czk run", border_style="cyan"))

    def render_media_header(self, *, media: MediaType, mode: Mode, command: str) -> None:
        mode_style = "yellow" if mode == "test" else "magenta"
        title = f"{media.upper()} - {_mode_label(mode)}"

        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(justify="right", style="bold cyan", no_wrap=True)
        table.add_column(style="white")
        table.add_row("command", command)

        self.console.print()
        self.console.print(Panel(table, title=title, border_style=mode_style))

    def render_exit_code(self, exit_code: int) -> None:
        style = "green" if exit_code == 0 else "yellow"
        table = Table.grid(expand=True)
        table.add_column(style="bold cyan", no_wrap=True)
        table.add_column(style=style)
        table.add_row("czkawka_exit_code", str(exit_code))
        self.console.print(table)

    def render_metrics(self, summary: MediaSummary) -> None:
        metrics = Table(title="metrics", box=box.SIMPLE, expand=True)
        metrics.add_column("name", style="bold cyan")
        metrics.add_column("value", justify="right", style="white")
        metrics.add_row("total_found", _format_number(summary.total_found))
        metrics.add_row("duplicate_groups", _format_number(summary.duplicate_groups))
        metrics.add_row("duplicates_to_remove", _format_number(summary.duplicates_to_remove))
        metrics.add_row("after_remove_estimate", _format_number(summary.after_remove_estimate))
        self.console.print(metrics)

    def render_artifacts(self, *, json_path: Path, csv_path: Path) -> None:
        artifacts = Table(title="artifacts", box=box.SIMPLE, expand=True)
        artifacts.add_column("type", style="bold cyan", no_wrap=True)
        artifacts.add_column("path", style="white")
        artifacts.add_row("json", str(json_path))
        artifacts.add_row("csv", str(csv_path))
        self.console.print(artifacts)

    def render_preview_table(
        self,
        *,
        preview_rows: list[DuplicatePreviewRow],
        shown_rows: int,
        total_rows: int,
    ) -> None:
        subtitle = f"table_rows_shown: {shown_rows}/{total_rows}"
        self.console.print(subtitle, style="bold cyan")

        if not preview_rows:
            self.console.print("(no duplicate rows)")
            return

        table = Table(title="duplicate preview", box=box.SIMPLE_HEAVY, expand=True)
        table.add_column("#", justify="right", style="bold")
        table.add_column("file_to_keep", style="white")
        table.add_column("remove_count", justify="right", style="yellow")
        table.add_column("first_remove", style="white")

        for row in preview_rows:
            table.add_row(
                str(row.index),
                row.file_to_keep,
                str(row.remove_count),
                row.first_remove,
            )

        self.console.print(table)

    def render_combined_summary(self, summary: MediaSummary) -> None:
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(justify="right", style="bold cyan", no_wrap=True)
        table.add_column(style="white")
        table.add_row("total_found", _format_number(summary.total_found))
        table.add_row("duplicate_groups", _format_number(summary.duplicate_groups))
        table.add_row("duplicates_to_remove", _format_number(summary.duplicates_to_remove))
        table.add_row("after_remove_estimate", _format_number(summary.after_remove_estimate))
        self.console.print()
        self.console.print(Panel(table, title="combined summary", border_style="green"))

    def render_error(self, message: str, details: str | None = None) -> None:
        body = message if not details else f"{message}\n\n{details}"
        self.console.print(Panel(body, title="error", border_style="red"))
