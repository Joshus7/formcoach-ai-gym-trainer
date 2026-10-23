"""Bodyweight squat, side view. Signal: knee angle."""
from __future__ import annotations

import numpy as np

from ... import geometry as g
from ..rep_counter import RepEvent
from .base import Exercise


class Squat(Exercise):
    key = "squat"
    name = "Squat"
    view = "side"
    tip = "Side view: camera at hip height, 2-3 m away, whole body side-on."
    icon = "squat"
    joints = ("shoulder", "hip", "knee", "ankle", "heel", "foot")

    def measure(self, lms, side, t):
        sh, hip, knee = self.p(lms, side, "shoulder"), self.p(lms, side, "hip"), self.p(lms, side, "knee")
        ank, heel, foot = self.p(lms, side, "ankle"), self.p(lms, side, "heel"), self.p(lms, side, "foot")
        torso = g.torso_length(lms)
        knee_angle = g.angle(hip, knee, ank)
        facing = 1.0 if foot[0] >= heel[0] else -1.0
        values = {
            "knee": knee_angle,
            "hip_below_knee": g.normalised(hip[1] - knee[1], torso),
            "torso_lean": g.angle_to_vertical(sh, hip),
            "knee_past_toe": g.normalised((knee[0] - foot[0]) * facing, torso),
        }
        return self.metrics(t, knee_angle, values, side)

    def frame_faults(self, m, in_rep):
        out = {}
        if not in_rep:
            return out
        if m.values["torso_lean"] > self.th["torso_lean_max"]:
            out["torso_lean"] = self.joint_ids(m.side, "shoulder", "hip")
        if m.values["knee_past_toe"] > self.th["knee_past_toe_max"]:
            out["knees_forward"] = self.joint_ids(m.side, "knee", "foot")
        return out

    def extreme_faults(self, event: RepEvent, frames):
        faults = []
        depth = np.nanmax(self.series(frames, "hip_below_knee")) if frames else -1.0
        # Deep enough if either the knee bends far enough or the hip reaches knee level.
        if event.partial or (event.extreme > self.th["depth_max_knee"]
                             and depth < self.th["depth_min_hip_below_knee"]):
            faults.append("not_deep")
        if event.start_peak < self.th["lockout_min_knee"]:
            faults.append("no_lockout")
        return faults
