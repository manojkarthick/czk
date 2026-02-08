from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from czk_tool.report import build_rows, load_duplicate_groups


class ReportParsingTests(unittest.TestCase):
    def test_load_image_fixture_groups(self) -> None:
        image_json = ROOT / "all-image-dupes.json"
        groups = load_duplicate_groups(image_json)
        self.assertEqual(len(groups), 240)
        self.assertTrue(all(len(group) == 2 for group in groups))

    def test_image_aeb_projection_uses_oldest_on_size_tie(self) -> None:
        image_json = ROOT / "all-image-dupes.json"
        groups = load_duplicate_groups(image_json)
        rows = build_rows(groups[:1], mode="test")

        self.assertEqual(len(rows), 1)
        self.assertTrue(
            rows[0].file_to_keep.endswith("miaamabile_CV6RgoWs1cO_20211105_2.jpg")
        )
        self.assertEqual(rows[0].count, 1)
        self.assertTrue(
            rows[0].files_to_remove[0].endswith(
                "miadrudolph_1636150421_2700547930622873296_38937563.jpg"
            )
        )

    def test_video_aeb_projection_keeps_biggest(self) -> None:
        video_json = ROOT / "all-video-dupes.json"
        groups = load_duplicate_groups(video_json)
        rows = build_rows(groups[:1], mode="test")

        self.assertEqual(len(rows), 1)
        self.assertTrue(
            rows[0].file_to_keep.endswith("miaamabile_CL3ICvWBvGG_20210301_2.mp4")
        )
        self.assertEqual(rows[0].count, 1)

    def test_execute_mode_uses_filesystem_when_conclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            keep_path = Path(tmp_dir) / "keep.jpg"
            remove_path = Path(tmp_dir) / "remove.jpg"
            keep_path.write_bytes(b"keep")

            group = [
                {
                    "path": str(remove_path),
                    "size": 10,
                    "modified_date": 2,
                },
                {
                    "path": str(keep_path),
                    "size": 9,
                    "modified_date": 1,
                },
            ]

            rows = build_rows([group], mode="execute")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].file_to_keep, str(keep_path))
            self.assertEqual(rows[0].files_to_remove, [str(remove_path)])
            self.assertEqual(rows[0].count, 1)


if __name__ == "__main__":
    unittest.main()

