"""Recursive scan of folders and zip archives."""

from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator

from .config import Config
from .converter import target_for
from .longpath import long_path

Logger = Callable[[str], None]
MAX_FOLDER_DEPTH = 59


@dataclass
class FileEntry:
    """Represents a file discovered during the scan."""

    source_path: Path   # real location on disk (may be in a temporary folder)
    rel_path: PurePosixPath  # logical relative path used for the output
    size: int
    allowed: bool
    reason: str = ""
    convert_to: str = ""  # target extension if a conversion is possible


def safe_extract(zip_path: Path, dest_dir: Path) -> None:
    """Extract a zip archive while guarding against malicious paths (zip slip)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_root = dest_dir.resolve()
    with zipfile.ZipFile(long_path(zip_path)) as archive:
        for member in archive.infolist():
            target = (dest_dir / member.filename).resolve()
            if not str(target).startswith(str(dest_root)):
                raise ValueError(f"Unsafe archive path detected: {member.filename}")
            _extract_member(archive, member, dest_dir)


def _extract_member(archive: zipfile.ZipFile, member: zipfile.ZipInfo, dest_dir: Path) -> None:
    """Extract an archive member, handling Windows long paths and decompression errors."""
    target = dest_dir / member.filename
    if member.is_dir():
        Path(long_path(target)).mkdir(parents=True, exist_ok=True)
        return
    Path(long_path(target.parent)).mkdir(parents=True, exist_ok=True)
    try:
        with archive.open(member) as source, open(long_path(target), "wb") as handle:
            shutil.copyfileobj(source, handle)
    except RuntimeError as exc:
        # zlib decompression errors (e.g., -3 invalid block lengths) come as RuntimeError
        raise ValueError(f"Cannot decompress {member.filename}: {exc}") from exc


def _classify(path: Path, rel_path: PurePosixPath, config: Config) -> FileEntry:
    """Determine whether a file is allowed based on its format and size."""
    size = os.path.getsize(long_path(path))
    ext = path.suffix.lower().lstrip(".")
    reasons: list[str] = []

    allowed_exts = config.normalized_extensions
    format_ok = not allowed_exts or ext in allowed_exts
    if not format_ok:
        label = f".{ext}" if ext else "(no extension)"
        reasons.append(f"format {label} not allowed")

    size_ok = size <= config.max_file_size
    if not size_ok:
        reasons.append(
            f"size {size / (1024 * 1024):.1f} MB > limit {config.max_file_size_mb} MB"
        )

    # A conversion is only offered if the format is the only problem.
    convert_to = ""
    if config.convert_unsupported and not format_ok and size_ok:
        convert_to = target_for(ext, allowed_exts)

    return FileEntry(
        source_path=path,
        rel_path=rel_path,
        size=size,
        allowed=not reasons,
        reason=" ; ".join(reasons),
        convert_to=convert_to,
    )


def _reject_file(path: Path, rel_path: PurePosixPath, config: Config, reason: str) -> FileEntry:
    """Create a rejected entry for a file, preserving its size for reporting."""
    entry = _classify(path, rel_path, config)
    entry.allowed = False
    entry.convert_to = ""
    entry.reason = f"{reason} ; {entry.reason}" if entry.reason else reason
    return entry


def _reject_subtree(
    current_dir: Path,
    rel_prefix: PurePosixPath,
    temp_dir: Path,
    config: Config,
    log: Logger,
    reason: str,
) -> Iterator[FileEntry]:
    """Yield rejected entries for every file contained in a subtree."""
    with os.scandir(long_path(current_dir)) as it:
        children = sorted(it, key=lambda e: e.name.lower())
    for child in children:
        item = current_dir / child.name
        rel = rel_prefix / child.name
        if child.is_dir():
            yield from _reject_subtree(item, rel, temp_dir, config, log, reason)
        elif child.is_file():
            yield _reject_file(item, rel, config, reason)


def _has_duplicate_content(zip_path: Path, parent_dir: Path) -> bool:
    """Check if a ZIP file contains files already present in the parent directory.
    
    Returns True if the ZIP contains significant overlap with existing files,
    suggesting it's a duplicate extraction.
    """
    try:
        with zipfile.ZipFile(long_path(zip_path)) as archive:
            zip_members = set()
            for member in archive.namelist():
                # Get the first path component (top-level folder or file name)
                parts = member.split('/')
                if parts[0]:
                    zip_members.add(parts[0].lower())
            
            # Check for existing files/folders in the parent directory
            existing = set()
            try:
                with os.scandir(long_path(parent_dir)) as it:
                    for entry in it:
                        if entry.name.lower() != zip_path.name.lower():  # exclude the zip itself
                            existing.add(entry.name.lower())
            except (OSError, FileNotFoundError):
                return False
            
            # If there's any overlap, it's likely a duplicate
            overlap = zip_members & existing
            return len(overlap) > 0
    except (zipfile.BadZipFile, RuntimeError, ValueError):
        return False


def _walk(
    current_dir: Path,
    rel_prefix: PurePosixPath,
    temp_dir: Path,
    config: Config,
    log: Logger,
) -> Iterator[FileEntry]:
    with os.scandir(long_path(current_dir)) as it:
        children = sorted(it, key=lambda e: e.name.lower())
    for child in children:
        item = current_dir / child.name
        rel = rel_prefix / child.name
        if child.is_dir():
            depth = len(rel.parts)
            if depth > MAX_FOLDER_DEPTH:
                reason = f"folder depth {depth} exceeds limit {MAX_FOLDER_DEPTH}"
                log(f"Skipping subtree: {rel} ({reason})")
                yield from _reject_subtree(item, rel, temp_dir, config, log, reason)
                continue
            yield from _walk(item, rel, temp_dir, config, log)
        elif child.is_file():
            if item.suffix.lower() == ".zip" and config.recurse_zips:
                log(f"Extracting nested zip: {rel}")
                # Check for duplicate content before extraction
                if _has_duplicate_content(item, current_dir):
                    log(f"  ! ZIP contains files already present in this folder, rejected as duplicate")
                    entry = _classify(item, rel, config)
                    entry.allowed = False
                    entry.reason = (entry.reason + " ; " if entry.reason else "") + "contains duplicate extracted content"
                    yield entry
                    continue
                extract_to = Path(tempfile.mkdtemp(dir=temp_dir))
                try:
                    safe_extract(item, extract_to)
                except (zipfile.BadZipFile, ValueError, RuntimeError) as exc:
                    log(f"  ! Corrupted or unreadable zip ({exc}), treated as a rejected file")
                    entry = _classify(item, rel, config)
                    entry.allowed = False
                    entry.reason = (entry.reason + " ; " if entry.reason else "") + "corrupted or unreadable archive"
                    yield entry
                    continue
                # The zip content is catalogued under a folder named after the zip.
                yield from _walk(extract_to, rel, temp_dir, config, log)
            else:
                yield _classify(item, rel, config)


def scan(root: Path, temp_dir: Path, config: Config, log: Logger) -> Iterator[FileEntry]:
    """Recursively walk `root` and yield one FileEntry per discovered file."""
    yield from _walk(root, PurePosixPath(), temp_dir, config, log)
