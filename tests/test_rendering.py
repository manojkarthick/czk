from __future__ import annotations

import io
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from czk_tool.report import DuplicatePreviewRow, MediaSummary
from czk_tool.rendering import RenderConfig, Renderer


class RenderingTests(unittest.TestCase):
    def test_no_color_mode_has_required_fields_without_ansi(self) -> None:
        buffer = io.StringIO()
        renderer = Renderer(RenderConfig(no_color=True, stdout_is_tty=True), file=buffer)

        renderer.render_run_header(
            mode="test",
            target_dir=Path("/tmp/data"),
            out_dir=Path("/tmp/out"),
            timestamp="20260208-140000",
            media_targets=["images", "videos"],
        )
        renderer.render_media_header(
            media="images",
            mode="test",
            command="czkawka_cli image -d /tmp/data ...",
        )
        renderer.render_exit_code(0)
        renderer.render_metrics(
            MediaSummary(
                total_found=100,
                duplicate_groups=10,
                duplicates_to_remove=20,
                after_remove_estimate=80,
            )
        )
        renderer.render_artifacts(
            json_path=Path("/tmp/out/demo-images-20260208-140000.json"),
            csv_path=Path("/tmp/out/demo-images-20260208-140000.csv"),
        )
        renderer.render_preview_table(
            preview_rows=[
                DuplicatePreviewRow(
                    index=1,
                    file_to_keep="/tmp/data/keep.jpg",
                    remove_count=2,
                    first_remove="/tmp/data/remove.jpg",
                )
            ],
            shown_rows=1,
            total_rows=1,
        )
        renderer.render_combined_summary(
            MediaSummary(
                total_found=100,
                duplicate_groups=10,
                duplicates_to_remove=20,
                after_remove_estimate=80,
            )
        )

        output = buffer.getvalue()
        self.assertIn("mode", output)
        self.assertIn("target_dir", output)
        self.assertIn("metrics", output)
        self.assertIn("artifacts", output)
        self.assertIn("table_rows_shown: 1/1", output)
        self.assertNotIn("\x1b[", output)

    def test_preview_table_headers_present(self) -> None:
        buffer = io.StringIO()
        renderer = Renderer(RenderConfig(no_color=True, stdout_is_tty=False), file=buffer)
        renderer.render_preview_table(
            preview_rows=[
                DuplicatePreviewRow(index=1, file_to_keep="/tmp/a", remove_count=1, first_remove="/tmp/b")
            ],
            shown_rows=1,
            total_rows=2,
        )
        output = buffer.getvalue()
        self.assertIn("#", output)
        self.assertIn("file_to_keep", output)
        self.assertIn("remove_count", output)
        self.assertIn("first_remove", output)

    def test_auto_plain_output_when_not_tty(self) -> None:
        buffer = io.StringIO()
        renderer = Renderer(RenderConfig(no_color=False, stdout_is_tty=False), file=buffer)
        renderer.render_error("Run failed", "sample details")
        output = buffer.getvalue()
        self.assertIn("Run failed", output)
        self.assertNotIn("\x1b[", output)


if __name__ == "__main__":
    unittest.main()
