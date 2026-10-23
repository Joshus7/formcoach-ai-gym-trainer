"""Workout engine: landmarks in, rep counts / form feedback / scores out.

The engine does not run pose estimation itself, so it can be fed live MediaPipe
results, cached landmark files (evaluation) or synthetic data (tests).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from . import exercises
from .exercises.base import FrameMetrics, RepResult
from .feedback import FeedbackManager, Message
from .rep_counter import Phase
from .session import Session
from .smoothing import LandmarkSmoother


class State(str, Enum):
    NO_POSE = "no_pose"            # nobody detected
    NOT_VISIBLE = "not_visible"    # required joints hidden / wrong camera angle
    COUNTDOWN = "countdown"        # "get into position"
    ACTIVE = "active"
    FINISHED = "finished"          # target sets reached


@dataclass
class EngineOutput:
    t: float
    state: State
    landmarks: np.ndarray | None
    bad_joints: set[int] = field(default_factory=set)
    message: Message | None = None
    countdown: float = 0.0
    reps: int = 0                  # valid reps in the whole session
    no_reps: int = 0
    set_number: int = 1
    reps_in_set: int = 0
    phase: str = Phase.WAITING.value
    signal: float = float("nan")
    new_rep: RepResult | None = None
    set_completed: bool = False


class WorkoutEngine:
    # Brief landmark dropouts shorter than this don't pause counting.
    DROPOUT_GRACE_S = 0.5

    def __init__(self, exercise_key: str, config: dict, target_reps: int | None = None,
                 target_sets: int | None = None, countdown_s: float | None = None,
                 user_id: int | None = None, source: str = ""):
        self.config = config
        general = config.get("general", {})
        self.exercise = exercises.create(exercise_key, config)
        self.counter = self.exercise.make_counter()
        self.min_vis = general.get("min_visibility", 0.6)
        self.countdown_s = general.get("countdown_s", 3) if countdown_s is None else countdown_s
        oe = general.get("one_euro", {})
        self.smoother = LandmarkSmoother(oe.get("min_cutoff", 1.5), oe.get("beta", 0.02), oe.get("d_cutoff", 1.0))
        self.feedback = FeedbackManager(self.exercise, general.get("live_fault_frames", 6),
                                        general.get("voice_repeat_s", 4.0))
        self.session = Session(exercise_key, user_id=user_id, target_reps=target_reps,
                               target_sets=target_sets, source=source)
        self.target_reps = target_reps
        self.target_sets = target_sets
        self.state = State.NO_POSE if self.countdown_s > 0 else State.ACTIVE
        self._countdown_start: float | None = None
        self._last_ok_t: float | None = None
        self._rep_frames: list[FrameMetrics] = []
        self._rep_fault_log: list[set[str]] = []
        self._set_number = 1
        self._reps_in_set = 0
        self._last_message: Message | None = None
        self._message_until = 0.0
        self._started = self.countdown_s <= 0

    # ------------------------------------------------------------------ public
    def process(self, landmarks: np.ndarray | None, t: float) -> EngineOutput:
        """Feed one frame. ``landmarks`` is the raw (33, 4) pose or None; ``t`` in seconds."""
        if self.state == State.FINISHED:
            return self._output(t, None)
        if landmarks is None or np.isnan(landmarks[:, 0]).all():
            return self._lost(t, None, State.NO_POSE)

        lms = self.smoother(landmarks, t)
        side = self.exercise.choose_side(lms)
        if not self.exercise.visibility_ok(lms, side, self.min_vis):
            return self._lost(t, lms, State.NOT_VISIBLE)
        self._last_ok_t = t

        if not self._started:
            return self._countdown(t, lms)
        self.state = State.ACTIVE
        return self._active(t, lms, side)

    def next_set(self) -> None:
        """Manually start the next set (e.g. a button in the UI)."""
        if self._reps_in_set:
            self._complete_set()

    def finish(self) -> Session:
        self.session.finish()
        return self.session

    # ------------------------------------------------------------------ states
    def _lost(self, t: float, lms, state: State) -> EngineOutput:
        if self._started and self._last_ok_t is not None and t - self._last_ok_t < self.DROPOUT_GRACE_S:
            return self._output(t, lms)  # momentary glitch: keep the rep in progress
        if self.counter.in_rep:
            self._abandon_rep()
        self.counter.reset()
        self._countdown_start = None
        self.state = state
        msg = Message(self.exercise.visibility_message(lms if state != State.NO_POSE else None), "info")
        out = self._output(t, lms, message=msg)
        return out

    def _countdown(self, t: float, lms) -> EngineOutput:
        if self._countdown_start is None:
            self._countdown_start = t
        remaining = self.countdown_s - (t - self._countdown_start)
        if remaining <= 0:
            self._started = True
            self.state = State.ACTIVE
            self.counter.reset()
            return self._output(t, lms, message=Message("Go!", "good", "Go"))
        self.state = State.COUNTDOWN
        out = self._output(t, lms, message=Message("Get into position", "info"))
        out.countdown = remaining
        return out

    def _active(self, t: float, lms, side: str) -> EngineOutput:
        m = self.exercise.measure(lms, side, t)
        frame_faults = self.exercise.frame_faults(m, self.counter.in_rep)
        bad = {j for joints in frame_faults.values() for j in joints}
        event = self.counter.update(m.signal, t)

        if self.counter.in_rep or event is not None:
            self._rep_frames.append(m)
            self._rep_fault_log.append(set(frame_faults))

        new_rep = None
        set_done = False
        message = self.feedback.live(set(frame_faults), t)
        if event is not None:
            faults = self.exercise.rep_faults(event, self._rep_frames, self._rep_fault_log)
            score, valid = self.exercise.score(faults)
            new_rep = RepResult(
                index=len(self.session.reps) + 1, score=score, faults=faults, valid=valid,
                duration=round(event.duration, 3), start_t=round(event.start_t, 3), end_t=round(event.end_t, 3),
                metrics={"extreme": round(float(event.extreme), 3), "start_peak": round(float(event.start_peak), 3)},
            )
            self.session.add_rep(new_rep)
            if valid:
                self._reps_in_set += 1
            message = self.feedback.for_rep(new_rep, t, self._reps_in_set)
            self._rep_frames, self._rep_fault_log = [], []
            if self.target_reps and self._reps_in_set >= self.target_reps:
                set_done = True
                self._complete_set()
                if message.say and self.state != State.FINISHED:
                    message.say = f"{message.say}. Set complete"
        elif not self.counter.in_rep and self._rep_frames:
            self._rep_frames, self._rep_fault_log = [], []

        out = self._output(t, lms, bad=bad, message=message, signal=m.signal)
        out.new_rep = new_rep
        out.set_completed = set_done
        return out

    # ------------------------------------------------------------------ helpers
    def _abandon_rep(self) -> None:
        self._rep_frames, self._rep_fault_log = [], []

    def _complete_set(self) -> None:
        self.session.sets_completed += 1
        if self.target_sets and self.session.sets_completed >= self.target_sets:
            self.state = State.FINISHED
            self.session.finish()
            return
        self._set_number += 1
        self._reps_in_set = 0

    def _output(self, t: float, lms, bad=None, message: Message | None = None,
                signal: float = float("nan")) -> EngineOutput:
        # Rep messages stay on screen for a moment even if the next frame has none.
        if message is not None:
            self._last_message, self._message_until = message, t + 2.0
        elif self._last_message is not None and t < self._message_until:
            message = Message(self._last_message.text, self._last_message.level)
        return EngineOutput(
            t=t, state=self.state, landmarks=lms, bad_joints=bad or set(), message=message,
            reps=self.session.good_reps, no_reps=self.session.no_reps,
            set_number=self._set_number, reps_in_set=self._reps_in_set,
            phase=self.counter.phase.value, signal=signal,
        )
