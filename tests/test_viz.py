from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from czk_tool.report import DuplicateRow, DuplicateVisualRow, MediaSummary, build_visual_rows_from_csv, write_csv
from czk_tool.viz import MediaItemMetadata, VizMediaSection, VizRunContext, build_html_report


class VizReportTests(unittest.TestCase):
    def test_build_html_report_uses_cards_controls_and_friendly_labels(self) -> None:
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
                    metadata_by_path={
                        str(image_keep): MediaItemMetadata(
                            size_bytes=2048,
                            modified_epoch=1_700_000_000,
                            width=640,
                            height=480,
                        ),
                        str(image_remove): MediaItemMetadata(
                            size_bytes=1024,
                            modified_epoch=1_700_000_010,
                            width=320,
                            height=240,
                        ),
                    },
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
                    metadata_by_path={
                        str(video_keep): MediaItemMetadata(
                            size_bytes=10_000,
                            modified_epoch=1_700_000_020,
                        ),
                        str(video_remove): MediaItemMetadata(
                            size_bytes=8_000,
                            modified_epoch=1_700_000_030,
                        ),
                    },
                ),
            ]

            html_report = build_html_report(run_context=run_context, media_sections=sections)

        self.assertIn("czk viz report", html_report)
        self.assertIn("Run Mode", html_report)
        self.assertIn("Target Folder", html_report)
        self.assertIn("Reports Folder", html_report)
        self.assertIn("Run Timestamp", html_report)
        self.assertIn("Media Types", html_report)
        self.assertEqual(html_report.count("<h2>Overview</h2>"), 2)
        self.assertIn('<body data-theme="dark">', html_report)
        self.assertIn('id="theme-toggle"', html_report)
        self.assertIn("Light mode", html_report)
        self.assertIn("function czkToggleTheme()", html_report)
        self.assertIn("function czkApplyCardView(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId, pageDelta)", html_report)
        self.assertIn("function czkFilterCards(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId)", html_report)
        self.assertIn("function czkChangePage(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId, pageDelta)", html_report)
        self.assertIn("function czkJumpPage(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId, target)", html_report)
        self.assertIn("function czkClearCardSearch(sectionId, inputId, sizeSelectId, pageStatusId, firstBtnId, prevBtnId, nextBtnId, lastBtnId)", html_report)
        self.assertIn("function czkOpenBackground(event)", html_report)
        self.assertIn("Scanner Exit Code: 0", html_report)
        self.assertIn('class="results-section"', html_report)
        self.assertIn("<h2>Results</h2>", html_report)
        self.assertIn("Showing 1 of 1 duplicate groups", html_report)
        self.assertIn("Search filenames", html_report)
        self.assertIn("Partial match across keep and remove files", html_report)
        self.assertIn("Items per page", html_report)
        self.assertIn('option value="25" selected', html_report)
        self.assertIn('option value="50">50</option>', html_report)
        self.assertIn('option value="100">100</option>', html_report)
        self.assertIn(">First</button>", html_report)
        self.assertIn(">Previous</button>", html_report)
        self.assertIn(">Next</button>", html_report)
        self.assertIn(">Last</button>", html_report)
        self.assertIn("Page 1 of 1", html_report)
        self.assertIn("czkFilterCards('dup-cards-images-1', 'dup-cards-images-1-search', 'dup-cards-images-1-page-size', 'dup-cards-images-1-page-status', 'dup-cards-images-1-page-first', 'dup-cards-images-1-page-prev', 'dup-cards-images-1-page-next', 'dup-cards-images-1-page-last')", html_report)
        self.assertIn("czkFilterCards('dup-cards-videos-2', 'dup-cards-videos-2-search', 'dup-cards-videos-2-page-size', 'dup-cards-videos-2-page-status', 'dup-cards-videos-2-page-first', 'dup-cards-videos-2-page-prev', 'dup-cards-videos-2-page-next', 'dup-cards-videos-2-page-last')", html_report)
        self.assertIn("czkClearCardSearch('dup-cards-images-1', 'dup-cards-images-1-search', 'dup-cards-images-1-page-size', 'dup-cards-images-1-page-status', 'dup-cards-images-1-page-first', 'dup-cards-images-1-page-prev', 'dup-cards-images-1-page-next', 'dup-cards-images-1-page-last')", html_report)
        self.assertIn("czkChangePage('dup-cards-images-1', 'dup-cards-images-1-search', 'dup-cards-images-1-page-size', 'dup-cards-images-1-page-status', 'dup-cards-images-1-page-first', 'dup-cards-images-1-page-prev', 'dup-cards-images-1-page-next', 'dup-cards-images-1-page-last', -1)", html_report)
        self.assertIn("czkJumpPage('dup-cards-images-1', 'dup-cards-images-1-search', 'dup-cards-images-1-page-size', 'dup-cards-images-1-page-status', 'dup-cards-images-1-page-first', 'dup-cards-images-1-page-prev', 'dup-cards-images-1-page-next', 'dup-cards-images-1-page-last', 'first')", html_report)
        self.assertIn("czkJumpPage('dup-cards-images-1', 'dup-cards-images-1-search', 'dup-cards-images-1-page-size', 'dup-cards-images-1-page-status', 'dup-cards-images-1-page-first', 'dup-cards-images-1-page-prev', 'dup-cards-images-1-page-next', 'dup-cards-images-1-page-last', 'last')", html_report)
        self.assertIn("Show all", html_report)
        self.assertIn("Collapse all", html_report)
        self.assertIn("Group:</strong>", html_report)
        self.assertIn("File to Keep", html_report)
        self.assertIn("Files to Remove", html_report)
        self.assertIn("Marked for Removal", html_report)
        self.assertIn('class="dup-card"', html_report)
        self.assertNotIn('class="duplicate-table"', html_report)
        self.assertNotIn("file_to_keep", html_report)
        self.assertNotIn("files_to_remove", html_report)
        self.assertNotIn("remove_count", html_report)
        self.assertNotIn('class="dup-card" open', html_report)
        self.assertIn("querySelectorAll('.dup-card')", html_report)
        self.assertIn('class="dup-cards" data-page="1"', html_report)
        self.assertIn('data-search="keep-image.jpg remove-image.jpg"', html_report)
        self.assertIn("<img ", html_report)
        self.assertIn("<video controls preload=\"metadata\" muted>", html_report)
        self.assertIn(">Open</a>", html_report)
        self.assertIn("onclick=\"return czkOpenBackground(event)\"", html_report)
        self.assertIn("Size:</strong>", html_report)
        self.assertIn("Modified:</strong>", html_report)
        self.assertIn("Resolution:</strong>", html_report)
        self.assertIn("640x480", html_report)
        self.assertIn("Resolution:</strong> -", html_report)
        self.assertIn("images.json", html_report)
        self.assertIn("videos.csv", html_report)

    def test_build_html_report_honors_top_and_hides_path_row(self) -> None:
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
                metadata_by_path={
                    "/tmp/folder/<bad>&keep.jpg": MediaItemMetadata(
                        size_bytes=1234,
                        modified_epoch=1_700_000_000,
                        width=1920,
                        height=1080,
                    ),
                    "/tmp/folder/remove 1.jpg": MediaItemMetadata(
                        size_bytes=1200,
                        modified_epoch=1_700_000_100,
                        width=800,
                        height=600,
                    ),
                    "/tmp/folder/remove 2.jpg": MediaItemMetadata(
                        size_bytes=1100,
                        modified_epoch=1_700_000_200,
                        width=640,
                        height=480,
                    ),
                },
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
        self.assertIn("Resolution:</strong> 1920x1080", report)
        self.assertNotIn('class="media-path"', report)
        self.assertIn(str(csv_path), report)

    def test_build_html_report_paginates_cards_with_default_25(self) -> None:
        visual_rows = [
            DuplicateVisualRow(
                index=index,
                file_to_keep=f"/tmp/item-{index}.jpg",
                files_to_remove=[f"/tmp/item-{index}-dup.jpg"],
                remove_count=1,
            )
            for index in range(1, 31)
        ]
        report = build_html_report(
            run_context=VizRunContext(
                run_mode="VIZ (DRY RUN)",
                target_dir=Path("/tmp"),
                out_dir=Path("/tmp"),
                timestamp="20260209-090900",
                media_targets=["images"],
            ),
            media_sections=[
                VizMediaSection(
                    media="images",
                    command_preview="czkawka_cli image --dry-run",
                    exit_code=0,
                    summary=MediaSummary(
                        total_found=30,
                        duplicate_groups=30,
                        duplicates_to_remove=30,
                        after_remove_estimate=0,
                    ),
                    json_path=Path("/tmp/images.json"),
                    csv_path=Path("/tmp/images.csv"),
                    visual_rows=visual_rows,
                    shown_rows=30,
                    total_rows=30,
                    metadata_by_path={},
                )
            ],
        )

        self.assertIn("Page 1 of 2", report)
        self.assertIn('data-group-index="26" data-search="item-26.jpg item-26-dup.jpg" hidden', report)
        self.assertIn(">First</button>", report)
        self.assertIn(">Last</button>", report)
        self.assertNotIn(
            'id="dup-cards-images-1-page-next" class="control-btn" onclick="czkChangePage(\'dup-cards-images-1\', \'dup-cards-images-1-search\', \'dup-cards-images-1-page-size\', \'dup-cards-images-1-page-status\', \'dup-cards-images-1-page-first\', \'dup-cards-images-1-page-prev\', \'dup-cards-images-1-page-next\', \'dup-cards-images-1-page-last\', 1)" disabled>Next</button>',
            report,
        )

    def test_build_html_report_omits_item_actions_when_path_is_blank(self) -> None:
        report = build_html_report(
            run_context=VizRunContext(
                run_mode="VIZ (DRY RUN)",
                target_dir=Path("/tmp"),
                out_dir=Path("/tmp"),
                timestamp="20260209-091000",
                media_targets=["images"],
            ),
            media_sections=[
                VizMediaSection(
                    media="images",
                    command_preview="czkawka_cli image --dry-run",
                    exit_code=0,
                    summary=MediaSummary(
                        total_found=0,
                        duplicate_groups=1,
                        duplicates_to_remove=0,
                        after_remove_estimate=0,
                    ),
                    json_path=Path("/tmp/images.json"),
                    csv_path=Path("/tmp/images.csv"),
                    visual_rows=[
                        DuplicateVisualRow(
                            index=1,
                            file_to_keep="",
                            files_to_remove=[],
                            remove_count=0,
                        )
                    ],
                    shown_rows=1,
                    total_rows=1,
                    metadata_by_path={},
                )
            ],
        )

        self.assertIn("Preview unavailable", report)
        self.assertNotIn(">Open</a>", report)


if __name__ == "__main__":
    unittest.main()
