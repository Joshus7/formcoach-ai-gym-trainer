"""FormCoach entry point.

    python -m formcoach.app
    python -m formcoach.app --demo push_up     # start straight into a dataset-video demo
"""
from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .settings import AppSettings
from .ui.main_window import MainWindow
from .ui.theme import stylesheet


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="FormCoach - AI gym trainer")
    ap.add_argument("--demo", metavar="EXERCISE", help="start a 'demo with dataset video' for this exercise")
    ap.add_argument("--video", help="start with this video file (needs --exercise)")
    ap.add_argument("--exercise", default="push_up")
    args, qt_args = ap.parse_known_args(argv)

    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName("FormCoach")
    settings = AppSettings.load()
    app.setStyleSheet(stylesheet(settings.theme))
    win = MainWindow(settings)
    win.show()
    if args.demo or args.video:
        req = {"exercise": args.demo or args.exercise, "source": "dataset" if args.demo else "video",
               "path": args.video or "", "target_reps": None, "target_sets": None,
               "user_id": win.home.current_user()}
        QTimer.singleShot(300, lambda: win.start_workout(req))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
