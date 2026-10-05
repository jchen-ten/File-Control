"""Conversion of unsupported formats into allowed formats.

Conversion relies on LibreOffice / OpenOffice in "headless" mode
(the ``soffice`` executable). If the tool is not installed, conversion is
simply skipped and the file stays rejected.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Callable

from .longpath import long_path

Logger = Callable[[str], None]

# Source extension (lowercase, no dot) -> allowed target extension.
# Covers in particular OpenOffice/LibreOffice formats to their Office equivalents.
CONVERSIONS: dict[str, str] = {
    # Word processing -> docx
    "odt": "docx",
    "ott": "docx",
    "fodt": "docx",
    "sxw": "docx",
    "rtf": "docx",
    "wpd": "docx",
    # Spreadsheet -> xlsx
    "ods": "xlsx",
    "ots": "xlsx",
    "fods": "xlsx",
    "sxc": "xlsx",
    # Presentation -> pptx
    "odp": "pptx",
    "otp": "pptx",
    "fodp": "pptx",
    "sxi": "pptx",
    # Drawing -> pdf
    "odg": "pdf",
    "fodg": "pdf",
    # Miscellaneous documents -> pdf
    "odf": "pdf",
}

# Common Windows locations for LibreOffice/OpenOffice.
_WINDOWS_CANDIDATES = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    r"C:\Program Files\OpenOffice\program\soffice.exe",
    r"C:\Program Files (x86)\OpenOffice\program\soffice.exe",
    r"C:\Program Files\OpenOffice 4\program\soffice.exe",
    r"C:\Program Files (x86)\OpenOffice 4\program\soffice.exe",
]


@lru_cache(maxsize=1)
def find_soffice() -> str | None:
    """Locate the ``soffice`` executable (LibreOffice/OpenOffice), or None."""
    for name in ("soffice", "soffice.exe"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in _WINDOWS_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    return None


def conversion_available() -> bool:
    """Report whether a conversion engine is available on the machine."""
    return find_soffice() is not None


def target_for(ext: str, allowed_extensions: set[str]) -> str:
    """Return the allowed target extension for `ext`, or "" if conversion is impossible.

    Conversion is only offered if the target format is among the allowed formats.
    """
    target = CONVERSIONS.get(ext.lower().lstrip("."))
    if target and target in allowed_extensions:
        return target
    return ""


def convert_file(
    source_path: Path,
    target_ext: str,
    work_dir: Path,
    log: Logger | None = None,
    timeout: int = 120,
) -> Path | None:
    """Convert `source_path` into `target_ext` inside `work_dir`.

    Returns the path of the converted file on success, otherwise None.
    The original input is never modified.
    """
    log = log or (lambda _msg: None)
    soffice = find_soffice()
    if not soffice:
        return None

    source_path = Path(source_path)
    work_dir = Path(work_dir)
    Path(long_path(work_dir)).mkdir(parents=True, exist_ok=True)

    # Copy the source to a short, simple path to avoid issues with long
    # paths / special characters passed on the command line.
    local_in = work_dir / f"source{source_path.suffix.lower()}"
    with open(long_path(source_path), "rb") as src, open(long_path(local_in), "wb") as dst:
        shutil.copyfileobj(src, dst)

    try:
        completed = subprocess.run(
            [
                soffice,
                "--headless",
                "--norestore",
                "--convert-to",
                target_ext,
                "--outdir",
                str(work_dir),
                str(local_in),
            ],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log(f"  ! Conversion failed ({exc})")
        return None

    expected = work_dir / f"source.{target_ext}"
    if completed.returncode == 0 and expected.exists():
        return expected

    detail = completed.stderr.decode("utf-8", "replace").strip() if completed.stderr else ""
    if detail:
        log(f"  ! Conversion failed ({detail})")
    return None
