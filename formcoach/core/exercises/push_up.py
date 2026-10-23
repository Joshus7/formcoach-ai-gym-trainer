"""Push-up, side view. Signal: elbow angle."""
from __future__ import annotations

from ... import geometry as g
from ..rep_counter import RepEvent
from .base import Exercise


class PushUp(Exercise):
    key = "push_up"
    name = "Push-up"
    view = "side"
    tip = "Side view: place the camera at floor level, your whole body side-on."
    icon = "pushup"
    joints = ("shoulder", "elbow", "wrist", "hip", "ankle")

    def measure(self, lms, side, t):
        sh, el, wr = self.p(lms, side, "shoulder"), self.p(lms, side, "elbow"), self.p(lms, side, "wrist")
        hip, ank = self.p(lms, side, "hip"), self.p(lms, side, "ankle")
        elbow = g.angle(sh, el, wr)
        body = g.signed_line_deviation(sh, hip, ank)  # + sagging, - piked
        return self.metrics(t, elbow, {"elbow": elbow, "body_line": body}, side)

    def frame_faults(self, m, in_rep):
        out = {}
        if abs(m.values["body_line"]) > self.th["body_line_max_dev"]:
            out["hips_out_of_line"] = self.joint_ids(m.side, "hip", "shoulder", "ankle")
        return out

    def extreme_faults(self, event: RepEvent, frames):
        faults = []
        if event.partial or event.extreme > self.th["depth_max_elbow"]:
            faults.append("not_deep")
        if event.start_peak < self.th["lockout_min_elbow"]:
            faults.append("no_lockout")
        return faults
