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
    return Path(name).suffix.lower().lstrip(".")


def count_media_files(root: Path, media: MediaType) -> int:
    extensions = IMAGE_EXTENSIONS if media == "images" else VIDEO_EXTENSIONS
    total = 0
    for _, _, file_names in os.walk(root, followlinks=False):
        for file_name in file_names:
            if _extension(file_name) in extensions:
                total += 1
    return total

