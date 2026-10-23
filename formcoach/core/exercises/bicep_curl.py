"""Bicep curl (dumbbell), side view. Signal: elbow angle of the arm nearest the camera."""
from __future__ import annotations

import numpy as np

from .. import geometry as g
from .base import Exercise, RepWindow


class BicepCurl(Exercise):
    key = "bicep_curl"
    name = "Bicep curl"
    view = "side"
    tip = "Side view: camera at chest height, the working arm closest to the camera."
    icon = "curl"
    joints = ("shoulder", "elbow", "wrist", "hip")

    def measure(self, lms, side, t):
        sh, el, wr, hip = (self.p(lms, side, j) for j in ("shoulder", "elbow", "wrist", "hip"))
        elbow = g.angle(sh, el, wr)
        # Upper arm angle from hanging straight down (0 = elbow directly below the shoulder).
        upper_arm = g.angle_to_vertical(sh, el)
        lean = g.angle_to_vertical(sh, hip)
        return self.metrics(t, elbow, {"elbow": elbow, "upper_arm": upper_arm, "torso_lean": lean}, side)

    def frame_faults(self, m, in_rep):
        out = {}
        if in_rep and m.values["upper_arm"] > self.th["upper_arm_max_swing"]:
            out["elbow_drift"] = self.joint_ids(m.side, "elbow", "shoulder")
        return out

    tunable = {
        "top_max_elbow": ("max", "min_elbow"),
        "bottom_min_elbow": ("min", "extension_elbow"),
        "upper_arm_max_swing": ("max", "upper_arm"),
        "body_swing_max": ("max", "body_swing"),
    }

    def rep_metrics(self, w: RepWindow):
        lean = self.series(w.lead_in[-3:] + w.frames, "torso_lean")
        lean = lean[~np.isnan(lean)]
        return {
            "min_elbow": w.event.extreme,
            "extension_elbow": w.event.start_peak,
            "upper_arm": self.frame_quantile(w.frames, "upper_arm"),
            "body_swing": float(lean.max() - lean[0]) if len(lean) > 1 else 0.0,
        }

    def extreme_faults(self, w: RepWindow):
        m = self.rep_metrics(w)
        faults = []
        if w.event.partial or self.violates(m, "top_max_elbow"):
            faults.append("not_full_curl")
        if self.violates(m, "bottom_min_elbow"):
            faults.append("no_extension")
        if self.violates(m, "body_swing_max"):
            faults.append("body_swing")
        return faults
