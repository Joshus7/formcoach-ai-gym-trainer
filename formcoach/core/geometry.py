"""Geometry helpers on 2-D landmark coordinates (pixels, y pointing down)."""
from __future__ import annotations

import math

import numpy as np

from . import landmarks as L


def _xy(p) -> np.ndarray:
    return np.asarray(p, dtype=float)[:2]


def angle(a, b, c) -> float:
    """Angle ABC in degrees (0-180) at vertex b."""
    ba = _xy(a) - _xy(b)
    bc = _xy(c) - _xy(b)
    na, nc = np.linalg.norm(ba), np.linalg.norm(bc)
    if na < 1e-9 or nc < 1e-9:
        return float("nan")
    cos = float(np.dot(ba, bc) / (na * nc))
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def distance(a, b) -> float:
    return float(np.linalg.norm(_xy(a) - _xy(b)))


def line_deviation(a, b, c) -> float:
    """How far the chain a-b-c bends away from a straight line, in degrees (0 = straight)."""
    return 180.0 - angle(a, b, c)


def signed_line_deviation(a, b, c) -> float:
    """Like line_deviation, but positive when b lies below the a-c line (image y down).

    For a push-up seen from the side this is positive for sagging hips and negative
    for piked (raised) hips.
    """
    dev = line_deviation(a, b, c)
    a2, b2, c2 = _xy(a), _xy(b), _xy(c)
    ac = c2 - a2
    if abs(ac[0]) < 1e-9:
        return dev
    # y of the a-c line at b's x; larger y = lower in the image
    t = (b2[0] - a2[0]) / ac[0]
    y_line = a2[1] + t * ac[1]
    return dev if b2[1] > y_line else -dev


def angle_to_vertical(top, bottom) -> float:
    """Angle in degrees between the segment bottom->top and the upward vertical."""
    v = _xy(top) - _xy(bottom)
    n = np.linalg.norm(v)
    if n < 1e-9:
        return float("nan")
    return math.degrees(math.acos(max(-1.0, min(1.0, -v[1] / n))))


def midpoint(a, b) -> np.ndarray:
    return (_xy(a) + _xy(b)) / 2.0


def torso_length(lms: np.ndarray) -> float:
    """Shoulder-midpoint to hip-midpoint distance; used to normalise all distances.

    Falls back to the better single side when one side is missing.
    """
    sh = midpoint(lms[L.LEFT_SHOULDER], lms[L.RIGHT_SHOULDER])
    hp = midpoint(lms[L.LEFT_HIP], lms[L.RIGHT_HIP])
    d = distance(sh, hp)
    if d < 1e-6:
        d = max(distance(lms[L.LEFT_SHOULDER], lms[L.LEFT_HIP]),
                distance(lms[L.RIGHT_SHOULDER], lms[L.RIGHT_HIP]))
    return d


def normalised(value: float, torso: float) -> float:
    """Distance expressed in torso lengths (robust to how far the person stands)."""
    return value / torso if torso > 1e-6 else float("nan")
