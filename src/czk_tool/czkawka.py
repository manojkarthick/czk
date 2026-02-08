from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Literal

MediaType = Literal["images", "videos"]
SUCCESS_CODES = {0, 11}


def ensure_czkawka_cli() -> str:
    executable = shutil.which("czkawka_cli")
    if executable is None:
        raise RuntimeError("czkawka_cli is not installed or not available in PATH.")
    return executable


def build_czkawka_command(
    *,
    executable: str,
    media: MediaType,
    target_dir: Path,
    pretty_json_path: Path,
    dry_run: bool,
    image_similarity: str,
    hash_size: int,
    video_tolerance: int,
) -> list[str]:
    if media == "images":
        command = [
            executable,
            "image",
            "-d",
            str(target_dir),
            "-s",
            image_similarity,
            "-c",
            str(hash_size),
            "-D",
            "AEB",
            "-p",
            str(pretty_json_path),
            "-W",
        ]
    else:
        command = [
            executable,
            "video",
            "-d",
            str(target_dir),
            "-t",
            str(video_tolerance),
            "-D",
            "AEB",
            "-p",
            str(pretty_json_path),
            "-W",
        ]

    if dry_run:
        command.append("--dry-run")

    return command


def format_command(command: list[str]) -> str:
    return shlex.join(command)


def run_czkawka(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode not in SUCCESS_CODES:
        raise RuntimeError(
            "Czkawka command failed.\n"
            f"Command: {format_command(command)}\n"
            f"Exit code: {completed.returncode}\n"
            f"stdout:\n{completed.stdout.strip()}\n"
            f"stderr:\n{completed.stderr.strip()}"
        )
    return completed

