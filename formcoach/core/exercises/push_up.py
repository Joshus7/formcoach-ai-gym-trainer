"""Push-up, side view.

Counting signal: shoulder height above the wrist as a percentage of the person's own
arms-straight height (self-calibrating, see DECISIONS.md). Elbow angle and
shoulder-hip-ankle line are used for form.
"""
from __future__ import annotations

from .. import geometry as g
from ..smoothing import RollingPercentile
from .base import Exercise, RepWindow


class PushUp(Exercise):
    key = "push_up"
    name = "Push-up"
    view = "side"
    tip = "Side view: camera at floor level, 2-3 m away, your whole body side-on."
    icon = "pushup"
    joints = ("shoulder", "elbow", "wrist", "hip", "ankle")

    def __init__(self, cfg, general=None):
        super().__init__(cfg, general)
        self._top = RollingPercentile(window_s=self.th.get("calibration_window_s", 6.0), q=90)

    def reset(self):
        self._top.reset()

    def measure(self, lms, side, t):
        sh, el, wr = self.p(lms, side, "shoulder"), self.p(lms, side, "elbow"), self.p(lms, side, "wrist")
        hip, ank = self.p(lms, side, "hip"), self.p(lms, side, "ankle")
        torso = g.torso_length(lms)
        height = g.normalised(wr[1] - sh[1], torso)
        top = self._top(height, t)
        height_pct = 100.0 * height / top if top > 0.05 else float("nan")
        values = {
            "elbow": g.angle(sh, el, wr),
            "height_pct": height_pct,
            "body_line": g.signed_line_deviation(sh, hip, ank),  # + sagging, - piked
        }
        return self.metrics(t, height_pct, values, side)

    def frame_faults(self, m, in_rep):
        out = {}
        if abs(m.values["body_line"]) > self.th["body_line_max_dev"]:
            out["hips_out_of_line"] = self.joint_ids(m.side, "hip", "shoulder", "ankle")
        return out

    def extreme_faults(self, w: RepWindow):
        faults = []
        min_elbow = self.peak(w.frames, "elbow", min, 180.0)
        # Deep enough if the elbow bends far enough or the shoulders drop far enough.
        if w.event.partial or (min_elbow > self.th["depth_max_elbow"]
                               and w.event.extreme > self.th["depth_max_height_pct"]):
            faults.append("not_deep")
        lockout = self.peak(w.lead_in + w.frames[:2], "elbow", max, 180.0)
        if lockout < self.th["lockout_min_elbow"]:
            faults.append("no_lockout")
        return faults
