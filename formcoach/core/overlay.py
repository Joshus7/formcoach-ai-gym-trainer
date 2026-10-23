"""Draw the skeleton and small HUD elements onto OpenCV frames."""
from __future__ import annotations

from collections.abc import Iterable

import cv2
import numpy as np

from . import landmarks as L

OK = (90, 220, 90)        # BGR green
BAD = (60, 60, 235)       # BGR red
DIM = (150, 150, 150)
WHITE = (245, 245, 245)


def draw_skeleton(frame: np.ndarray, lms: np.ndarray, bad_joints: Iterable[int] = (),
                  min_visibility: float = 0.5, thickness: int | None = None) -> np.ndarray:
    """Draw body connections; joints in ``bad_joints`` (and their bones) are red."""
    bad = set(bad_joints)
    h, w = frame.shape[:2]
    t = thickness or max(2, int(round(min(h, w) / 240)))
    for a, b in L.CONNECTIONS:
        va, vb = lms[a, 3], lms[b, 3]
        if va < min_visibility or vb < min_visibility:
            continue
        color = BAD if (a in bad or b in bad) else OK
        pa = (int(lms[a, 0]), int(lms[a, 1]))
        pb = (int(lms[b, 0]), int(lms[b, 1]))
        cv2.line(frame, pa, pb, color, t, cv2.LINE_AA)
    for i in L.BODY_POINTS:
        if lms[i, 3] < min_visibility:
            continue
        p = (int(lms[i, 0]), int(lms[i, 1]))
        color = BAD if i in bad else OK
        cv2.circle(frame, p, t + 3, color, -1, cv2.LINE_AA)
        cv2.circle(frame, p, t + 3, WHITE, 1, cv2.LINE_AA)
    return frame


def draw_label(frame: np.ndarray, text: str, org: tuple[int, int], scale: float = 0.7,
               color=WHITE, bg=(30, 30, 30)) -> None:
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
    x, y = org
    cv2.rectangle(frame, (x - 6, y - th - 6), (x + tw + 6, y + base + 4), bg, -1)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)


def draw_fps(frame: np.ndarray, fps: float) -> None:
    draw_label(frame, f"{fps:4.1f} FPS", (12, 30), 0.6)
