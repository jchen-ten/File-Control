"""Windows long-path handling (the 260-character MAX_PATH limit).

On Windows, many operations fail when the path exceeds 260 characters.
The “\\\\?\\” prefix lifts this limit. These utilities apply that prefix
transparently and safely.
"""

from __future__ import annotations

import os
from pathlib import Path

_IS_WINDOWS = os.name == "nt"
_PREFIX = "\\\\?\\"


def long_path(path: str | Path) -> str:
    """Return a version of the path usable even when it is very long.

    On Windows, returns the absolute path prefixed with “\\\\?\\”.
    On other systems, simply returns the path as a string.
    """
    path = Path(path)
    if not _IS_WINDOWS:
        return str(path)

    absolute = os.path.abspath(str(path))
    if absolute.startswith(_PREFIX):
        return absolute
    if absolute.startswith("\\\\"):
        # UNC path: \\server\share -> \\?\UNC\server\share
        return _PREFIX + "UNC\\" + absolute[2:]
    return _PREFIX + absolute


def remove_tree(path: str | Path) -> None:
    """Recursively delete a folder, even with Windows long paths.

    Unlike `shutil.rmtree`, this function prefixes every path with “\\\\?\\”
    on Windows, which avoids WinError 145 on deep directory trees.
    """
    path = Path(path)
    lp = long_path(path)
    if not os.path.exists(lp):
        return
    for root, dirs, files in os.walk(lp, topdown=False):
        for name in files:
            target = os.path.join(root, name)
            try:
                os.chmod(target, 0o700)
            except OSError:
                pass
            os.remove(target)
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(lp)
