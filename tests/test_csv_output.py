from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from czk_tool.report import (
    DuplicateRow,
    build_preview_rows_from_csv,
    build_pretty_table_from_csv,
    write_csv,
)


class CsvOutputTests(unittest.TestCase):
    def test_write_csv_uses_expected_columns_and_json_array(self) -> None:
        rows = [
            DuplicateRow(
                index=1,
                file_to_keep="/tmp/a.jpg",
                files_to_remove=["/tmp/b.jpg", "/tmp/c.jpg"],
                count=2,
            ),
            DuplicateRow(
                index=2,
                file_to_keep="/tmp/d.jpg",
                files_to_remove=["/tmp/e.jpg"],
                count=1,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "report.csv"
            write_csv(rows, csv_path)

            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                loaded = list(reader)
                self.assertEqual(reader.fieldnames, ["index", "file_to_keep", "files_to_remove", "count"])

            self.assertEqual(len(loaded), 2)
            self.assertEqual(json.loads(loaded[0]["files_to_remove"]), ["/tmp/b.jpg", "/tmp/c.jpg"])
            self.assertEqual(loaded[0]["count"], "2")

    def test_pretty_table_reads_back_from_csv_and_honors_top(self) -> None:
        rows = [
            DuplicateRow(index=1, file_to_keep="/tmp/one", files_to_remove=["/tmp/x"], count=1),
            DuplicateRow(index=2, file_to_keep="/tmp/two", files_to_remove=["/tmp/y"], count=1),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "report.csv"
            write_csv(rows, csv_path)

            table, total, shown = build_pretty_table_from_csv(csv_path, top=1)

            self.assertIn("file_to_keep", table)
            self.assertEqual(total, 2)
            self.assertEqual(shown, 1)

    def test_build_preview_rows_from_csv_extracts_first_remove(self) -> None:
        rows = [
            DuplicateRow(
                index=1,
                file_to_keep="/tmp/keep.jpg",
                files_to_remove=["/tmp/r1.jpg", "/tmp/r2.jpg"],
                count=2,
            )
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "report.csv"
            write_csv(rows, csv_path)
            preview_rows, total_rows, shown_rows = build_preview_rows_from_csv(csv_path, top=10)

            self.assertEqual(total_rows, 1)
            self.assertEqual(shown_rows, 1)
            self.assertEqual(preview_rows[0].index, 1)
            self.assertEqual(preview_rows[0].file_to_keep, "/tmp/keep.jpg")
            self.assertEqual(preview_rows[0].remove_count, 2)
            self.assertEqual(preview_rows[0].first_remove, "/tmp/r1.jpg")


if __name__ == "__main__":
    unittest.main()
