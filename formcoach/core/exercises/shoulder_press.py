"""Dumbbell shoulder press, front view. Signal: wrist height above shoulders (torso lengths)."""
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
        torso = g.torso_length(lms)
        vals = {}
        for s in ("left", "right"):
            sh, el, wr = (self.p(lms, s, j) for j in ("shoulder", "elbow", "wrist"))
            vals[f"height_{s}"] = g.normalised(sh[1] - wr[1], torso)
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

    def extreme_faults(self, w: RepWindow):
        faults = []
        lock = min(self.peak(w.frames, "elbow_left", max, 0.0), self.peak(w.frames, "elbow_right", max, 0.0))
        if w.event.partial or lock < self.th["lockout_min_elbow"]:
            faults.append("no_lockout")
        if w.event.start_peak > self.th["bottom_max_height"]:
            faults.append("not_low")
        return faults
