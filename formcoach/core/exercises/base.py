"""Exercise definition base class.

An exercise turns one frame of landmarks into named measurements (``measure``),
flags per-frame form faults (``frame_faults``) and, when the rep counter reports a
finished rep, decides which faults that rep had (``rep_faults``). All numbers come
from the exercise's section in config/exercises.yaml.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from .. import geometry as g
from .. import landmarks as L
from ..rep_counter import RepCounter, RepEvent


@dataclass
class FrameMetrics:
    t: float
    signal: float
    values: dict[str, float]
    side: str


@dataclass
class FaultSpec:
    code: str
    weight: float
    message: str
    major: bool = False
    live: bool = False


@dataclass
class RepWindow:
    """Everything the exercise needs to judge one finished rep."""
    event: RepEvent
    frames: list[FrameMetrics]                 # frames during the rep
    lead_in: list[FrameMetrics]                # start-position frames just before the rep
    fault_log: list[set[str]]                  # per-frame faults during the rep


@dataclass
class RepResult:
    index: int                 # 1-based, counts no-reps too
    score: int
    faults: list[str]
    valid: bool                # False = "no rep"
    duration: float
    start_t: float
    end_t: float
    metrics: dict[str, float] = field(default_factory=dict)


class Exercise(ABC):
    key: str = ""
    name: str = ""
    view: str = "side"                 # recommended camera view
    tip: str = ""
    icon: str = ""
    joints: tuple[str, ...] = ()       # per-side joints that must be visible
    both_sides: bool = False           # needs left and right (front view exercises)
    extra_points: tuple[int, ...] = ()  # landmarks needed regardless of side
    # threshold key -> ("max" | "min", rep metric name). "max": fault when metric > threshold,
    # "min": fault when metric < threshold. Used by tools/tune_thresholds.py.
    tunable: dict[str, tuple[str, str]] = {}

    def __init__(self, cfg: dict, general: dict | None = None):
        self.cfg = cfg
        self.general = general or {}
        self.th = cfg.get("thresholds", {})
        self.faults = {code: FaultSpec(code, float(f.get("weight", 0)), f.get("message", code),
                                       bool(f.get("major", False)), bool(f.get("live", False)))
                       for code, f in cfg.get("faults", {}).items()}
        self._side: str | None = None

    # ------------------------------------------------------------------ counter
    def make_counter(self) -> RepCounter:
        c = dict(self.cfg["counter"])
        return RepCounter(start=c["start"], turn=c["turn"], direction=c.get("direction", "decreasing"),
                          hysteresis=c.get("hysteresis", 5), min_rep_s=c.get("min_rep_s", 0.5),
                          partial_range=c.get("partial_range"))

    # ------------------------------------------------------------------ visibility
    def required_indices(self, side: str) -> list[int]:
        sides = ("left", "right") if self.both_sides else (side,)
        idx = [L.SIDE[s][j] for s in sides for j in self.joints]
        return idx + list(self.extra_points)

    def choose_side(self, lms: np.ndarray) -> str:
        """Pick the side facing the camera, with stickiness so it doesn't flip every frame."""
        def vis(s):
            return float(np.nanmean([lms[L.SIDE[s][j], 3] for j in self.joints]))
        vl, vr = vis("left"), vis("right")
        best = "left" if vl >= vr else "right"
        if self._side is None or abs(vl - vr) > 0.1:
            self._side = best
        return self._side

    def visibility_ok(self, lms: np.ndarray, side: str, min_vis: float) -> bool:
        v = lms[self.required_indices(side), 3]
        return bool(np.all(np.nan_to_num(v) >= min_vis))

    def visibility_message(self, lms: np.ndarray | None) -> str:
        if lms is None:
            return "Move so your full body is visible"
        if self.view == "side" and self._looks_frontal(lms):
            return "Turn sideways to the camera"
        if self.view == "front" and not self._looks_frontal(lms):
            return "Face the camera"
        return "Move so your full body is visible"

    @staticmethod
    def _looks_frontal(lms: np.ndarray) -> bool:
        """Shoulders far apart relative to the torso and both clearly visible = facing the camera."""
        torso = g.torso_length(lms)
        width = g.distance(lms[L.LEFT_SHOULDER], lms[L.RIGHT_SHOULDER])
        both = lms[L.LEFT_SHOULDER, 3] > 0.8 and lms[L.RIGHT_SHOULDER, 3] > 0.8
        return both and torso > 0 and width / torso > 0.45

    # ------------------------------------------------------------------ per exercise
    def p(self, lms: np.ndarray, side: str, joint: str) -> np.ndarray:
        return lms[L.SIDE[side][joint]]

    @abstractmethod
    def measure(self, lms: np.ndarray, side: str, t: float) -> FrameMetrics:
        ...

    def frame_faults(self, m: FrameMetrics, in_rep: bool) -> dict[str, list[int]]:
        """Return {fault code: landmark indices to colour red} for this frame."""
        return {}

    def rep_metrics(self, w: RepWindow) -> dict[str, float]:
        """Scalar summaries of one rep that the thresholds are compared against."""
        return {}

    def extreme_faults(self, w: RepWindow) -> list[str]:
        """Faults judged on the whole rep (depth, lockout, ...)."""
        return []

    def violates(self, metrics: dict[str, float], threshold_key: str) -> bool:
        kind, name = self.tunable[threshold_key]
        v, th = metrics.get(name, math.nan), self.th[threshold_key]
        if math.isnan(v):
            return False
        return v > th if kind == "max" else v < th

    def reset(self) -> None:
        """Forget per-person calibration (called when the person is lost)."""

    # ------------------------------------------------------------------ scoring
    def rep_faults(self, w: RepWindow) -> list[str]:
        faults = list(self.extreme_faults(w))
        frac = self.general.get("fault_frame_fraction", 0.3)
        if w.fault_log:
            n = len(w.fault_log)
            for code in self.faults:
                share = sum(code in s for s in w.fault_log) / n
                if share >= frac and code not in faults:
                    faults.append(code)
        return faults

    def score(self, faults: list[str]) -> tuple[int, bool]:
        """Score out of 100 and whether the rep is valid (not a no-rep)."""
        s = 100.0 - sum(self.faults[f].weight for f in faults if f in self.faults)
        s = int(round(max(0.0, s)))
        major = any(self.faults[f].major for f in faults if f in self.faults)
        valid = not major and s >= self.general.get("no_rep_below", 50)
        return s, valid

    def message(self, code: str) -> str:
        f = self.faults.get(code)
        return f.message if f else code

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def metrics(t: float, signal: float, values: dict[str, float], side: str) -> FrameMetrics:
        return FrameMetrics(t, signal, values, side)

    @staticmethod
    def joint_ids(side: str, *joints: str) -> list[int]:
        return [L.SIDE[side][j] for j in joints]

    @staticmethod
    def series(frames: list[FrameMetrics], key: str) -> np.ndarray:
        return np.array([f.values.get(key, math.nan) for f in frames], dtype=float)

    def frame_quantile(self, frames: list[FrameMetrics], key: str, absolute: bool = False) -> float:
        """Value exceeded in ``fault_frame_fraction`` of the frames - matches how per-frame faults
        become rep faults, so per-frame thresholds can be tuned on it."""
        s = self.series(frames, key)
        s = s[~np.isnan(s)]
        if not len(s):
            return math.nan
        if absolute:
            s = np.abs(s)
        return float(np.quantile(s, 1 - self.general.get("fault_frame_fraction", 0.3)))

    @classmethod
    def peak(cls, frames: list[FrameMetrics], key: str, fn=np.nanmax, default: float = math.nan) -> float:
        """fn (nanmax / nanmin) of a value over frames, or default if there is no data."""
        fn = {max: np.nanmax, min: np.nanmin}.get(fn, fn)
        s = cls.series(frames, key)
        return float(fn(s)) if np.any(~np.isnan(s)) else default
