from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Literal

MediaType = Literal["images", "videos"]
SUCCESS_CODES = {0, 11}


def ensure_czkawka_cli() -> str:
    """Resolve the `czkawka_cli` executable from PATH.

    Returns:
        Absolute path to the discovered executable.

    Raises:
        RuntimeError: If `czkawka_cli` is not installed or missing in PATH.
    """
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
    hash_alg: str,
    image_filter: str,
    video_tolerance: int,
) -> list[str]:
    """Build the Czkawka CLI command for a single media scan.

    Args:
        executable: Path to the `czkawka_cli` binary.
        media: Media mode (`images` or `videos`).
        target_dir: Directory to scan.
        pretty_json_path: Destination path for Czkawka's pretty JSON output.
        dry_run: Whether to run in dry-run mode.
        image_similarity: Similarity preset for image scanning.
        hash_size: Perceptual hash size for images.
        hash_alg: Hash algorithm for image scanning.
        image_filter: Image filter used for hashing.
        video_tolerance: Similarity tolerance for video scanning.

    Returns:
        Full argument vector ready for `subprocess.run`.
    """
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
            "-g",
            hash_alg,
            "-z",
            image_filter,
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
    """Render a command list as a shell-safe string.

    Args:
        command: Command tokens.

    Returns:
        Shell-escaped command line representation.
    """
    return shlex.join(command)


def run_czkawka(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Execute Czkawka and enforce allowed success exit codes.

    Args:
        command: Full Czkawka command tokens.

    Returns:
        Completed process object with stdout/stderr captured as text.

    Raises:
        RuntimeError: If Czkawka exits with a non-success code.
    """
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
