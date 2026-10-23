"""Dumbbell shoulder press, front view.

Signal: wrist height above the shoulders in arm lengths (shoulder-elbow + elbow-wrist), which
reads ~1.0 at full lockout for everyone; torso length varies too much in a front view.
"""
from __future__ import annotations

from .. import geometry as g
from .base import Exercise, RepWindow


class ShoulderPress(Exercise):
    key = "shoulder_press"
    name = "Shoulder press"
    view = "front"
    tip = "Front view: face the camera, both arms and your hips in frame."
    icon = "press"
    joints = ("shoulder", "elbow", "wrist", "hip")
    both_sides = True

    def choose_side(self, lms):
        return "both"

    def required_indices(self, side):
        return super().required_indices("left")

    def measure(self, lms, side, t):
        vals = {}
        for s in ("left", "right"):
            sh, el, wr = (self.p(lms, s, j) for j in ("shoulder", "elbow", "wrist"))
            arm = g.distance(sh, el) + g.distance(el, wr)
            vals[f"height_{s}"] = g.normalised(sh[1] - wr[1], arm)
            vals[f"elbow_{s}"] = g.angle(sh, el, wr)
        height = (vals["height_left"] + vals["height_right"]) / 2
        vals["height"] = height
        vals["asymmetry"] = abs(vals["height_left"] - vals["height_right"])
        return self.metrics(t, height, vals, side)

    def frame_faults(self, m, in_rep):
        out = {}
        if in_rep and m.values["asymmetry"] > self.th["symmetry_max_diff"]:
            out["uneven"] = self.joint_ids("left", "wrist", "elbow") + self.joint_ids("right", "wrist", "elbow")
        return out

    tunable = {
        "lockout_min_elbow": ("min", "lockout_elbow"),
        "bottom_max_height": ("max", "bottom_height"),
        "symmetry_max_diff": ("max", "asymmetry"),
    }

    def rep_metrics(self, w: RepWindow):
        return {
            "lockout_elbow": min(self.peak(w.frames, "elbow_left", max, 0.0),
                                 self.peak(w.frames, "elbow_right", max, 0.0)),
            "bottom_height": w.event.start_peak,
            "asymmetry": self.frame_quantile(w.frames, "asymmetry"),
        }

    def extreme_faults(self, w: RepWindow):
        m = self.rep_metrics(w)
        faults = []
        if w.event.partial or self.violates(m, "lockout_min_elbow"):
            faults.append("no_lockout")
        if self.violates(m, "bottom_max_height"):
            faults.append("not_low")
        return faults
