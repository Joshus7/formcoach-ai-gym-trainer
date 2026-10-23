"""Bicep curl (dumbbell, one or alternating arms), side view. Signal: elbow angle."""
from __future__ import annotations

import numpy as np

from ... import geometry as g
from ..rep_counter import RepEvent
from .base import Exercise


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

    def extreme_faults(self, event: RepEvent, frames):
        faults = []
        if event.partial or event.extreme > self.th["top_max_elbow"]:
            faults.append("not_full_curl")
        if event.start_peak < self.th["bottom_min_elbow"]:
            faults.append("no_extension")
        lean = self.series(frames, "torso_lean")
        lean = lean[~np.isnan(lean)]
        if len(lean) and (lean.max() - lean[0]) > self.th["body_swing_max"]:
            faults.append("body_swing")
        return faults

