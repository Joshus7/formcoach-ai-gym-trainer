"""Main window: sidebar navigation and the stacked screens; owns the engine thread and voice."""
from __future__ import annotations

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from ..core.config import load_config, merged
from ..core.exercises import EXERCISES, create
from ..core.voice import VoiceCoach
from ..data.db import Database
from ..data.export import history_to_csv, session_to_csv, session_to_pdf
from ..settings import AppSettings, app_data_dir
from .history_view import HistoryView
from .home_view import HomeView
from .live_view import LiveView
from .settings_view import SettingsView
from .summary_view import SummaryView
from .theme import palette, stylesheet
from .worker import EngineWorker, SourceSpec


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings | None = None, db: Database | None = None):
        super().__init__()
        self.settings = settings or AppSettings.load()
        self.db = db or Database(app_data_dir() / "formcoach.db")
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
        self.summary.export_csv_requested.connect(lambda: self.export_session(self._session, "csv"))
        self.summary.export_pdf_requested.connect(lambda: self.export_session(self._session, "pdf"))
        self.home.user_combo.currentIndexChanged.connect(self._user_changed)
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
        self.history = HistoryView(self.db, self.pal, self.home.current_user)
        self.settings_view = SettingsView(self.settings, self.base_config)
        self.stack.addWidget(self.history)
        self.stack.addWidget(self.settings_view)
        self.screens = {"home": self.home, "live": self.live, "summary": self.summary,
                        "history": self.history, "settings": self.settings_view}
        self.history.open_session.connect(self.open_saved_session)
        self.history.export_session_csv.connect(lambda sid: self.export_session(self.db.load_session(sid), "csv"))
        self.history.export_session_pdf.connect(lambda sid: self.export_session(self.db.load_session(sid), "pdf"))
        self.history.export_history.connect(self.export_history)
        self.settings_view.theme_changed.connect(self.apply_theme)
        self.settings_view.saved.connect(self._settings_saved)
        self.settings_view.test_voice.connect(self._test_voice)

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

    # ------------------------------------------------------------------ users
    def refresh_users(self, select: int | None = None) -> None:
        if not self.db.list_users():
            self.db.default_user()
        current = select or self.settings.last_user_id
        self.home.set_users(self.db.list_users(), current)

    def add_user(self, name: str) -> None:
        uid = self.db.add_user(name)
        self.refresh_users(uid)
        self._user_changed()

    def _user_changed(self, *_):
        self.settings.last_user_id = self.home.current_user()
        self.settings.save()

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
        if session.reps:
            self.db.save_session(session)

    def fault_messages(self, exercise: str) -> dict[str, str]:
        ex = create(exercise, self.exercise_config())
        return {k: f.message for k, f in ex.faults.items()}

    def open_saved_session(self, session_id: int) -> None:
        s = self.db.load_session(session_id)
        if s is not None:
            self._session = s
            self.summary.show_session(s, self.fault_messages(s.exercise))
            self.go("summary")

    def _export_dir(self) -> str:
        d = app_data_dir() / "exports"
        d.mkdir(exist_ok=True)
        return str(d)

    def export_session(self, session, kind: str) -> None:
        if session is None or not session.reps:
            QMessageBox.information(self, "Export", "There are no reps to export in this session.")
            return
        default = f"{self._export_dir()}/formcoach_{session.exercise}_{session.started_at:%Y%m%d_%H%M}.{kind}"
        filt = "CSV files (*.csv)" if kind == "csv" else "PDF files (*.pdf)"
        path, _ = QFileDialog.getSaveFileName(self, f"Export session ({kind.upper()})", default, filt)
        if not path:
            return
        try:
            if kind == "csv":
                session_to_csv(session, path, self.fault_messages(session.exercise))
            else:
                session_to_pdf(session, path, self.db.user_name(session.user_id),
                               self.fault_messages(session.exercise))
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        self.status.setText(f"Saved {path}")

    def export_history(self, exercise) -> None:
        default = f"{self._export_dir()}/formcoach_history.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export history (CSV)", default, "CSV files (*.csv)")
        if path:
            try:
                history_to_csv(self.db, self.home.current_user(), path, exercise)
                self.status.setText(f"Saved {path}")
            except OSError as exc:
                QMessageBox.warning(self, "Export failed", str(exc))

    def _settings_saved(self) -> None:
        self.voice.enabled = self.settings.voice_on
        self.voice.set_rate(self.settings.voice_rate)
        self.status.setText("Settings saved")

    def _test_voice(self, rate: int) -> None:
        self.voice.set_rate(rate)
        was = self.voice.enabled
        self.voice.enabled = True
        self.voice.say("Keep your hips in line")
        self.voice.enabled = was

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
        self.db.close()
        super().closeEvent(event)
