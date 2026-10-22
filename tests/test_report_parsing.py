from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from czk_tool import report
from czk_tool.report import build_rows, delete_marked_files, load_duplicate_groups


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

    def test_size_tie_keeps_newest(self) -> None:
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

        rows = build_rows(groups)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].file_to_keep, "/tmp/library/images/file_b.jpg")
        self.assertEqual(rows[0].files_to_remove, ["/tmp/library/images/file_a.jpg"])
        self.assertEqual(rows[0].count, 1)

    def test_keeps_biggest_even_if_older(self) -> None:
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

        rows = build_rows(groups)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].file_to_keep, "/tmp/library/videos/file_b.mp4")
        self.assertEqual(rows[0].files_to_remove, ["/tmp/library/videos/file_a.mp4"])
        self.assertEqual(rows[0].count, 1)

    def test_size_and_date_tie_keeps_lexicographically_first_path(self) -> None:
        groups = [
            [
                {"path": "/tmp/library/images/file_b.jpg", "size": 100, "modified_date": 5},
                {"path": "/tmp/library/images/file_a.jpg", "size": 100, "modified_date": 5},
            ]
        ]

        rows = build_rows(groups)
        self.assertEqual(rows[0].file_to_keep, "/tmp/library/images/file_a.jpg")
        self.assertEqual(rows[0].files_to_remove, ["/tmp/library/images/file_b.jpg"])

    def test_delete_marked_files_trashes_only_marked_paths(self) -> None:
        rows = build_rows(
            [
                [
                    {"path": "/tmp/library/remove.jpg", "size": 3, "modified_date": 2},
                    {"path": "/tmp/library/keep.jpg", "size": 5, "modified_date": 1},
                ]
            ]
        )
        with patch.object(report.Path, "is_file", return_value=True), patch.object(
            report.Path, "exists", return_value=True
        ), patch.object(report, "send2trash") as trash_mock:
            failures = delete_marked_files(rows)

        self.assertEqual(failures, [])
        trash_mock.assert_called_once_with("/tmp/library/remove.jpg")

    def test_delete_marked_files_skips_group_when_keeper_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            keep_path = Path(tmp_dir) / "keep.jpg"
            remove_path = Path(tmp_dir) / "remove.jpg"
            remove_path.write_bytes(b"dup")

            rows = build_rows(
                [
                    [
                        {"path": str(remove_path), "size": 3, "modified_date": 2},
                        {"path": str(keep_path), "size": 5, "modified_date": 1},
                    ]
                ]
            )
            failures = delete_marked_files(rows)

            self.assertEqual(len(failures), 1)
            self.assertTrue(remove_path.exists())


    def test_delete_marked_files_reports_trash_errors(self) -> None:
        rows = build_rows(
            [
                [
                    {"path": "/tmp/library/remove.jpg", "size": 3, "modified_date": 2},
                    {"path": "/tmp/library/keep.jpg", "size": 5, "modified_date": 1},
                ]
            ]
        )
        with patch.object(report.Path, "is_file", return_value=True), patch.object(
            report.Path, "exists", return_value=True
        ), patch.object(report, "send2trash", side_effect=OSError("trash unavailable")):
            failures = delete_marked_files(rows)

        self.assertEqual(len(failures), 1)
        self.assertIn("/tmp/library/remove.jpg", failures[0])
        self.assertIn("trash unavailable", failures[0])

if __name__ == "__main__":
    unittest.main()

