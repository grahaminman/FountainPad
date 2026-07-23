#!/usr/bin/env python3
"""
main.py — FountainPad entry point.

Developer notes
---------------
Boot order matters for Qt WebEngine:

  1. Import QtCore / set AA_ShareOpenGLContexts *before* QApplication
  2. Create QApplication
  3. Then import MainWindow (which pulls in QWebEngineView)

On some platforms WebEngine must not be imported before the OpenGL-share
attribute is set. Keep heavy UI imports inside main() after that attribute.

Run:
  python main.py
  # or: python -m-style from this directory with venv active

Version is set on QApplication; bump when cutting releases.
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtCore import QCoreApplication, Qt
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "PySide6 is required.\n"
            "  python3 -m venv .venv && source .venv/bin/activate\n"
            "  pip install -r requirements.txt\n"
            "  python main.py",
            file=sys.stderr,
        )
        return 1

    # Helpful for WebEngine on mixed GPU / remote / offscreen setups.
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    app.setApplicationName("FountainPad")
    app.setOrganizationName("FountainPad")
    app.setApplicationVersion("1.1.0")

    # Import after QApplication + OpenGL attribute (WebEngine safety).
    from mainwindow import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
