"""Main window: sidebar navigation and the stacked screens; owns the engine thread and voice."""
from __future__ import annotations

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (QApplication, QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from ..core.config import load_config, merged
from ..core.exercises import EXERCISES, create
from ..core.voice import VoiceCoach
from ..settings import AppSettings
from .home_view import HomeView
from .live_view import LiveView
from .summary_view import SummaryView
from .theme import palette, stylesheet
from .worker import EngineWorker, SourceSpec


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings | None = None):
        super().__init__()
        self.settings = settings or AppSettings.load()
        self.base_config = load_config()
        self.pal = palette(self.settings.theme)
        self.voice = VoiceCoach(enabled=self.settings.voice_on, rate=self.settings.voice_rate)
        self._thread: QThread | None = None
        self._worker: EngineWorker | None = None
        self._session = None

        self.setWindowTitle("FormCoach - AI Gym Trainer")
        self.resize(1360, 860)
        self.setMinimumSize(1100, 720)
        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_sidebar())
        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.home = HomeView(self.pal.accent)
        self.live = LiveView(self.pal)
        self.summary = SummaryView(self.pal)
        for w in (self.home, self.live, self.summary):
            self.stack.addWidget(w)
        self._extra_screens()

        self.home.start_requested.connect(self.start_workout)
        self.home.add_user_requested.connect(self.add_user)
        self.live.stop_requested.connect(self.stop_workout)
        self.live.voice_toggled.connect(self._set_voice)
        self.summary.home_requested.connect(lambda: self.go("home"))
        self.summary.history_requested.connect(lambda: self.go("history"))
        self.refresh_users()
        self.go("home")

    # ------------------------------------------------------------------ layout
    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(200)
        v = QVBoxLayout(side)
        v.setContentsMargins(14, 22, 14, 18)
        v.setSpacing(6)
        brand = QLabel("FormCoach")
        brand.setObjectName("Brand")
        tag = QLabel("AI gym trainer")
        tag.setObjectName("Muted")
        v.addWidget(brand)
        v.addWidget(tag)
        v.addSpacing(18)
        self.nav = QButtonGroup(self)
        self.nav_buttons = {}
        for key, text in (("home", "Workout"), ("history", "History"), ("settings", "Settings")):
            b = QPushButton(text)
            b.setObjectName("Nav")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.nav.addButton(b)
            self.nav_buttons[key] = b
            v.addWidget(b)
        v.addStretch()
        self.status = QLabel("")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        return side

    def _extra_screens(self) -> None:
        """History and Settings screens (added in a later phase)."""
        self.screens = {"home": self.home, "live": self.live, "summary": self.summary}

    def go(self, name: str) -> None:
        if self._worker is not None and name != "live":
            return  # don't leave the live screen while a workout is running
        widget = self.screens.get(name)
        if widget is None:
            return
        self.stack.setCurrentWidget(widget)
        for key, b in self.nav_buttons.items():
            b.setChecked(key == name or (key == "home" and name in ("live", "summary")))
        if hasattr(widget, "refresh"):
            widget.refresh()

    # ------------------------------------------------------------------ users (stored in the DB later)
    def refresh_users(self) -> None:
        self.home.set_users([(None, "Guest")])

    def add_user(self, name: str) -> None:
        self.status.setText("Profiles are saved once storage is enabled.")

    # ------------------------------------------------------------------ workout
    def exercise_config(self) -> dict:
        return merged(self.base_config, self.settings.overrides)

    def start_workout(self, req: dict) -> None:
        if self._worker is not None:
            return
        kind = req["source"]
        if kind == "video" and not req["path"]:
            QMessageBox.information(self, "Choose a video", "Pick a video file first (Browse...).")
            return
        spec = SourceSpec(kind=kind, camera=self.settings.camera_index, path=req["path"],
                          width=self.settings.width, height=self.settings.height)
        ex = req["exercise"]
        self.live.reset(EXERCISES[ex].name, self.voice.enabled)
        self.go("live")

        self._thread = QThread(self)
        self._worker = EngineWorker(ex, self.exercise_config(), spec, req["target_reps"], req["target_sets"],
                                    req.get("user_id"))
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        w = self._worker
        w.frame_ready.connect(self.live.video.set_image)
        w.stats.connect(self.live.update_stats)
        w.rep_done.connect(self.live.show_rep)
        w.speak.connect(self.voice.say)
        w.error.connect(self._on_error)
        w.source_opened.connect(self.live.set_source)
        w.finished.connect(self._on_finished)
        self.live.pause_toggled.connect(w.set_paused, Qt.ConnectionType.DirectConnection)
        self.live.next_set_requested.connect(w.next_set, Qt.ConnectionType.DirectConnection)
        self._thread.start()
        self.status.setText("Workout running")

    def stop_workout(self) -> None:
        if self._worker is not None:
            self._worker.stop()

    def _on_error(self, message: str) -> None:
        self.live.video.set_message(message)
        QMessageBox.warning(self, "FormCoach", message)

    def _on_finished(self, session) -> None:
        try:
            self.live.pause_toggled.disconnect()
            self.live.next_set_requested.disconnect()
        except (RuntimeError, TypeError):
            pass
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
        self._thread = None
        self._worker = None
        self.status.setText("")
        self._session = session
        if session is None:
            self.go("home")
            return
        self.on_session_saved(session)
        ex = create(session.exercise, self.exercise_config())
        self.summary.show_session(session, {k: f.message for k, f in ex.faults.items()})
        self.go("summary")

    def on_session_saved(self, session) -> None:
        """Hook for storage (implemented when the database is added)."""

    def _set_voice(self, on: bool) -> None:
        self.voice.enabled = on
        self.settings.voice_on = on
        self.settings.save()

    def apply_theme(self, name: str) -> None:
        self.settings.theme = name
        QApplication.instance().setStyleSheet(stylesheet(name))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None:
            self._worker.stop()
            if self._thread is not None:
                self._thread.quit()
                self._thread.wait(3000)
        self.voice.close()
        self.settings.save()
        super().closeEvent(event)
