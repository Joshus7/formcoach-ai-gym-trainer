"""Home screen: who is training, which exercise, which input, optional targets."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QRadioButton, QSpinBox, QToolButton, QVBoxLayout,
                               QWidget)

from ..core.exercises import EXERCISES
from ..core.video_source import dataset_clips
from .widgets import Card, exercise_icon, h_spacer


class HomeView(QWidget):
    start_requested = Signal(dict)
    add_user_requested = Signal(str)

    def __init__(self, accent: str = "#4f8cff", parent=None):
        super().__init__(parent)
        self._accent = accent
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        # Header with user profile
        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("Ready to train?")
        title.setObjectName("Title")
        sub = QLabel("Pick an exercise, place your camera as shown and press Start.")
        sub.setObjectName("Subtitle")
        titles.addWidget(title)
        titles.addWidget(sub)
        header.addLayout(titles)
        header.addWidget(h_spacer())
        header.addWidget(QLabel("Profile"))
        self.user_combo = QComboBox()
        self.user_combo.setMinimumWidth(180)
        header.addWidget(self.user_combo)
        self.new_user = QLineEdit()
        self.new_user.setPlaceholderText("New profile name")
        self.new_user.setMaximumWidth(170)
        self.new_user.returnPressed.connect(self._add_user)
        add = QPushButton("Add")
        add.clicked.connect(self._add_user)
        header.addWidget(self.new_user)
        header.addWidget(add)
        root.addLayout(header)

        # Exercise tiles
        section = QLabel("Exercise")
        section.setObjectName("Section")
        root.addWidget(section)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.ex_group = QButtonGroup(self)
        self.ex_group.setExclusive(True)
        self._tiles: dict[str, QToolButton] = {}
        for i, (key, cls) in enumerate(EXERCISES.items()):
            b = QToolButton()
            b.setObjectName("ExerciseTile")
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            b.setIcon(QIcon(exercise_icon(key, accent, 96)))
            b.setIconSize(QSize(64, 64))
            b.setText(f"{cls.name}\n{cls.view} view")
            b.setMinimumSize(150, 130)
            b.setProperty("key", key)
            self.ex_group.addButton(b)
            self._tiles[key] = b
            grid.addWidget(b, 0, i)
        root.addLayout(grid)
        self.tip = QLabel()
        self.tip.setObjectName("Muted")
        self.tip.setWordWrap(True)
        root.addWidget(self.tip)
        self.ex_group.buttonClicked.connect(self._on_exercise)

        # Source + targets
        row = QHBoxLayout()
        row.setSpacing(16)
        src_card = Card()
        sl = QVBoxLayout(src_card)
        sl.setContentsMargins(18, 14, 18, 14)
        lbl = QLabel("Input")
        lbl.setObjectName("Section")
        sl.addWidget(lbl)
        self.rb_webcam = QRadioButton("Webcam")
        self.rb_video = QRadioButton("Video file")
        self.rb_dataset = QRadioButton("Demo with dataset video")
        self.rb_webcam.setChecked(True)
        self.src_group = QButtonGroup(self)
        for rb in (self.rb_webcam, self.rb_video, self.rb_dataset):
            self.src_group.addButton(rb)
            sl.addWidget(rb)
        file_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Choose a video file...")
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse)
        file_row.addWidget(self.file_edit)
        file_row.addWidget(browse)
        sl.addLayout(file_row)
        self.dataset_info = QLabel()
        self.dataset_info.setObjectName("Muted")
        sl.addWidget(self.dataset_info)
        row.addWidget(src_card, 2)

        tgt_card = Card()
        tl = QVBoxLayout(tgt_card)
        tl.setContentsMargins(18, 14, 18, 14)
        lbl = QLabel("Targets (optional)")
        lbl.setObjectName("Section")
        tl.addWidget(lbl)
        g = QGridLayout()
        g.addWidget(QLabel("Reps per set"), 0, 0)
        self.reps_spin = QSpinBox()
        self.reps_spin.setRange(0, 200)
        self.reps_spin.setSpecialValueText("No target")
        g.addWidget(self.reps_spin, 0, 1)
        g.addWidget(QLabel("Sets"), 1, 0)
        self.sets_spin = QSpinBox()
        self.sets_spin.setRange(0, 20)
        self.sets_spin.setSpecialValueText("No target")
        g.addWidget(self.sets_spin, 1, 1)
        tl.addLayout(g)
        tl.addStretch()
        row.addWidget(tgt_card, 1)
        root.addLayout(row)

        root.addStretch()
        bottom = QHBoxLayout()
        bottom.addWidget(h_spacer())
        self.start_btn = QPushButton("Start workout")
        self.start_btn.setObjectName("Primary")
        self.start_btn.clicked.connect(self._start)
        bottom.addWidget(self.start_btn)
        root.addLayout(bottom)

        self._tiles["push_up"].setChecked(True)
        self._on_exercise(self._tiles["push_up"])

    # ------------------------------------------------------------------ users
    def set_users(self, users: list[tuple[int, str]], current: int | None = None) -> None:
        self.user_combo.blockSignals(True)
        self.user_combo.clear()
        for uid, name in users:
            self.user_combo.addItem(name, uid)
        if current is not None:
            idx = self.user_combo.findData(current)
            if idx >= 0:
                self.user_combo.setCurrentIndex(idx)
        self.user_combo.blockSignals(False)

    def current_user(self) -> int | None:
        return self.user_combo.currentData()

    def _add_user(self) -> None:
        name = self.new_user.text().strip()
        if name:
            self.add_user_requested.emit(name)
            self.new_user.clear()

    # ------------------------------------------------------------------ exercise / source
    def selected_exercise(self) -> str:
        b = self.ex_group.checkedButton()
        return b.property("key") if b else "push_up"

    def _on_exercise(self, button) -> None:
        key = button.property("key")
        cls = EXERCISES[key]
        self.tip.setText(f"Camera: {cls.tip}")
        n = len(dataset_clips(key))
        self.dataset_info.setText(f"{n} dataset clips available for {cls.name.lower()}" if n else
                                  "No dataset clips yet - run scripts/download_data.py")
        self.rb_dataset.setEnabled(n > 0)
        if not n and self.rb_dataset.isChecked():
            self.rb_webcam.setChecked(True)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a workout video", "",
                                              "Videos (*.mp4 *.mov *.avi *.mkv *.webm)")
        if path:
            self.file_edit.setText(path)
            self.rb_video.setChecked(True)

    def _start(self) -> None:
        kind = "webcam" if self.rb_webcam.isChecked() else "video" if self.rb_video.isChecked() else "dataset"
        self.start_requested.emit({
            "exercise": self.selected_exercise(), "source": kind, "path": self.file_edit.text().strip(),
            "target_reps": self.reps_spin.value() or None, "target_sets": self.sets_spin.value() or None,
            "user_id": self.current_user(),
        })
