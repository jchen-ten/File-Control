"""Compression of allowed files with splitting into multiple archives."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable, Sequence

from .config import Config
from .longpath import long_path
from .scanner import FileEntry

Logger = Callable[[str], None]

# Size of read/write blocks (streaming), to avoid loading entire files
# into memory.
_CHUNK = 1024 * 1024

# Already-compressed formats: recompressing them is slow for a negligible gain.
# We store them as-is (ZIP_STORED) to greatly speed up archiving.
_ALREADY_COMPRESSED = {
    "zip", "7z", "rar", "gz", "bz2", "xz",
    "pdf", "png", "jpg", "jpeg", "gif", "webp",
    "docx", "xlsx", "pptx", "odt", "ods", "odp",
    "mp3", "mp4", "avi", "mov", "mkv", "m4a", "aac",
}


def _compress_type_for(rel_path: PurePosixPath) -> int:
    ext = PurePosixPath(rel_path).suffix.lstrip(".").lower()
    return zipfile.ZIP_STORED if ext in _ALREADY_COMPRESSED else zipfile.ZIP_DEFLATED


def pack(
    entries: Sequence[FileEntry],
    archives_dir: Path,
    config: Config,
    log: Logger,
) -> list[Path]:
    """Compress the allowed files into one or more zip archives.

    A new archive is started as soon as adding a file would exceed
    `max_zip_size`. A file larger than the limit is placed alone in its own
    archive.
    """
    if not entries:
        log("No allowed files to compress.")
        return []

    archives_dir.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    part = 1
    current_size = 0
    current_zip: zipfile.ZipFile | None = None

    def open_new() -> zipfile.ZipFile:
        nonlocal part, current_size
        name = archives_dir / f"{config.archive_prefix}_{part:03d}.zip"
        log(f"Creating archive: {name.name}")
        handle = zipfile.ZipFile(long_path(name), "w", zipfile.ZIP_DEFLATED, allowZip64=True)
        created.append(name)
        current_size = 0
        return handle

    total = len(entries)
    current_zip = open_new()
    try:
        for index, entry in enumerate(entries, 1):
            if current_size > 0 and current_size + entry.size > config.max_zip_size:
                current_zip.close()
                part += 1
                current_zip = open_new()

            log(f"  Adding ({index}/{total}): {entry.rel_path} ({entry.size / (1024 * 1024):.1f} MB)")
            info = zipfile.ZipInfo(str(entry.rel_path))
            info.compress_type = _compress_type_for(entry.rel_path)
            with open(long_path(entry.source_path), "rb") as source, current_zip.open(info, "w") as dest:
                shutil.copyfileobj(source, dest, _CHUNK)
            current_size += entry.size
    finally:
        if current_zip is not None:
            current_zip.close()

    return created
