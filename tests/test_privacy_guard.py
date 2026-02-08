from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_SUFFIXES = {".py", ".md", ".sh", ".toml", ".yaml", ".yml", ".json", ".txt"}
SKIP_FILES = {"tests/test_privacy_guard.py"}
PATTERNS = [
    re.compile(r"/(?:Users|home)/[^/\s]+/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\[^\\\\\s]+\\\\"),
]


class PrivacyGuardTests(unittest.TestCase):
    def test_tracked_files_have_no_machine_specific_user_paths(self) -> None:
        tracked_files = self._tracked_files()
        offenses: list[str] = []

        for relative_path in tracked_files:
            if relative_path in SKIP_FILES:
                continue
            path = ROOT / relative_path
            if not path.exists() or not path.is_file():
                continue
            if path.suffix.lower() not in ALLOWED_SUFFIXES:
                continue

            for line_number, line in self._safe_read_lines(path):
                for pattern in PATTERNS:
                    if pattern.search(line):
                        offenses.append(
                            f"{relative_path}:{line_number}: {line.strip()}"
                        )
                        break

        if offenses:
            self.fail(
                "Found machine-specific user paths in tracked files:\n"
                + "\n".join(offenses)
            )

    def _tracked_files(self) -> list[str]:
        completed = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return [line for line in completed.stdout.splitlines() if line]

    def _safe_read_lines(self, path: Path) -> list[tuple[int, str]]:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return []
        return list(enumerate(content.splitlines(), start=1))


if __name__ == "__main__":
    unittest.main()

