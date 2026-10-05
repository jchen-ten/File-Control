"""Loading and saving of the File Control configuration."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

MB = 1024 * 1024


def resolve_config_path() -> Path:
    """Location of config.json, in both script mode and executable mode.

    - PyInstaller executable (frozen): config.json next to the .exe (editable by
      the user), falling back to the bundled copy.
    - Script mode: config.json at the project root.
    """
    if getattr(sys, "frozen", False):  # PyInstaller executable
        exe_config = Path(sys.executable).resolve().parent / "config.json"
        if exe_config.is_file():
            return exe_config
        bundled = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "config.json"
        return exe_config if not bundled.is_file() else bundled
    return Path(__file__).resolve().parent.parent / "config.json"

DEFAULT_CONFIG = {
    "allowed_extensions": [
        "zip", "pdf", "txt", "md", "docx", "doc", "pptx", "ppt",
        "csv", "png", "jpg", "jpeg", "xlsx", "xls",
    ],
    "max_file_size_mb": 50,
    "max_zip_size_mb": 3000,
    "recurse_zips": True,
    "convert_unsupported": True,
    "archive_prefix": "archive",
}


@dataclass
class Config:
    """File processing settings."""

    allowed_extensions: list[str] = field(
        default_factory=lambda: list(DEFAULT_CONFIG["allowed_extensions"])
    )
    max_file_size_mb: float = DEFAULT_CONFIG["max_file_size_mb"]
    max_zip_size_mb: float = DEFAULT_CONFIG["max_zip_size_mb"]
    recurse_zips: bool = DEFAULT_CONFIG["recurse_zips"]
    convert_unsupported: bool = DEFAULT_CONFIG["convert_unsupported"]
    archive_prefix: str = DEFAULT_CONFIG["archive_prefix"]

    @property
    def max_file_size(self) -> int:
        """Maximum size of an allowed file, in bytes."""
        return int(self.max_file_size_mb * MB)

    @property
    def max_zip_size(self) -> int:
        """Maximum size of an archive before splitting, in bytes."""
        return int(self.max_zip_size_mb * MB)

    @property
    def normalized_extensions(self) -> set[str]:
        """Allowed extensions, lowercase and without leading dot."""
        return {ext.lower().lstrip(".").strip() for ext in self.allowed_extensions if ext.strip()}

    def to_dict(self) -> dict:
        return {
            "allowed_extensions": list(self.allowed_extensions),
            "max_file_size_mb": self.max_file_size_mb,
            "max_zip_size_mb": self.max_zip_size_mb,
            "recurse_zips": self.recurse_zips,
            "convert_unsupported": self.convert_unsupported,
            "archive_prefix": self.archive_prefix,
        }


def load_config(path: str | Path) -> Config:
    """Load the configuration from a JSON file, falling back to defaults."""
    path = Path(path)
    data = dict(DEFAULT_CONFIG)
    if path.is_file():
        try:
            with path.open("r", encoding="utf-8") as handle:
                data.update(json.load(handle))
        except (json.JSONDecodeError, OSError):
            pass
    return Config(
        allowed_extensions=list(data.get("allowed_extensions", DEFAULT_CONFIG["allowed_extensions"])),
        max_file_size_mb=float(data.get("max_file_size_mb", DEFAULT_CONFIG["max_file_size_mb"])),
        max_zip_size_mb=float(data.get("max_zip_size_mb", DEFAULT_CONFIG["max_zip_size_mb"])),
        recurse_zips=bool(data.get("recurse_zips", DEFAULT_CONFIG["recurse_zips"])),
        convert_unsupported=bool(data.get("convert_unsupported", DEFAULT_CONFIG["convert_unsupported"])),
        archive_prefix=str(data.get("archive_prefix", DEFAULT_CONFIG["archive_prefix"])),
    )


def save_config(config: Config, path: str | Path) -> None:
    """Save the configuration to a JSON file."""
    path = Path(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, indent=2, ensure_ascii=False)
