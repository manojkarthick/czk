from __future__ import annotations

import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from czk_tool.duckdb_shell import (  # noqa: E402
    ExpandedDuplicateRow,
    JsonDuplicateRow,
    MediaInventoryRow,
    build_expanded_rows,
    build_json_rows,
    collect_media_inventory,
    ensure_duckdb_cli,
    launch_duckdb_session,
)


class DuckdbShellTests(unittest.TestCase):
    def test_collect_media_inventory_filters_by_media(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "one.jpg").write_bytes(b"a")
            (root / "two.mp4").write_bytes(b"b")
            (root / "three.txt").write_bytes(b"c")

            image_rows = collect_media_inventory(root, ["images"])
            both_rows = collect_media_inventory(root, ["images", "videos"])

            self.assertEqual(len(image_rows), 1)
            self.assertEqual(image_rows[0].media_type, "images")
            self.assertEqual(Path(image_rows[0].path).name, "one.jpg")

            self.assertEqual(len(both_rows), 2)
            media_types = {row.media_type for row in both_rows}
            self.assertEqual(media_types, {"images", "videos"})

    def test_build_expanded_rows_parses_remove_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "dupes.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["index", "file_to_keep", "files_to_remove", "count"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "index": 1,
                        "file_to_keep": "/tmp/keep.jpg",
                        "files_to_remove": json.dumps(["/tmp/a.jpg", "/tmp/b.jpg"]),
                        "count": 2,
                    }
                )

            expanded = build_expanded_rows(csv_path, "images")
            self.assertEqual(len(expanded), 2)
            self.assertEqual(expanded[0].group_index, 1)
            self.assertEqual(expanded[0].remove_ordinal, 1)
            self.assertEqual(expanded[1].remove_ordinal, 2)
            self.assertEqual(expanded[0].group_remove_count, 2)

    def test_build_expanded_rows_empty_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "dupes.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["index", "file_to_keep", "files_to_remove", "count"],
                )
                writer.writeheader()

            expanded = build_expanded_rows(csv_path, "videos")
            self.assertEqual(expanded, [])

    def test_build_json_rows_extracts_grouped_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "report.json"
            json_path.write_text(
                json.dumps(
                    [
                        [
                            {"path": "/tmp/a.jpg", "size": 100, "modified_date": 10},
                            {"path": "/tmp/b.jpg", "size": 90, "modified_date": 20},
                        ],
                        [{"path": "/tmp/c.jpg"}],
                    ]
                ),
                encoding="utf-8",
            )
            rows = build_json_rows(json_path)

            self.assertEqual(len(rows), 3)
            self.assertIsInstance(rows[0], JsonDuplicateRow)
            self.assertEqual(rows[0].group_index, 1)
            self.assertEqual(rows[0].item_index, 1)
            self.assertEqual(rows[0].path, "/tmp/a.jpg")
            self.assertEqual(rows[2].group_index, 2)
            self.assertEqual(rows[2].item_index, 1)

    def test_ensure_duckdb_cli_raises_when_missing(self) -> None:
        with patch("czk_tool.duckdb_shell.shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "duckdb CLI"):
                ensure_duckdb_cli()

    def test_launch_duckdb_session_uses_memory_and_quiet_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            duplicate_csv = Path(tmp_dir) / "images.csv"
            with duplicate_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["index", "file_to_keep", "files_to_remove", "count"],
                )
                writer.writeheader()

            duplicate_json = Path(tmp_dir) / "images-report.json"
            duplicate_json.write_text(
                json.dumps([[{"path": "/tmp/one.jpg", "size": 1, "modified_date": 1}]]),
                encoding="utf-8",
            )

            captured: dict[str, object] = {}

            def fake_run(command: list[str], check: bool) -> subprocess.CompletedProcess[str]:
                captured["command"] = command
                read_command = next(part for part in command if part.startswith(".read "))
                init_path_text = read_command[len(".read ") :].strip()
                if init_path_text.startswith('"') and init_path_text.endswith('"'):
                    init_path_text = init_path_text[1:-1]
                init_path = Path(init_path_text.replace('""', '"'))
                captured["sql"] = init_path.read_text(encoding="utf-8")
                return subprocess.CompletedProcess(command, 0)

            with patch("czk_tool.duckdb_shell.subprocess.run", side_effect=fake_run):
                exit_code = launch_duckdb_session(
                    media_targets=["images"],
                    duckdb_executable="/usr/local/bin/duckdb",
                    duplicate_csv_paths={"images": duplicate_csv},
                    duplicate_json_paths={"images": duplicate_json},
                    inventory_rows=[
                        MediaInventoryRow(
                            media_type="images",
                            path="/tmp/one.jpg",
                            file_name="one.jpg",
                            extension="jpg",
                            size_bytes=1,
                            modified_epoch=1,
                        )
                    ],
                    expanded_rows={
                        "images": [
                            ExpandedDuplicateRow(
                                group_index=1,
                                file_to_keep="/tmp/one.jpg",
                                remove_path="/tmp/two.jpg",
                                remove_ordinal=1,
                                group_remove_count=1,
                            )
                        ]
                    },
                )

            self.assertEqual(exit_code, 0)
            command = captured["command"]
            self.assertIsInstance(command, list)
            self.assertIn(":memory:", command)
            self.assertIn("-cmd", command)
            self.assertIn(".output stdout", command)
            self.assertNotIn("-init", command)
            sql = str(captured["sql"])
            self.assertIn("CREATE OR REPLACE TABLE media_inventory", sql)
            self.assertIn("CREATE OR REPLACE TABLE duplicates_images", sql)
            self.assertIn("CREATE OR REPLACE TABLE duplicates_images_json", sql)
            self.assertIn("read_csv_auto", sql)
            self.assertIn("CREATE OR REPLACE TABLE duplicates_images_expanded", sql)
            self.assertNotIn("CREATE OR REPLACE TABLE duplicates_videos", sql)
            self.assertNotIn("CREATE OR REPLACE TABLE duplicates_videos_json", sql)
            self.assertNotIn("CREATE OR REPLACE TABLE duplicates_videos_expanded", sql)


if __name__ == "__main__":
    unittest.main()
