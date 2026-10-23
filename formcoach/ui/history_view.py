"""History: past sessions per user, exercise filter, progress charts, exports."""
from __future__ import annotations

from datetime import datetime

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core.exercises import EXERCISES
from ..data.db import Database
from .theme import Palette
from .widgets import Card, h_spacer


class HistoryView(QWidget):
    open_session = Signal(int)
    export_history = Signal(object)          # exercise filter or None
    export_session_csv = Signal(int)
    export_session_pdf = Signal(int)

    COLS = ["Date", "Exercise", "Reps", "No-reps", "Avg score", "Duration"]

    def __init__(self, db: Database, palette: Palette, user_getter, parent=None):
        super().__init__(parent)
        self.db = db
        self.p = palette
        self.user_getter = user_getter
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(14)

        head = QHBoxLayout()
        title = QLabel("History")
        title.setObjectName("Title")
        head.addWidget(title)
        head.addWidget(h_spacer())
        self.user_label = QLabel()
        self.user_label.setObjectName("Muted")
        head.addWidget(self.user_label)
        head.addSpacing(12)
        head.addWidget(QLabel("Exercise"))
        self.filter = QComboBox()
        self.filter.addItem("All exercises", None)
        for key, cls in EXERCISES.items():
            self.filter.addItem(cls.name, key)
        self.filter.currentIndexChanged.connect(self.refresh)
        head.addWidget(self.filter)
        root.addLayout(head)

        charts = QHBoxLayout()
        charts.setSpacing(12)
        self.reps_plot = self._plot("Reps per session", "reps")
        self.score_plot = self._plot("Average score", "score")
        self.score_plot.setYRange(0, 100)
        for title_text, plot in (("Reps per session", self.reps_plot), ("Average score over time", self.score_plot)):
            card = Card()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            lbl = QLabel(title_text)
            lbl.setObjectName("Section")
            cl.addWidget(lbl)
            cl.addWidget(plot)
            charts.addWidget(card)
        root.addLayout(charts, 2)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda row, _c: self._emit_selected(self.open_session))
        root.addWidget(self.table, 3)

        self.empty = QLabel("No workouts yet - finish a session and it will appear here.")
        self.empty.setObjectName("Muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.empty)

        buttons = QHBoxLayout()
        b_open = QPushButton("Open summary")
        b_open.clicked.connect(lambda: self._emit_selected(self.open_session))
        b_csv = QPushButton("Session CSV")
        b_csv.clicked.connect(lambda: self._emit_selected(self.export_session_csv))
        b_pdf = QPushButton("Session PDF")
        b_pdf.clicked.connect(lambda: self._emit_selected(self.export_session_pdf))
        b_del = QPushButton("Delete session")
        b_del.clicked.connect(self._delete)
        b_all = QPushButton("Export history CSV")
        b_all.clicked.connect(lambda: self.export_history.emit(self.filter.currentData()))
        for b in (b_open, b_csv, b_pdf, b_del):
            buttons.addWidget(b)
        buttons.addWidget(h_spacer())
        buttons.addWidget(b_all)
        root.addLayout(buttons)
        self._ids: list[int] = []

    def _plot(self, title: str, ylabel: str) -> pg.PlotWidget:
        plot = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        plot.setBackground(self.p.surface)
        plot.showGrid(y=True, alpha=0.2)
        plot.setLabel("left", ylabel)
        plot.setMinimumHeight(180)
        return plot

    def refresh(self) -> None:
        uid = self.user_getter()
        self.user_label.setText(f"Profile: {self.db.user_name(uid)}")
        rows = self.db.list_sessions(uid, self.filter.currentData())
        self._ids = [r["id"] for r in reversed(rows)]
        self.table.setRowCount(len(rows))
        for i, r in enumerate(reversed(rows)):
            m, s = divmod(int(r["duration_s"]), 60)
            vals = [datetime.fromisoformat(r["started_at"]).strftime("%d %b %Y %H:%M"),
                    EXERCISES[r["exercise"]].name if r["exercise"] in EXERCISES else r["exercise"],
                    str(r["total_reps"]), str(r["no_reps"]), f"{r['avg_score']:.0f}", f"{m}:{s:02d}"]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if j >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, j, item)
        self.empty.setVisible(not rows)
        self.table.setVisible(bool(rows))

        self.reps_plot.clear()
        self.score_plot.clear()
        if rows:
            xs = [datetime.fromisoformat(r["started_at"]).timestamp() for r in rows]
            pen = pg.mkPen(self.p.accent, width=2)
            self.reps_plot.plot(xs, [r["total_reps"] for r in rows], pen=pen, symbol="o",
                                symbolBrush=self.p.accent, symbolSize=7)
            self.score_plot.plot(xs, [r["avg_score"] for r in rows], pen=pg.mkPen(self.p.good, width=2),
                                 symbol="o", symbolBrush=self.p.good, symbolSize=7)
            if len(xs) == 1:  # give a single point some room
                for plot in (self.reps_plot, self.score_plot):
                    plot.setXRange(xs[0] - 3600, xs[0] + 3600)
            else:
                for plot in (self.reps_plot, self.score_plot):
                    plot.enableAutoRange(axis="x")

    def selected_session(self) -> int | None:
        row = self.table.currentRow()
        return self._ids[row] if 0 <= row < len(self._ids) else None

    def _emit_selected(self, signal) -> None:
        sid = self.selected_session()
        if sid is not None:
            signal.emit(sid)

    def _delete(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        sid = self.selected_session()
        if sid is None:
            return
        if QMessageBox.question(self, "Delete session", "Delete this workout permanently?") == \
                QMessageBox.StandardButton.Yes:
            self.db.delete_session(sid)
            self.refresh()
