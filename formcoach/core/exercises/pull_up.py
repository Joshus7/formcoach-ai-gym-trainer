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

    def extreme_faults(self, w: RepWindow):
        faults = []
        if w.event.partial or self.peak(w.frames, "chin_above_wrist", max, -1.0) < self.th["chin_min_above_wrist"]:
            faults.append("chin_not_over")
        if w.event.start_peak < self.th["hang_min_elbow"]:
            faults.append("no_full_hang")
        hip = self.series(w.frames, "hip_x")
        if np.sum(~np.isnan(hip)) > 2 and np.nanmax(hip) - np.nanmin(hip) > self.th["kipping_max_hip_range"]:
            faults.append("kipping")
        return faults
