"""Live workout screen: video with skeleton, rep counter, score and feedback."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .theme import Palette
from .widgets import Card, VideoView


class LiveView(QWidget):
    pause_toggled = Signal(bool)
    stop_requested = Signal()
    next_set_requested = Signal()
    voice_toggled = Signal(bool)

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self.p = palette
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        self.video = VideoView()
        self.video.set_message("Starting camera...")
        root.addWidget(self.video, 3)

        panel = QVBoxLayout()
        panel.setSpacing(12)
        self.title = QLabel("Push-up")
        self.title.setObjectName("Title")
        self.source = QLabel()
        self.source.setObjectName("Muted")
        self.source.setWordWrap(True)
        panel.addWidget(self.title)
        panel.addWidget(self.source)

        reps_card = Card()
        rl = QVBoxLayout(reps_card)
        rl.setContentsMargins(18, 10, 18, 14)
        lbl = QLabel("REPS")
        lbl.setObjectName("StatLabel")
        self.reps = QLabel("0")
        self.reps.setObjectName("BigNumber")
        self.reps.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_label = QLabel("Set 1")
        self.set_label.setObjectName("Muted")
        self.set_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_reps = QLabel("No reps: 0")
        self.no_reps.setObjectName("Muted")
        self.no_reps.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rl.addWidget(lbl)
        rl.addWidget(self.reps)
        rl.addWidget(self.set_label)
        rl.addWidget(self.no_reps)
        panel.addWidget(reps_card)

        score_card = Card()
        sl = QVBoxLayout(score_card)
        sl.setContentsMargins(18, 10, 18, 14)
        lbl = QLabel("LAST REP")
        lbl.setObjectName("StatLabel")
        self.score = QLabel("-")
        self.score.setObjectName("StatValue")
        self.score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.score_detail = QLabel("")
        self.score_detail.setObjectName("Muted")
        self.score_detail.setWordWrap(True)
        self.score_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(lbl)
        sl.addWidget(self.score)
        sl.addWidget(self.score_detail)
        panel.addWidget(score_card)

        self.feedback = QLabel("Get into position")
        self.feedback.setObjectName("Feedback")
        self.feedback.setWordWrap(True)
        self.feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback.setMinimumHeight(70)
        panel.addWidget(self.feedback)

        panel.addStretch()
        self.fps = QLabel("FPS -")
        self.fps.setObjectName("Muted")
        panel.addWidget(self.fps)
        self.voice = QCheckBox("Voice coach")
        self.voice.setChecked(True)
        self.voice.toggled.connect(self.voice_toggled)
        panel.addWidget(self.voice)

        buttons = QHBoxLayout()
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.toggled.connect(self._pause)
        self.next_btn = QPushButton("Next set")
        self.next_btn.clicked.connect(self.next_set_requested)
        self.stop_btn = QPushButton("Finish")
        self.stop_btn.setObjectName("Danger")
        self.stop_btn.clicked.connect(self.stop_requested)
        buttons.addWidget(self.pause_btn)
        buttons.addWidget(self.next_btn)
        buttons.addWidget(self.stop_btn)
        panel.addLayout(buttons)

        side = QWidget()
        side.setLayout(panel)
        side.setFixedWidth(320)
        root.addWidget(side)

        self._score_timer = QTimer(self)
        self._score_timer.setSingleShot(True)
        self._score_timer.timeout.connect(lambda: self.score.setStyleSheet(""))

    def reset(self, exercise_name: str, voice_on: bool) -> None:
        self.title.setText(exercise_name)
        self.reps.setText("0")
        self.no_reps.setText("No reps: 0")
        self.set_label.setText("Set 1")
        self.score.setText("-")
        self.score.setStyleSheet("")
        self.score_detail.setText("")
        self.feedback.setText("Get into position")
        self.pause_btn.setChecked(False)
        self.voice.setChecked(voice_on)
        self.video.set_message("Starting...")
        self.source.setText("")

    def set_source(self, text: str) -> None:
        self.source.setText(f"Input: {text}")

    def update_stats(self, s: dict) -> None:
        self.reps.setText(str(s["reps"]))
        self.no_reps.setText(f"No reps: {s['no_reps']}")
        self.set_label.setText(f"Set {s['set']}  -  {s['reps_in_set']} reps this set")
        self.fps.setText(f"FPS {s['fps']:.0f}  -  {s['state'].replace('_', ' ')}")
        text = s["message"]
        if s["state"] == "countdown":
            text = f"Get into position... {int(s['countdown']) + 1}"
        if text:
            color = {"good": self.p.good, "warn": self.p.warn, "bad": self.p.warn}.get(s["level"], self.p.text)
            self.feedback.setStyleSheet(f"color: {color};")
            self.feedback.setText(text)

    def show_rep(self, rep: dict) -> None:
        if rep["valid"]:
            color = self.p.good if rep["score"] >= 80 else self.p.warn
            self.score.setText(f"{rep['score']}")
        else:
            color = self.p.warn  # "no rep" is shown in orange
            self.score.setText(f"NO REP ({rep['score']})")
        self.score.setStyleSheet(f"color: {color};")
        self.score_detail.setText(", ".join(rep["faults"]) if rep["faults"] else "Clean rep")
        self._score_timer.start(2500)

    def _pause(self, paused: bool) -> None:
        self.pause_btn.setText("Resume" if paused else "Pause")
        if paused:
            self.feedback.setText("Paused")
        self.pause_toggled.emit(paused)
