from __future__ import annotations

import unittest
import tempfile
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
        self.assertEqual(args.hash_alg, "Gradient")
        self.assertEqual(args.image_filter, "Nearest")
        self.assertEqual(args.image_similarity, "High")
        self.assertEqual(args.video_tolerance, 10)
        self.assertEqual(args.top, 50)
        self.assertIsNone(args.out_dir)
        self.assertFalse(args.no_color)

    def test_execute_with_overrides(self) -> None:
        args = parse_args(
            [
                "execute",
                "/tmp/data",
                "--media",
                "videos",
                "-t",
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

    def test_check_alias_resolves_to_test(self) -> None:
        args = parse_args(["check"])
        self.assertEqual(args.command, "test")

    def test_analyze_defaults(self) -> None:
        args = parse_args(["analyze"])
        self.assertEqual(args.command, "analyze")
        self.assertEqual(args.directory, ".")
        self.assertEqual(args.media, "both")
        self.assertEqual(args.hash_size, 32)
        self.assertEqual(args.hash_alg, "Gradient")
        self.assertEqual(args.image_filter, "Nearest")
        self.assertEqual(args.video_tolerance, 10)
        self.assertIsNone(args.out_dir)
        self.assertFalse(args.no_color)

    def test_analyse_alias_resolves_to_analyze(self) -> None:
        args = parse_args(["analyse"])
        self.assertEqual(args.command, "analyze")

    def test_viz_defaults(self) -> None:
        args = parse_args(["viz"])
        self.assertEqual(args.command, "viz")
        self.assertEqual(args.directory, ".")
        self.assertEqual(args.media, "both")
        self.assertEqual(args.hash_size, 32)
        self.assertEqual(args.hash_alg, "Gradient")
        self.assertEqual(args.image_filter, "Nearest")
        self.assertEqual(args.image_similarity, "High")
        self.assertEqual(args.video_tolerance, 10)
        self.assertEqual(args.top, 50)
        self.assertIsNone(args.out_dir)
        self.assertFalse(args.no_color)

    def test_analyze_accepts_shared_flags(self) -> None:
        args = parse_args(
            [
                "analyze",
                "/tmp/data",
                "--media",
                "images",
                "-c",
                "64",
                "--hash-alg",
                "Blockhash",
                "--image-filter",
                "Catmullrom",
                "-s",
                "Low",
                "--out-dir",
                "/tmp/out",
            ]
        )
        self.assertEqual(args.command, "analyze")
        self.assertEqual(args.directory, "/tmp/data")
        self.assertEqual(args.media, "images")
        self.assertEqual(args.hash_size, 64)
        self.assertEqual(args.hash_alg, "Blockhash")
        self.assertEqual(args.image_filter, "Catmullrom")
        self.assertEqual(args.image_similarity, "Low")
        self.assertEqual(args.out_dir, "/tmp/out")

    def test_no_color_flag(self) -> None:
        args = parse_args(["execute", "--no-color"])
        self.assertTrue(args.no_color)

    def test_invalid_video_tolerance(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["test", "--tolerance", "21"])

    def test_main_does_not_render_combined_summary(self) -> None:
        with patch.object(cli, "ensure_czkawka_cli", return_value="/opt/homebrew/bin/czkawka_cli"), patch.object(
            cli, "_run_one_media", return_value=None
        ), patch.object(cli.Renderer, "render_run_header"), patch.object(
            cli.Renderer, "render_combined_summary", create=True
        ) as combined_mock:
            exit_code = cli.main(["test", ".", "--media", "images", "--no-color"])
            self.assertEqual(exit_code, 0)
            combined_mock.assert_not_called()

    def test_main_analyze_runs_duckdb_after_scan(self) -> None:
        with patch.object(cli, "ensure_czkawka_cli", return_value="/opt/homebrew/bin/czkawka_cli"), patch.object(
            cli, "ensure_duckdb_cli", return_value="/opt/homebrew/bin/duckdb"
        ), patch.object(cli, "_run_one_media", return_value=(Path("/tmp/a.json"), Path("/tmp/a.csv"))) as run_media_mock, patch.object(
            cli, "collect_media_inventory", return_value=[]
        ), patch.object(
            cli, "build_expanded_rows", return_value=[]
        ) as build_expanded_mock, patch.object(
            cli, "launch_duckdb_session", return_value=0
        ) as launch_mock, patch.object(
            cli.Renderer, "render_run_header"
        ), patch.object(
            cli.Renderer, "render_duckdb_intro"
        ):
            exit_code = cli.main(["analyze", ".", "--media", "images", "--no-color"])
            self.assertEqual(exit_code, 0)
            self.assertEqual(run_media_mock.call_count, 1)
            self.assertEqual(run_media_mock.call_args.kwargs["mode"], "analyze")
            self.assertEqual(run_media_mock.call_args.kwargs["hash_alg"], "Gradient")
            self.assertEqual(run_media_mock.call_args.kwargs["image_filter"], "Nearest")
            self.assertEqual(build_expanded_mock.call_count, 1)
            launch_mock.assert_called_once()
            self.assertIn("duplicate_json_paths", launch_mock.call_args.kwargs)

    def test_main_analyze_missing_duckdb_returns_nonzero(self) -> None:
        with patch.object(cli, "ensure_czkawka_cli", return_value="/opt/homebrew/bin/czkawka_cli"), patch.object(
            cli, "ensure_duckdb_cli", side_effect=RuntimeError("duckdb CLI is missing")
        ):
            exit_code = cli.main(["analyze", ".", "--media", "images", "--no-color"])
            self.assertEqual(exit_code, 1)

    def test_main_viz_opens_browser_and_skips_terminal_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch.object(
            cli, "ensure_czkawka_cli", return_value="/opt/homebrew/bin/czkawka_cli"
        ), patch.object(
            cli,
            "_scan_one_media",
            return_value=cli._MediaRunResult(
                command=["/opt/homebrew/bin/czkawka_cli", "image", "--dry-run"],
                exit_code=0,
                summary=cli.MediaSummary(
                    total_found=10,
                    duplicate_groups=2,
                    duplicates_to_remove=3,
                    after_remove_estimate=7,
                ),
                json_path=Path("/tmp/demo-images.json"),
                csv_path=Path("/tmp/demo-images.csv"),
            ),
        ) as scan_mock, patch.object(
            cli, "build_visual_rows_from_csv", return_value=([], 0, 0)
        ), patch.object(
            cli, "load_duplicate_groups", return_value=[]
        ), patch.object(
            cli, "build_html_report", return_value="<html><body>report</body></html>"
        ), patch.object(
            cli.webbrowser, "open", return_value=True
        ) as browser_open_mock, patch.object(
            cli.Renderer, "render_run_header"
        ) as run_header_mock:
            exit_code = cli.main(["viz", ".", "--media", "images", "--out-dir", tmp_dir, "--no-color"])

            self.assertEqual(exit_code, 0)
            self.assertEqual(scan_mock.call_count, 1)
            self.assertEqual(scan_mock.call_args.kwargs["hash_alg"], "Gradient")
            self.assertEqual(scan_mock.call_args.kwargs["image_filter"], "Nearest")
            browser_open_mock.assert_called_once()
            run_header_mock.assert_not_called()

            html_files = list(Path(tmp_dir).glob("*.html"))
            self.assertEqual(len(html_files), 1)

    def test_resolve_out_dir_defaults_to_shared_temp(self) -> None:
        with patch.object(cli.tempfile, "gettempdir", return_value="/tmp/czk-temp"):
            out_dir = cli._resolve_out_dir(None)
        self.assertEqual(out_dir, Path("/tmp/czk-temp/czk-reports").resolve())

    def test_main_uses_default_temp_out_dir_when_omitted(self) -> None:
        with patch.object(cli.tempfile, "gettempdir", return_value="/tmp/czk-temp"), patch.object(
            cli, "ensure_czkawka_cli", return_value="/opt/homebrew/bin/czkawka_cli"
        ), patch.object(
            cli, "_run_one_media", return_value=(Path("/tmp/a.json"), Path("/tmp/a.csv"))
        ) as run_media_mock, patch.object(
            cli.Renderer, "render_run_header"
        ):
            exit_code = cli.main(["test", ".", "--media", "images", "--no-color"])
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                run_media_mock.call_args.kwargs["out_dir"],
                Path("/tmp/czk-temp/czk-reports").resolve(),
            )

    def test_main_uses_explicit_out_dir_override(self) -> None:
        with patch.object(cli.tempfile, "gettempdir", return_value="/tmp/czk-temp"), patch.object(
            cli, "ensure_czkawka_cli", return_value="/opt/homebrew/bin/czkawka_cli"
        ), patch.object(
            cli, "_run_one_media", return_value=(Path("/tmp/a.json"), Path("/tmp/a.csv"))
        ) as run_media_mock, patch.object(
            cli.Renderer, "render_run_header"
        ):
            exit_code = cli.main(
                ["test", ".", "--media", "images", "--out-dir", "/tmp/custom", "--no-color"]
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(run_media_mock.call_args.kwargs["out_dir"], Path("/tmp/custom").resolve())


if __name__ == "__main__":
    unittest.main()
