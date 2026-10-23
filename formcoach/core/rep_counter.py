"""Generic rep counter: a state machine over one scalar signal (usually a joint angle).

Phases (named for a push-up, but used by every exercise):

    UP    - in the start position (e.g. arms extended, elbow >= start threshold)
    DOWN  - in the turnaround zone (e.g. elbow <= turn threshold)

A rep is UP -> DOWN -> UP. The start and turn thresholds are far apart, which
already gives hysteresis; on top of that the signal must leave the start zone by
``hysteresis`` degrees before a rep is considered started, and a rep shorter than
``min_rep_s`` is discarded as noise. Movements that leave the start zone by at least
``partial_range`` but return without reaching the turn zone are reported as partial
attempts so the exercise can score them as "no rep" (e.g. "Go lower").

``direction="decreasing"`` means the signal goes *down* during the rep (elbow flexion);
``"increasing"`` means it goes up (e.g. wrist height in a shoulder press).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class Phase(str, Enum):
    WAITING = "waiting"   # never been in the start position yet
    UP = "up"
    MOVING = "moving"     # left the start zone, turn zone not reached yet
    DOWN = "down"         # turn zone reached, returning


@dataclass
class RepEvent:
    """Emitted when a rep (or partial attempt) finishes."""
    start_t: float
    end_t: float
    turn_t: float | None
    extreme: float          # most flexed value reached (min for decreasing, max for increasing)
    start_peak: float       # most extended value just before the rep started
    end_peak: float         # value at the moment the rep was completed
    partial: bool = False

    @property
    def duration(self) -> float:
        return self.end_t - self.start_t


@dataclass
class RepCounter:
    start: float               # value that counts as start position
    turn: float                # value that counts as the turnaround
    direction: str = "decreasing"
    hysteresis: float = 5.0
    min_rep_s: float = 0.4
    partial_range: float | None = None
    max_rep_s: float = 20.0    # a "rep" taking longer than this is abandoned

    phase: Phase = field(default=Phase.WAITING, init=False)
    count: int = field(default=0, init=False)
    partials: int = field(default=0, init=False)

    def __post_init__(self):
        if self.direction not in ("decreasing", "increasing"):
            raise ValueError("direction must be 'decreasing' or 'increasing'")
        self._sign = 1.0 if self.direction == "decreasing" else -1.0
        if self._s(self.turn) >= self._s(self.start):
            raise ValueError("turn threshold must be past the start threshold in the rep direction")
        self._reset_rep()

    # Internally everything is mapped so that a rep always goes "down".
    def _s(self, v: float) -> float:
        return self._sign * v

    def _reset_rep(self) -> None:
        self._rep_start_t = None
        self._turn_t = None
        self._extreme = math.inf
        self._top_peak = -math.inf

    def reset(self) -> None:
        """Forget any rep in progress; the next rep needs the start position again."""
        self.phase = Phase.WAITING
        self._reset_rep()

    @property
    def in_rep(self) -> bool:
        return self.phase in (Phase.MOVING, Phase.DOWN)

    def update(self, value: float, t: float) -> RepEvent | None:
        if value is None or math.isnan(value):
            return None
        s = self._s(value)
        start, turn = self._s(self.start), self._s(self.turn)

        if self.phase == Phase.WAITING:
            if s >= start:
                self.phase = Phase.UP
                self._top_peak = s
            return None

        if self.phase == Phase.UP:
            if s >= start - self.hysteresis:
                self._top_peak = max(self._top_peak, s)
            else:
                self.phase = Phase.MOVING
                self._rep_start_t = t
                self._extreme = s
                if s <= turn:
                    self.phase = Phase.DOWN
                    self._turn_t = t
            return None

        self._extreme = min(self._extreme, s)
        if self._rep_start_t is not None and t - self._rep_start_t > self.max_rep_s:
            # Stuck mid-rep (e.g. resting at the bottom): abandon it.
            self.reset()
            return None

        if self.phase == Phase.MOVING:
            if s <= turn:
                self.phase = Phase.DOWN
                self._turn_t = t
            elif s >= start:
                event = None
                rng = self._top_peak - self._extreme
                if (self.partial_range is not None and rng >= self.partial_range
                        and t - self._rep_start_t >= self.min_rep_s):
                    self.partials += 1
                    event = self._event(t, s, partial=True)
                self._back_to_up(s)
                return event
            return None

        # Phase.DOWN
        if s >= start:
            event = None
            if t - self._rep_start_t >= self.min_rep_s:
                self.count += 1
                event = self._event(t, s, partial=False)
            self._back_to_up(s)
            return event
        return None

    def _event(self, t: float, s: float, partial: bool) -> RepEvent:
        return RepEvent(
            start_t=self._rep_start_t, end_t=t, turn_t=self._turn_t,
            extreme=self._sign * self._extreme, start_peak=self._sign * self._top_peak,
            end_peak=self._sign * s, partial=partial,
        )

    def _back_to_up(self, s: float) -> None:
        self.phase = Phase.UP
        self._reset_rep()
        self._top_peak = s
