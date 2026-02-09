from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from czk_tool.report import DuplicateRow, DuplicateVisualRow, MediaSummary, build_visual_rows_from_csv, write_csv
from czk_tool.viz import VizMediaSection, VizRunContext, build_html_report


class VizReportTests(unittest.TestCase):
    def test_build_html_report_includes_sections_and_media_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            image_keep = temp_root / "keep-image.jpg"
            image_remove = temp_root / "remove-image.jpg"
            video_keep = temp_root / "keep-video.mp4"
            video_remove = temp_root / "remove-video.mp4"
            image_keep.write_bytes(b"image")
            image_remove.write_bytes(b"image-remove")
            video_keep.write_bytes(b"video")
            video_remove.write_bytes(b"video-remove")

            run_context = VizRunContext(
                run_mode="VIZ (DRY RUN)",
                target_dir=temp_root,
                out_dir=temp_root,
                timestamp="20260209-090000",
                media_targets=["images", "videos"],
            )
            sections = [
                VizMediaSection(
                    media="images",
                    command_preview="czkawka_cli image \\\n  --dry-run",
                    exit_code=0,
                    summary=MediaSummary(
                        total_found=10,
                        duplicate_groups=1,
                        duplicates_to_remove=1,
                        after_remove_estimate=9,
                    ),
                    json_path=temp_root / "images.json",
                    csv_path=temp_root / "images.csv",
                    visual_rows=[
                        DuplicateVisualRow(
                            index=1,
                            file_to_keep=str(image_keep),
                            files_to_remove=[str(image_remove)],
                            remove_count=1,
                        )
                    ],
                    shown_rows=1,
                    total_rows=1,
                ),
                VizMediaSection(
                    media="videos",
                    command_preview="czkawka_cli video \\\n  --dry-run",
                    exit_code=0,
                    summary=MediaSummary(
                        total_found=8,
                        duplicate_groups=1,
                        duplicates_to_remove=1,
                        after_remove_estimate=7,
                    ),
                    json_path=temp_root / "videos.json",
                    csv_path=temp_root / "videos.csv",
                    visual_rows=[
                        DuplicateVisualRow(
                            index=1,
                            file_to_keep=str(video_keep),
                            files_to_remove=[str(video_remove)],
                            remove_count=1,
                        )
                    ],
                    shown_rows=1,
                    total_rows=1,
                ),
            ]

            html_report = build_html_report(run_context=run_context, media_sections=sections)

        self.assertIn("czk viz report", html_report)
        self.assertIn("Run Mode", html_report)
        self.assertIn("Target Folder", html_report)
        self.assertIn("Reports Folder", html_report)
        self.assertIn("Run Timestamp", html_report)
        self.assertIn("Media Types", html_report)
        self.assertIn("IMAGES | DRY RUN", html_report)
        self.assertIn("VIDEOS | DRY RUN", html_report)
        self.assertIn("Scanner Exit Code: 0", html_report)
        self.assertIn("<img ", html_report)
        self.assertIn("<video controls preload=\"metadata\" muted>", html_report)
        self.assertIn("images.json", html_report)
        self.assertIn("videos.csv", html_report)

    def test_build_html_report_honors_top_and_escapes_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            csv_path = temp_root / "images.csv"
            write_csv(
                [
                    DuplicateRow(
                        index=1,
                        file_to_keep="/tmp/folder/<bad>&keep.jpg",
                        files_to_remove=["/tmp/folder/remove 1.jpg", "/tmp/folder/remove 2.jpg"],
                        count=2,
                    ),
                    DuplicateRow(
                        index=2,
                        file_to_keep="/tmp/folder/skip-me.jpg",
                        files_to_remove=["/tmp/folder/skip-remove.jpg"],
                        count=1,
                    ),
                ],
                csv_path,
            )
            visual_rows, total_rows, shown_rows = build_visual_rows_from_csv(csv_path, top=1)
            section = VizMediaSection(
                media="images",
                command_preview="czkawka_cli image --dry-run",
                exit_code=0,
                summary=MediaSummary(
                    total_found=2,
                    duplicate_groups=2,
                    duplicates_to_remove=3,
                    after_remove_estimate=0,
                ),
                json_path=temp_root / "images.json",
                csv_path=csv_path,
                visual_rows=visual_rows,
                shown_rows=shown_rows,
                total_rows=total_rows,
            )
            report = build_html_report(
                run_context=VizRunContext(
                    run_mode="VIZ (DRY RUN)",
                    target_dir=temp_root,
                    out_dir=temp_root,
                    timestamp="20260209-090500",
                    media_targets=["images"],
                ),
                media_sections=[section],
            )

        self.assertIn("Showing 1 of 2 duplicate groups", report)
        self.assertIn("&lt;bad&gt;&amp;keep.jpg", report)
        self.assertNotIn("skip-me.jpg", report)
        self.assertIn("Preview unavailable", report)
        self.assertIn(str(csv_path), report)


if __name__ == "__main__":
    unittest.main()
