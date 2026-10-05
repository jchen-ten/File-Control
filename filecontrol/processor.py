"""Orchestration: scan, sorting of rejected files, and compression."""

from __future__ import annotations

import csv
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable

from .config import Config
from .converter import conversion_available, convert_file
from .longpath import long_path, remove_tree
from .packer import pack
from .scanner import FileEntry, safe_extract, scan

Logger = Callable[[str], None]


def default_output_dir(input_path: str | Path) -> Path:
    """Default output folder: same location as the input, suffixed with `_NEW`.

    - Folder `C:/data/project`     -> `C:/data/project_NEW`
    - Zip    `C:/data/project.zip` -> `C:/data/project_NEW`
    """
    input_path = Path(input_path)
    base_name = input_path.stem if input_path.suffix.lower() == ".zip" else input_path.name
    return input_path.parent / f"{base_name}_NEW"


@dataclass
class Summary:
    """Result of a complete processing run."""

    total_files: int = 0
    accepted_files: int = 0
    rejected_files: int = 0
    converted_files: int = 0
    accepted_size: int = 0
    rejected_size: int = 0
    archives: list[Path] = field(default_factory=list)
    rejected_dir: Path | None = None
    report_path: Path | None = None

    def as_text(self) -> str:
        mb = 1024 * 1024
        lines = [
            "----- Summary -----",
            f"Files scanned      : {self.total_files}",
            f"Allowed files      : {self.accepted_files} ({self.accepted_size / mb:.1f} MB)",
            f"Converted files    : {self.converted_files}",
            f"Rejected files     : {self.rejected_files} ({self.rejected_size / mb:.1f} MB)",
            f"Archives created   : {len(self.archives)}",
        ]
        for archive in self.archives:
            size = archive.stat().st_size / mb if archive.exists() else 0
            lines.append(f"  - {archive.name} ({size:.1f} MB)")
        if self.rejected_dir and self.rejected_files:
            lines.append(f"Rejected folder    : {self.rejected_dir}")
        if self.report_path and self.rejected_files:
            lines.append(f"Rejects report     : {self.report_path}")
        return "\n".join(lines)


def process(
    input_path: str | Path,
    output_dir: str | Path,
    config: Config,
    log: Logger | None = None,
) -> Summary:
    """Process a folder or a zip in a single pass (analyze + compress).

    Kept for compatibility. For a two-step flow (analyze then confirmation),
    use `ProcessSession`.
    """
    with ProcessSession(input_path, output_dir, config, log) as session:
        session.analyze()
        session.create_archives()
        return session.summary


