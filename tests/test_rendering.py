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
    def test_friendly_labels_and_no_ansi(self) -> None:
        buffer = io.StringIO()
        renderer = Renderer(
            RenderConfig(no_color=True, stdout_is_tty=True, terminal_width=140),
            file=buffer,
        )

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
            command=["/opt/homebrew/bin/czkawka_cli", "image", "-d", "/tmp/data", "--dry-run"],
        )
        renderer.render_exit_code(0)
        renderer.render_summary(
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

        output = buffer.getvalue()
        self.assertIn("Run Overview", output)
        self.assertIn("Run Mode", output)
        self.assertIn("Summary", output)
        self.assertIn("Total Files Scanned", output)
        self.assertIn("Duplicate Groups Found", output)
        self.assertIn("Files Marked for Removal", output)
        self.assertIn("Estimated Files Remaining", output)
        self.assertNotIn("\x1b[", output)
        self.assertNotIn("combined summary", output.lower())

    def test_command_multiline_has_backslash_continuation(self) -> None:
        buffer = io.StringIO()
        renderer = Renderer(
            RenderConfig(no_color=True, stdout_is_tty=False, terminal_width=120),
            file=buffer,
        )
        renderer.render_media_header(
            media="videos",
            mode="execute",
            command=[
                "/opt/homebrew/bin/czkawka_cli",
                "video",
                "-d",
                "/tmp/input",
                "-t",
                "10",
                "-D",
                "AEB",
            ],
        )
        output = buffer.getvalue()
        self.assertIn("Command", output)
        self.assertIn("czkawka_cli video \\", output)
        self.assertIn("  -d <target-folder> \\", output)
        self.assertIn("  -D AEB", output)
        self.assertNotIn("/tmp/input", output)

    def test_preview_compacts_to_filename_only(self) -> None:
        buffer = io.StringIO()
        renderer = Renderer(
            RenderConfig(no_color=True, stdout_is_tty=False, terminal_width=140),
            file=buffer,
        )
        renderer.render_preview_table(
            preview_rows=[
                DuplicatePreviewRow(
                    index=1,
                    file_to_keep="/tmp/a/very/deep/path/keep-file.jpg",
                    remove_count=2,
                    first_remove="/tmp/b/another/deep/path/remove-file.jpg",
                )
            ],
            shown_rows=1,
            total_rows=3,
        )
        output = buffer.getvalue()
        self.assertIn("keep-file.jpg", output)
        self.assertIn("remove-file.jpg", output)
        self.assertNotIn("/tmp/a/very/deep/path/keep-file.jpg", output)

    def test_preview_wide_medium_narrow_layouts(self) -> None:
        row = DuplicatePreviewRow(
            index=1,
            file_to_keep="/tmp/path/keep.jpg",
            remove_count=1,
            first_remove="/tmp/path/remove.jpg",
        )

        wide_buffer = io.StringIO()
        wide_renderer = Renderer(
            RenderConfig(no_color=True, stdout_is_tty=False, terminal_width=140),
            file=wide_buffer,
        )
        wide_renderer.render_preview_table(preview_rows=[row], shown_rows=1, total_rows=1)
        wide_output = wide_buffer.getvalue()
        self.assertIn("index", wide_output)
        self.assertIn("first_remove", wide_output)

        medium_buffer = io.StringIO()
        medium_renderer = Renderer(
            RenderConfig(no_color=True, stdout_is_tty=False, terminal_width=100),
            file=medium_buffer,
        )
        medium_renderer.render_preview_table(preview_rows=[row], shown_rows=1, total_rows=1)
        medium_output = medium_buffer.getvalue()
        self.assertIn("index", medium_output)
        self.assertIn("remove_count", medium_output)
        self.assertNotIn("first_remove", medium_output)

        narrow_buffer = io.StringIO()
        narrow_renderer = Renderer(
            RenderConfig(no_color=True, stdout_is_tty=False, terminal_width=70),
            file=narrow_buffer,
        )
        narrow_renderer.render_preview_table(preview_rows=[row], shown_rows=1, total_rows=1)
        narrow_output = narrow_buffer.getvalue()
        self.assertIn("Duplicate Preview", narrow_output)
        self.assertIn("Group", narrow_output)

    def test_auto_plain_output_when_not_tty(self) -> None:
        buffer = io.StringIO()
        renderer = Renderer(RenderConfig(no_color=False, stdout_is_tty=False), file=buffer)
        renderer.render_error("Run failed", "sample details")
        output = buffer.getvalue()
        self.assertIn("Run failed", output)
        self.assertNotIn("\x1b[", output)

    def test_duckdb_intro_respects_media_selection(self) -> None:
        images_buffer = io.StringIO()
        images_renderer = Renderer(
            RenderConfig(no_color=True, stdout_is_tty=False, terminal_width=120),
            file=images_buffer,
        )
        images_renderer.render_duckdb_intro(["images"])
        images_output = images_buffer.getvalue()
        self.assertIn("duplicates_images", images_output)
        self.assertIn("duplicates_images_json", images_output)
        self.assertIn("duplicates_images_expanded", images_output)
        self.assertNotIn("duplicates_videos", images_output)
        self.assertNotIn("duplicates_videos_json", images_output)
        self.assertNotIn("duplicates_videos_expanded", images_output)

        videos_buffer = io.StringIO()
        videos_renderer = Renderer(
            RenderConfig(no_color=True, stdout_is_tty=False, terminal_width=120),
            file=videos_buffer,
        )
        videos_renderer.render_duckdb_intro(["videos"])
        videos_output = videos_buffer.getvalue()
        self.assertIn("duplicates_videos", videos_output)
        self.assertIn("duplicates_videos_json", videos_output)
        self.assertIn("duplicates_videos_expanded", videos_output)
        self.assertNotIn("duplicates_images", videos_output)
        self.assertNotIn("duplicates_images_json", videos_output)
        self.assertNotIn("duplicates_images_expanded", videos_output)


if __name__ == "__main__":
    unittest.main()
