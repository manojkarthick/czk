from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from czk_tool import cli
from czk_tool.cli import parse_args


class CliArgTests(unittest.TestCase):
    def test_test_defaults(self) -> None:
        args = parse_args(["test"])
        self.assertEqual(args.command, "test")
        self.assertEqual(args.directory, ".")
        self.assertEqual(args.media, "both")
        self.assertEqual(args.hash_size, 32)
        self.assertEqual(args.image_similarity, "High")
        self.assertEqual(args.video_tolerance, 10)
        self.assertEqual(args.top, 50)
        self.assertEqual(args.out_dir, ".")
        self.assertFalse(args.no_color)

    def test_execute_with_overrides(self) -> None:
        args = parse_args(
            [
                "execute",
                "/tmp/data",
                "--media",
                "videos",
                "--video-tolerance",
                "20",
                "--top",
                "7",
                "--out-dir",
                "/tmp/out",
            ]
        )
        self.assertEqual(args.command, "execute")
        self.assertEqual(args.directory, "/tmp/data")
        self.assertEqual(args.media, "videos")
        self.assertEqual(args.video_tolerance, 20)
        self.assertEqual(args.top, 7)
        self.assertEqual(args.out_dir, "/tmp/out")

    def test_no_color_flag(self) -> None:
        args = parse_args(["execute", "--no-color"])
        self.assertTrue(args.no_color)

    def test_invalid_video_tolerance(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["test", "--video-tolerance", "21"])

    def test_main_does_not_render_combined_summary(self) -> None:
        with patch.object(cli, "ensure_czkawka_cli", return_value="/opt/homebrew/bin/czkawka_cli"), patch.object(
            cli, "_run_one_media", return_value=None
        ), patch.object(cli.Renderer, "render_run_header"), patch.object(
            cli.Renderer, "render_combined_summary", create=True
        ) as combined_mock:
            exit_code = cli.main(["test", ".", "--media", "images", "--no-color"])
            self.assertEqual(exit_code, 0)
            combined_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
