"""File Control entry point.

Usage:
    python main.py            -> launch the graphical interface
    python main.py <input>    -> command-line mode
"""

from __future__ import annotations

import sys

from filecontrol.config import load_config, resolve_config_path
from filecontrol.processor import ProcessSession, default_output_dir

# When the app is bundled as a windowed executable (PyInstaller --windowed),
# there is no console attached: `print()` is invisible and `input()` cannot
# read anything, so command-line mode would just hang forever (e.g. if a
# user drags a folder onto the .exe icon). In that case always open the
# graphical interface instead, pre-filling the dropped path if any.
IS_FROZEN_GUI = bool(getattr(sys, "frozen", False))

CONFIG_PATH = resolve_config_path()


def _run_cli(input_path: str) -> int:
    config = load_config(CONFIG_PATH)
    output_path = default_output_dir(input_path)
    session = ProcessSession(input_path, output_path, config, log=print)
    try:
        # Step 1: analyze and list the unsupported files.
        try:
            session.analyze()
        except (ValueError, OSError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print()
        print(session.rejected_listing())
        print()
        print(session.summary.as_text())

        if not session.accepted:
            print("\nNo allowed files to compress.")
            return 0

        # Step 2: ask for confirmation before creating the archives.
        prompt = (
            f"\nCreate the zip(s) for {len(session.accepted)} allowed "
            f"file(s)? [y/N] "
        )
        answer = input(prompt).strip().lower()
        if answer in ("o", "oui", "y", "yes"):
            print()
            session.create_archives()
            print()
            print(session.summary.as_text())
        else:
            print("Archive creation cancelled.")
    finally:
        session.close()
    return 0


def main() -> int:
    args = sys.argv[1:]
    if len(args) >= 1 and not IS_FROZEN_GUI:
        return _run_cli(args[0])

    from filecontrol.gui import launch

    launch(initial_path=args[0] if args else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