class ProcessSession:
    """Two-step processing: `analyze()` then `create_archives()`.

    The temporary folder (zip extraction, conversions) stays alive between the
    two steps and is only cleaned up when `close()` is called.
    The original input is never modified.
    """

    def __init__(
        self,
        input_path: str | Path,
        output_dir: str | Path,
        config: Config,
        log: Logger | None = None,
    ) -> None:
        self.input_path = Path(input_path)
        self.output_dir = Path(output_dir)
        self.config = config
        self.log = log or (lambda _msg: None)

        self.rejected_dir = self.output_dir / "rejected"
        self.archives_dir = self.output_dir / "archives"
        self.summary = Summary(rejected_dir=self.rejected_dir)
        self.accepted: list[FileEntry] = []
        self.rejected: list[FileEntry] = []

        self._tmp: Path | None = None
        self._analyzed = False

    # ------------------------------------------------------------ Step 1
    def analyze(self) -> Summary:
        """Step 1: scan, convert if possible, and list the rejected files.

        Copies unsupported files into `rejected/` and writes the CSV report.
        Does not create any archive.
        """
        if self._analyzed:
            return self.summary
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input not found: {self.input_path}")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._tmp = Path(tempfile.mkdtemp(prefix="filecontrol_"))

        if self.input_path.is_file() and self.input_path.suffix.lower() == ".zip":
            self.log(f"Extracting input archive: {self.input_path.name}")
            root = self._tmp / "input"
            try:
                safe_extract(self.input_path, root)
            except (zipfile.BadZipFile, ValueError, RuntimeError) as exc:
                raise ValueError(f"Cannot extract input archive: {exc}") from exc
        elif self.input_path.is_dir():
            root = self.input_path
        else:
            raise ValueError("The input must be a folder or a .zip file")

        self.log("Analyzing files...")
        entries = list(scan(root, self._tmp, self.config, self.log))
        self.summary.total_files = len(entries)

        convert_dir = self._tmp / "conversions"
        can_convert = self.config.convert_unsupported and conversion_available()
        if self.config.convert_unsupported and not conversion_available() and any(e.convert_to for e in entries):
            self.log("Warning: no conversion engine (LibreOffice) detected, conversions skipped.")

        for entry in entries:
            if not entry.allowed and entry.convert_to and can_convert:
                converted = _try_convert(entry, convert_dir, self.config, self.log)
                if converted is not None:
                    entry = converted

            if entry.allowed:
                self.accepted.append(entry)
                self.summary.accepted_files += 1
                self.summary.accepted_size += entry.size
                if entry.reason.startswith("converted"):
                    self.summary.converted_files += 1
            else:
                self.rejected.append(entry)
                self.summary.rejected_files += 1
                self.summary.rejected_size += entry.size
                _copy_rejected(entry, self.rejected_dir, self.log)

        if self.rejected:
            self.summary.report_path = _write_report(self.rejected, self.output_dir, self.log)

        self._analyzed = True
        self.log("Analysis complete.")
        return self.summary

    def rejected_listing(self) -> str:
        """Readable list of unsupported files (format or size)."""
        if not self.rejected:
            return "No unsupported files."
        mb = 1024 * 1024
        lines = [f"Unsupported files ({len(self.rejected)}):"]
        for entry in self.rejected:
            lines.append(f"  - {entry.rel_path} ({entry.size / mb:.1f} MB): {entry.reason}")
        return "\n".join(lines)

    # ------------------------------------------------------------ Step 2
    def create_archives(self) -> Summary:
        """Step 2: compress the allowed files into one or more archives."""
        if not self._analyzed:
            raise RuntimeError("Call analyze() before create_archives().")
        self.summary.archives = pack(self.accepted, self.archives_dir, self.config, self.log)
        self.log("Compression complete.")
        return self.summary

    # ------------------------------------------------------------ Cleanup
    def close(self) -> None:
        """Remove the temporary folder."""
        if self._tmp is not None:
            try:
                remove_tree(self._tmp)
            except OSError as exc:
                self.log(f"Warning: incomplete cleanup of the temporary folder ({exc})")
            self._tmp = None

    def __enter__(self) -> "ProcessSession":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _try_convert(
    entry: FileEntry,
    convert_dir: Path,
    config: Config,
    log: Logger,
) -> FileEntry | None:
    """Try to convert a rejected file into an allowed format.

    Returns a new accepted FileEntry on success, otherwise None.
    """
    source_ext = PurePosixPath(entry.rel_path).suffix.lstrip(".").lower()
    log(f"Converting: {entry.rel_path} (.{source_ext} -> .{entry.convert_to})")
    work_dir = Path(tempfile.mkdtemp(dir=convert_dir)) if convert_dir.exists() else None
    if work_dir is None:
        convert_dir.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(dir=convert_dir))

    converted_path = convert_file(entry.source_path, entry.convert_to, work_dir, log)
    if converted_path is None:
        return None

    new_rel = entry.rel_path.with_suffix(f".{entry.convert_to}")
    new_size = converted_path.stat().st_size
    if new_size > config.max_file_size:
        log(f"  ! Converted file too large ({new_size / (1024 * 1024):.1f} MB), rejected")
        return None

    log(f"  → Converted to {new_rel.name}")
    return FileEntry(
        source_path=converted_path,
        rel_path=new_rel,
        size=new_size,
        allowed=True,
        reason=f"converted from .{source_ext}",
    )


def _copy_rejected(entry: FileEntry, rejected_dir: Path, log: Logger) -> None:
    destination = rejected_dir / Path(*entry.rel_path.parts)
    Path(long_path(destination.parent)).mkdir(parents=True, exist_ok=True)
    with open(long_path(entry.source_path), "rb") as source, open(long_path(destination), "wb") as target:
        shutil.copyfileobj(source, target)
    log(f"Rejected: {entry.rel_path} ({entry.reason})")


def _write_report(rejected: list[FileEntry], output_dir: Path, log: Logger) -> Path:
    """Write a CSV report listing all rejected files."""
    report_path = output_dir / "rejects_report.csv"
    with report_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["File name", "Format", "Size (MB)", "Size (bytes)", "Original path", "Rejection reason"])
        for entry in rejected:
            name = PurePosixPath(entry.rel_path).name
            ext = PurePosixPath(entry.rel_path).suffix.lstrip(".").lower() or "(no extension)"
            parent = str(PurePosixPath(entry.rel_path).parent)
            origin = "" if parent == "." else parent
            writer.writerow([
                name,
                ext,
                f"{entry.size / (1024 * 1024):.3f}",
                entry.size,
                origin,
                entry.reason,
            ])
    log(f"Rejects report written: {report_path.name}")
    return report_path
