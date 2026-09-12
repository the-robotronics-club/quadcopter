#!/usr/bin/env python3
"""NIDAR GCS — native desktop Ground Control Station.

Run with:
    python main.py
"""
import sys

from PySide6.QtWidgets import QApplication

from gcs.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
