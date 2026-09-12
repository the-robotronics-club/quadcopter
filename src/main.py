#!/usr/bin/env python3
"""NIDAR GCS — native desktop Ground Control Station.

Run with:
    python main.py

IMPORTANT — folder layout:
This file must live OUTSIDE the `gcs/` package, as its sibling:

    project_root/
        main.py        <- this file
        gcs/            <- the package
            __init__.py
            main_window.py
            ...

`gcs/main_window.py` is imported below as `gcs.main_window`, which
only resolves if the *parent* of `gcs/` is on sys.path. Python
automatically puts the directory containing the script you run at
sys.path[0], so as long as main.py sits next to (not inside) gcs/,
this works no matter what your current working directory is when
you invoke it. The sys.path.insert below is just extra insurance
for unusual invocations (symlinks, some IDE "run" configs, etc.)
where that automatic behavior can be bypassed.
"""
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))

from PySide6.QtWidgets import QApplication

try:
    from gcs.main_window import MainWindow
except ModuleNotFoundError as exc:
    # This is exactly the failure mode reported earlier: main.py ends up
    # inside gcs/ instead of next to it (or gcs/'s __init__.py is
    # missing), and the person just sees a bare traceback with no clue
    # what to actually do about it. If it's specifically the 'gcs'
    # package that's missing, replace that traceback with a message
    # that says what's wrong and exactly how to fix it — anything else
    # (a genuinely missing third-party dependency, etc.) still raises
    # normally.
    if exc.name == "gcs":
        sys.exit(
            "\nCould not import the 'gcs' package.\n\n"
            "main.py must be run from the folder that directly contains it, "
            "with 'gcs' as a sibling folder (not a parent or child of it):\n\n"
            f"    {_here}/\n"
            f"        main.py   <- you're trying to run this\n"
            f"        gcs/      <- must be right here, with an __init__.py inside\n\n"
            f"Run it as:\n"
            f"    cd \"{_here}\"\n"
            f"    python main.py\n"
        )
    raise


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
