from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from czk_tool.report import build_rows, load_duplicate_groups


class ReportParsingTests(unittest.TestCase):
    def test_load_duplicate_groups_from_synthetic_json(self) -> None:
        payload = [
            [
                {
                    "path": "/tmp/library/images/file_a.jpg",
                    "size": 100,
                    "modified_date": 1,
                },
                {
                    "path": "/tmp/library/images/file_b.jpg",
                    "size": 100,
                    "modified_date": 2,
                },
            ],
            [
                {
                    "path": "/tmp/library/images/file_c.jpg",
                    "size": 200,
                    "modified_date": 2,
                },
                {
                    "path": "/tmp/library/images/file_d.jpg",
                    "size": 180,
                    "modified_date": 1,
                },
            ],
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "dupes.json"
            json_path.write_text(json.dumps(payload), encoding="utf-8")
            groups = load_duplicate_groups(json_path)

        self.assertEqual(len(groups), 2)
        self.assertEqual(len(groups[0]), 2)
        self.assertEqual(groups[0][0]["path"], "/tmp/library/images/file_a.jpg")

    def test_image_aeb_projection_uses_oldest_on_size_tie(self) -> None:
        groups = [
            [
                {
                    "path": "/tmp/library/images/file_a.jpg",
                    "size": 100,
                    "modified_date": 1,
                },
                {
                    "path": "/tmp/library/images/file_b.jpg",
                    "size": 100,
                    "modified_date": 3,
                },
            ]
        ]

        rows = build_rows(groups, mode="test")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].file_to_keep, "/tmp/library/images/file_a.jpg")
        self.assertEqual(rows[0].files_to_remove, ["/tmp/library/images/file_b.jpg"])
        self.assertEqual(rows[0].count, 1)

    def test_video_aeb_projection_keeps_biggest(self) -> None:
        groups = [
            [
                {
                    "path": "/tmp/library/videos/file_a.mp4",
                    "size": 2000,
                    "modified_date": 20,
                },
                {
                    "path": "/tmp/library/videos/file_b.mp4",
                    "size": 3000,
                    "modified_date": 10,
                },
            ]
        ]

        rows = build_rows(groups, mode="test")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].file_to_keep, "/tmp/library/videos/file_b.mp4")
        self.assertEqual(rows[0].files_to_remove, ["/tmp/library/videos/file_a.mp4"])
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

