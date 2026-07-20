#!/usr/bin/env python3
"""FountainPad — focused Fountain screenplay editor."""

from __future__ import annotations

import sys


def main() -> int:
    # QWebEngine must be imported before QApplication on some platforms
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QCoreApplication
    except ImportError:
        print(
            "PySide6 is required.\n"
            "  python3 -m venv .venv && source .venv/bin/activate\n"
            "  pip install -r requirements.txt\n"
            "  python main.py",
            file=sys.stderr,
        )
        return 1

    # Enable WebEngine software rendering fallbacks where helpful
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    app.setApplicationName("FountainPad")
    app.setOrganizationName("FountainPad")
    app.setApplicationVersion("1.0.0")

    from mainwindow import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
