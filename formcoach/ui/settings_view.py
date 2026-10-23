"""Settings: camera, resolution, voice, theme and advanced threshold editing."""
from __future__ import annotations

import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QRadioButton, QScrollArea, QSlider, QSpinBox, QTabWidget,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core.config import merged
from ..core.exercises import EXERCISES
from ..core.video_source import list_cameras
from ..settings import AppSettings
from .widgets import Card, h_spacer

RESOLUTIONS = [(640, 480), (1280, 720), (1920, 1080)]


class SettingsView(QWidget):
    saved = Signal()
    theme_changed = Signal(str)
    test_voice = Signal(int)

    def __init__(self, settings: AppSettings, base_config: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.base_config = base_config
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(14)
        title = QLabel("Settings")
        title.setObjectName("Title")
        root.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._advanced_tab(), "Advanced thresholds")
        root.addWidget(tabs, 1)

        bottom = QHBoxLayout()
        self.saved_label = QLabel("")
        self.saved_label.setObjectName("Muted")
        bottom.addWidget(self.saved_label)
        bottom.addWidget(h_spacer())
        save = QPushButton("Save settings")
        save.setObjectName("Primary")
        save.clicked.connect(self.save)
        bottom.addWidget(save)
        root.addLayout(bottom)
        self.refresh()

    # ------------------------------------------------------------------ tabs
    def _general_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        card = Card()
        form = QFormLayout(card)
        form.setContentsMargins(20, 16, 20, 16)
        form.setSpacing(12)

        cam_row = QHBoxLayout()
        self.camera = QSpinBox()
        self.camera.setRange(0, 9)
        detect = QPushButton("Detect cameras")
        detect.clicked.connect(self._detect)
        self.cam_info = QLabel("")
        self.cam_info.setObjectName("Muted")
        cam_row.addWidget(self.camera)
        cam_row.addWidget(detect)
        cam_row.addWidget(self.cam_info)
        cam_row.addStretch()
        form.addRow("Camera index", cam_row)

        self.resolution = QComboBox()
        for wd, ht in RESOLUTIONS:
            self.resolution.addItem(f"{wd} x {ht}", (wd, ht))
        form.addRow("Camera resolution", self.resolution)

        self.voice_on = QCheckBox("Spoken feedback (offline)")
        form.addRow("Voice", self.voice_on)
        speed_row = QHBoxLayout()
        self.voice_rate = QSlider(Qt.Orientation.Horizontal)
        self.voice_rate.setRange(100, 260)
        self.rate_label = QLabel()
        self.voice_rate.valueChanged.connect(lambda v: self.rate_label.setText(f"{v} wpm"))
        test = QPushButton("Test voice")
        test.clicked.connect(lambda: self.test_voice.emit(self.voice_rate.value()))
        speed_row.addWidget(self.voice_rate, 1)
        speed_row.addWidget(self.rate_label)
        speed_row.addWidget(test)
        form.addRow("Voice speed", speed_row)

        theme_row = QHBoxLayout()
        self.dark = QRadioButton("Dark")
        self.light = QRadioButton("Light")
        theme_row.addWidget(self.dark)
        theme_row.addWidget(self.light)
        theme_row.addStretch()
        form.addRow("Theme", theme_row)
        lay.addWidget(card)
        note = QLabel("Chart colours follow the new theme after a restart.")
        note.setObjectName("Muted")
        lay.addWidget(note)
        lay.addStretch()
        return w

    def _advanced_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        info = QLabel("Fine-tune rep counting and form rules. Values are stored as overrides on top of "
                      "config/exercises.yaml (which was tuned on the dataset).")
        info.setObjectName("Muted")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Setting", "Value"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.tree, 1)
        row = QHBoxLayout()
        reset = QPushButton("Reset all to tuned defaults")
        reset.clicked.connect(self._reset_overrides)
        row.addWidget(reset)
        row.addStretch()
        lay.addLayout(row)
        return w

    def _fill_tree(self) -> None:
        self.tree.clear()
        self._editors: dict[tuple, QDoubleSpinBox] = {}
        cfg = merged(self.base_config, self.settings.overrides)
        for key, cls in EXERCISES.items():
            top = QTreeWidgetItem([cls.name, ""])
            self.tree.addTopLevelItem(top)
            for section in ("counter", "thresholds"):
                for name, value in cfg[key].get(section, {}).items():
                    if not isinstance(value, (int, float)) or isinstance(value, bool):
                        continue
                    item = QTreeWidgetItem([f"{section}: {name}", ""])
                    top.addChild(item)
                    spin = QDoubleSpinBox()
                    small = abs(value) < 5 and name not in ("min_rep_s",)
                    spin.setDecimals(2 if small or name.endswith("_s") else 1)
                    spin.setRange(-1000, 1000)
                    spin.setSingleStep(0.05 if small else 1.0)
                    spin.setValue(float(value))
                    if self.settings.overrides.get(key, {}).get(section, {}).get(name) is not None:
                        item.setText(0, f"{section}: {name}  (edited)")
                    self.tree.setItemWidget(item, 1, spin)
                    self._editors[(key, section, name)] = spin
            top.setExpanded(key == "push_up")
            for code, fault in cfg[key].get("faults", {}).items():
                item = QTreeWidgetItem([f"score weight: {code}", ""])
                top.addChild(item)
                spin = QDoubleSpinBox()
                spin.setRange(0, 100)
                spin.setDecimals(0)
                spin.setValue(float(fault.get("weight", 0)))
                self.tree.setItemWidget(item, 1, spin)
                self._editors[(key, "faults", code)] = spin

    # ------------------------------------------------------------------ actions
    def refresh(self) -> None:
        s = self.settings
        self.camera.setValue(s.camera_index)
        idx = self.resolution.findData((s.width, s.height))
        self.resolution.setCurrentIndex(idx if idx >= 0 else 1)
        self.voice_on.setChecked(s.voice_on)
        self.voice_rate.setValue(s.voice_rate)
        self.rate_label.setText(f"{s.voice_rate} wpm")
        (self.dark if s.theme == "dark" else self.light).setChecked(True)
        self._fill_tree()

    def _detect(self) -> None:
        cams = list_cameras()
        self.cam_info.setText(f"found: {', '.join(map(str, cams))}" if cams else "no camera found")

    def _reset_overrides(self) -> None:
        self.settings.overrides = {}
        self._fill_tree()
        self.saved_label.setText("Thresholds reset - press Save to keep.")

    def collect_overrides(self) -> dict:
        overrides: dict = {}
        for (key, section, name), spin in self._editors.items():
            if section == "faults":
                base = self.base_config[key]["faults"][name].get("weight", 0)
                if abs(spin.value() - base) > 1e-9:
                    overrides.setdefault(key, {}).setdefault("faults", {})[name] = {"weight": spin.value()}
                continue
            base = self.base_config[key][section][name]
            if abs(spin.value() - float(base)) > 1e-6:
                overrides.setdefault(key, {}).setdefault(section, {})[name] = round(spin.value(), 3)
        return overrides

    def save(self) -> None:
        s = self.settings
        old_theme = s.theme
        s.camera_index = self.camera.value()
        s.width, s.height = self.resolution.currentData()
        s.voice_on = self.voice_on.isChecked()
        s.voice_rate = self.voice_rate.value()
        s.theme = "dark" if self.dark.isChecked() else "light"
        s.overrides = copy.deepcopy(self.collect_overrides())
        s.save()
        self._fill_tree()
        self.saved_label.setText("Saved.")
        if s.theme != old_theme:
            self.theme_changed.emit(s.theme)
        self.saved.emit()
