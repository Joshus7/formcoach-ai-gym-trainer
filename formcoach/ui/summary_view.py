"""Session summary: totals, best/worst rep, most common mistake and a rep-score chart."""
from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..core.exercises import EXERCISES
from ..core.session import Session
from .theme import Palette
from .widgets import Card, StatCard, h_spacer


def fmt_duration(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}:{s:02d}"


class SummaryView(QWidget):
    home_requested = Signal()
    history_requested = Signal()
    export_csv_requested = Signal()
    export_pdf_requested = Signal()

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self.p = palette
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(16)
        self.title = QLabel("Workout complete")
        self.title.setObjectName("Title")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("Subtitle")
        root.addWidget(self.title)
        root.addWidget(self.subtitle)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.cards = {k: StatCard(label) for k, label in [
            ("reps", "Total reps"), ("split", "Good / no-reps"), ("avg", "Average score"),
            ("best", "Best rep"), ("worst", "Worst rep"), ("duration", "Duration"),
            ("tut", "Time under tension"), ("sets", "Sets completed")]}
        for i, card in enumerate(self.cards.values()):
            grid.addWidget(card, i // 4, i % 4)
        root.addLayout(grid)

        mistake = Card()
        ml = QVBoxLayout(mistake)
        ml.setContentsMargins(18, 12, 18, 12)
        lbl = QLabel("MOST COMMON MISTAKE")
        lbl.setObjectName("StatLabel")
        self.mistake = QLabel("-")
        self.mistake.setObjectName("Section")
        ml.addWidget(lbl)
        ml.addWidget(self.mistake)
        root.addWidget(mistake)

        chart_card = Card()
        cl = QVBoxLayout(chart_card)
        cl.setContentsMargins(12, 12, 12, 12)
        lbl = QLabel("Score per rep (orange = no rep)")
        lbl.setObjectName("Section")
        cl.addWidget(lbl)
        self.plot = pg.PlotWidget()
        self.plot.setBackground(palette.surface)
        self.plot.setYRange(0, 100)
        self.plot.setLabel("left", "score")
        self.plot.setLabel("bottom", "rep")
        self.plot.showGrid(y=True, alpha=0.2)
        self.plot.setMouseEnabled(False, False)
        self.plot.setMinimumHeight(220)
        cl.addWidget(self.plot)
        root.addWidget(chart_card, 1)

        buttons = QHBoxLayout()
        self.csv_btn = QPushButton("Export CSV")
        self.csv_btn.clicked.connect(self.export_csv_requested)
        self.pdf_btn = QPushButton("Export PDF")
        self.pdf_btn.clicked.connect(self.export_pdf_requested)
        hist = QPushButton("History")
        hist.clicked.connect(self.history_requested)
        home = QPushButton("New workout")
        home.setObjectName("Primary")
        home.clicked.connect(self.home_requested)
        buttons.addWidget(self.csv_btn)
        buttons.addWidget(self.pdf_btn)
        buttons.addWidget(h_spacer())
        buttons.addWidget(hist)
        buttons.addWidget(home)
        root.addLayout(buttons)

    def show_session(self, s: Session, fault_messages: dict[str, str]) -> None:
        name = EXERCISES[s.exercise].name if s.exercise in EXERCISES else s.exercise
        self.title.setText(f"{name} - workout complete" if s.reps else f"{name} - no reps recorded")
        self.subtitle.setText(f"{s.started_at:%A %d %B %Y, %H:%M}  -  input: {s.source or '-'}")
        self.cards["reps"].set(s.good_reps)
        self.cards["split"].set(f"{s.good_reps} / {s.no_reps}")
        self.cards["avg"].set(f"{s.avg_score:.0f}" if s.reps else "-")
        best, worst = s.best_rep, s.worst_rep
        self.cards["best"].set(f"#{best.index} ({best.score})" if best else "-")
        self.cards["worst"].set(f"#{worst.index} ({worst.score})" if worst else "-")
        self.cards["duration"].set(fmt_duration(s.duration_s))
        self.cards["tut"].set(f"{s.time_under_tension_s:.0f} s")
        self.cards["sets"].set(s.sets_completed or ("1" if s.reps else "0"))
        fault = s.most_common_fault
        if fault:
            n = s.fault_counts[fault]
            self.mistake.setText(f"{fault_messages.get(fault, fault)}  ({n} of {len(s.reps)} reps)")
        else:
            self.mistake.setText("None - clean workout!" if s.reps else "-")
        self.plot.clear()
        if s.reps:
            xs = [r.index for r in s.reps]
            colors = [self.p.good if r.valid else self.p.warn for r in s.reps]
            bars = pg.BarGraphItem(x=xs, height=[r.score for r in s.reps], width=0.7,
                                   brushes=[pg.mkBrush(c) for c in colors], pens=[pg.mkPen(None)] * len(xs))
            self.plot.addItem(bars)
            self.plot.setXRange(0.3, max(xs) + 0.7)
            step = max(1, len(xs) // 15)
            self.plot.getAxis("bottom").setTicks([[(x, str(x)) for x in xs[::step]]])
