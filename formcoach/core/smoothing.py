"""One Euro filter (Casiez et al., CHI 2012) for landmarks and angles.

Low cutoff when the signal is still (removes jitter), higher cutoff when it moves
fast (keeps lag low). Works element-wise on scalars or numpy arrays.
"""
from __future__ import annotations

import math

import numpy as np


def _alpha(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuroFilter:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.05, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self) -> None:
        self._x = None
        self._dx = None
        self._t = None

    def __call__(self, x, t: float):
        x = np.asarray(x, dtype=float)
        if self._x is None:
            self._x, self._dx, self._t = x.copy(), np.zeros_like(x), t
            return x.copy() if x.ndim else float(x)
        dt = t - self._t
        if dt <= 0:
            # Duplicate or out-of-order timestamp: return the last estimate.
            return self._x.copy() if self._x.ndim else float(self._x)
        self._t = t
        # NaN inputs (missing points) keep the previous estimate.
        x = np.where(np.isnan(x), self._x, x)
        dx = (x - self._x) / dt
        a_d = _alpha(self.d_cutoff, dt)
        self._dx = a_d * dx + (1 - a_d) * self._dx
        cutoff = self.min_cutoff + self.beta * np.abs(self._dx)
        tau = 1.0 / (2.0 * math.pi * cutoff)
        a = 1.0 / (1.0 + tau / dt)
        self._x = a * x + (1 - a) * self._x
        return self._x.copy() if self._x.ndim else float(self._x)


class LandmarkSmoother:
    """Smooths an (N, 4) landmark array [x, y, z, visibility]; visibility is not filtered."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.05, d_cutoff: float = 1.0,
                 reset_after_s: float = 1.0):
        self._filter = OneEuroFilter(min_cutoff, beta, d_cutoff)
        self._last_t: float | None = None
        self.reset_after_s = reset_after_s

    def reset(self) -> None:
        self._filter.reset()
        self._last_t = None

    def __call__(self, lms: np.ndarray, t: float) -> np.ndarray:
        if self._last_t is not None and t - self._last_t > self.reset_after_s:
            self._filter.reset()  # person was lost for a while: don't drag old positions in
        self._last_t = t
        out = lms.astype(float).copy()
        out[:, :3] = self._filter(lms[:, :3], t)
        return out


class RollingPercentile:
    """Percentile of a signal over the last ``window_s`` seconds.

    Used as a self-calibrating reference, e.g. "how high are this person's shoulders
    when their arms are straight", which absorbs camera angle and body size.
    """

    def __init__(self, window_s: float = 6.0, q: float = 90.0):
        self.window_s = window_s
        self.q = q
        self._t: list[float] = []
        self._v: list[float] = []

    def reset(self) -> None:
        self._t, self._v = [], []

    def __call__(self, value: float, t: float) -> float:
        if not np.isnan(value):
            self._t.append(t)
            self._v.append(value)
        while self._t and t - self._t[0] > self.window_s:
            self._t.pop(0)
            self._v.pop(0)
        return float(np.percentile(self._v, self.q)) if self._v else float("nan")
