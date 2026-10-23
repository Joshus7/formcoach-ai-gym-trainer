"""Reusable widgets: video display, stat cards and simple exercise pictograms."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget


def bgr_to_qimage(frame: np.ndarray) -> QImage:
    h, w = frame.shape[:2]
    rgb = np.ascontiguousarray(frame[:, :, ::-1])
    return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


class VideoView(QLabel):
    """Shows frames scaled to fit, keeping the aspect ratio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(480, 270)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #000; border-radius: 14px;")
        self._image: QImage | None = None

    def set_image(self, image: QImage) -> None:
        self._image = image
        self._rescale()

    def set_message(self, text: str) -> None:
        self._image = None
        self.clear()
        self.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._image is None:
            return
        pm = QPixmap.fromImage(self._image).scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(pm)


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")


class StatCard(Card):
    def __init__(self, label: str, value: str = "-", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)
        self.value = QLabel(value)
        self.value.setObjectName("StatValue")
        self.label = QLabel(label)
        self.label.setObjectName("StatLabel")
        lay.addWidget(self.value)
        lay.addWidget(self.label)

    def set(self, value) -> None:
        self.value.setText(str(value))


# Stick-figure pictograms in a 100x100 box: list of (x1, y1, x2, y2) segments + head (x, y).
_FIGURES = {
    "push_up": ([(18, 62, 44, 50), (44, 50, 84, 66), (24, 60, 24, 78), (84, 66, 92, 78)], (12, 56)),
    "pull_up": ([(20, 14, 80, 14), (36, 14, 40, 34), (64, 14, 60, 34), (40, 34, 50, 40), (60, 34, 50, 40),
                 (50, 40, 50, 66), (50, 66, 44, 90), (50, 66, 56, 90)], (50, 28)),
    "squat": ([(46, 30, 40, 56), (40, 56, 62, 60), (62, 60, 58, 86), (46, 36, 72, 40)], (48, 20)),
    "bicep_curl": ([(50, 30, 50, 62), (50, 62, 44, 90), (50, 62, 56, 90), (50, 34, 54, 50),
                    (54, 50, 64, 38)], (50, 20)),
    "shoulder_press": ([(50, 34, 50, 64), (50, 64, 44, 90), (50, 64, 56, 90), (50, 36, 36, 26),
                        (36, 26, 36, 8), (50, 36, 64, 26), (64, 26, 64, 8)], (50, 24)),
}


def exercise_icon(key: str, color: str = "#4f8cff", size: int = 64) -> QPixmap:
    pm = QPixmap(QSize(size, size))
    pm.fill(Qt.GlobalColor.transparent)
    segs, head = _FIGURES.get(key, ([], (50, 50)))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 100
    pen = QPen(QColor(color), max(2.0, 6 * s), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    for x1, y1, x2, y2 in segs:
        p.drawLine(QPointF(x1 * s, y1 * s), QPointF(x2 * s, y2 * s))
    p.setBrush(QColor(color))
    p.drawEllipse(QPointF(head[0] * s, head[1] * s), 7 * s, 7 * s)
    p.end()
    return pm


def h_spacer() -> QWidget:
    w = QWidget()
    w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return w
