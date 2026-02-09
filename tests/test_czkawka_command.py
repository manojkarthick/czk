from __future__ import annotations

import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from czk_tool.czkawka import build_czkawka_command


class CzkawkaCommandTests(unittest.TestCase):
    def test_build_image_command_includes_hash_alg_and_image_filter(self) -> None:
        command = build_czkawka_command(
            executable="/opt/homebrew/bin/czkawka_cli",
            media="images",
            target_dir=Path("/tmp/data"),
            pretty_json_path=Path("/tmp/report.json"),
            dry_run=True,
            image_similarity="High",
            hash_size=32,
            hash_alg="Blockhash",
            image_filter="Catmullrom",
            video_tolerance=10,
        )

        self.assertIn("image", command)
        self.assertIn("-g", command)
        self.assertIn("Blockhash", command)
        self.assertIn("-z", command)
        self.assertIn("Catmullrom", command)
        self.assertIn("--dry-run", command)

    def test_build_video_command_ignores_image_specific_flags(self) -> None:
        command = build_czkawka_command(
            executable="/opt/homebrew/bin/czkawka_cli",
            media="videos",
            target_dir=Path("/tmp/data"),
            pretty_json_path=Path("/tmp/report.json"),
            dry_run=False,
            image_similarity="High",
            hash_size=32,
            hash_alg="Median",
            image_filter="Faussian",
            video_tolerance=12,
        )

        self.assertIn("video", command)
        self.assertNotIn("-g", command)
        self.assertNotIn("Median", command)
        self.assertNotIn("-z", command)
        self.assertNotIn("Faussian", command)
        self.assertNotIn("--dry-run", command)


if __name__ == "__main__":
    unittest.main()
