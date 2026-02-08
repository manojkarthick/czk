from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

MediaType = Literal["images", "videos"]

# Includes Czkawka macro defaults plus common variants users typically store.
IMAGE_EXTENSIONS = {
    "avif",
    "bmp",
    "gif",
    "hdr",
    "heic",
    "heif",
    "jpeg",
    "jpg",
    "kra",
    "png",
    "svg",
    "tif",
    "tiff",
    "webp",
}

VIDEO_EXTENSIONS = {
    "3gp",
    "avi",
    "flv",
    "gifv",
    "m4p",
    "m4v",
    "mkv",
    "mov",
    "mp4",
    "mpeg",
    "mpg",
    "ogv",
    "vob",
    "webm",
    "wmv",
}


def _extension(name: str) -> str:
    """Extract a lowercase extension without the leading dot.

    Args:
        name: File name or path string.

    Returns:
        Normalized file extension, or an empty string when missing.
    """
    return Path(name).suffix.lower().lstrip(".")


def count_media_files(root: Path, media: MediaType) -> int:
    """Count files matching known image/video extensions under a directory.

    Args:
        root: Directory to scan recursively.
        media: Media class to count (`images` or `videos`).

    Returns:
        Number of files matching the extension allowlist for the media type.
    """
    extensions = IMAGE_EXTENSIONS if media == "images" else VIDEO_EXTENSIONS
    total = 0
    for _, _, file_names in os.walk(root, followlinks=False):
        for file_name in file_names:
            if _extension(file_name) in extensions:
                total += 1
    return total
