"""Pull-up, front view. Signal: mean elbow angle; chin-over-bar from nose vs wrists."""
from __future__ import annotations

import numpy as np

from .. import geometry as g
from .. import landmarks as L
from .base import Exercise, RepWindow


class PullUp(Exercise):
    key = "pull_up"
    name = "Pull-up"
    view = "front"
    tip = "Front view: camera facing you from a few metres, bar and hips in frame."
    icon = "pullup"
    joints = ("shoulder", "elbow", "wrist", "hip")
    both_sides = True
    extra_points = (L.NOSE,)

    def choose_side(self, lms):
        return "both"

    def required_indices(self, side):
        return super().required_indices("left")

    def measure(self, lms, side, t):
        torso = g.torso_length(lms)
        elbows = [g.angle(*(self.p(lms, s, j) for j in ("shoulder", "elbow", "wrist"))) for s in ("left", "right")]
        wrist_y = (lms[L.LEFT_WRIST, 1] + lms[L.RIGHT_WRIST, 1]) / 2
        hip = g.midpoint(lms[L.LEFT_HIP], lms[L.RIGHT_HIP])
        sh = g.midpoint(lms[L.LEFT_SHOULDER], lms[L.RIGHT_SHOULDER])
        elbow = float(np.mean(elbows))
        vals = {
            "elbow": elbow,
            "chin_above_wrist": g.normalised(wrist_y - lms[L.NOSE, 1], torso),
            # hip position relative to the shoulders, so the body rising doesn't count as swing
            "hip_x": g.normalised(hip[0] - sh[0], torso),
        }
        return self.metrics(t, elbow, vals, side)

    tunable = {
        "chin_min_above_wrist": ("min", "chin_above_wrist"),
        "hang_min_elbow": ("min", "hang_elbow"),
        "kipping_max_hip_range": ("max", "hip_range"),
    }

    def rep_metrics(self, w: RepWindow):
        hip = self.series(w.frames, "hip_x")
        hip = hip[~np.isnan(hip)]
        return {
            "chin_above_wrist": self.peak(w.frames, "chin_above_wrist", max, -1.0),
            "hang_elbow": w.event.start_peak,
            "hip_range": float(hip.max() - hip.min()) if len(hip) > 2 else 0.0,
        }

    def extreme_faults(self, w: RepWindow):
        m = self.rep_metrics(w)
        faults = []
        if w.event.partial or self.violates(m, "chin_min_above_wrist"):
            faults.append("chin_not_over")
        if self.violates(m, "hang_min_elbow"):
            faults.append("no_full_hang")
        if self.violates(m, "kipping_max_hip_range"):
            faults.append("kipping")
        return faults
