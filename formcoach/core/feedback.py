"""Turn form faults into short messages, and rate-limit what gets spoken."""
from __future__ import annotations

from dataclasses import dataclass

from .exercises.base import Exercise, RepResult


@dataclass
class Message:
    text: str
    level: str = "info"      # info | good | warn | bad
    say: str | None = None   # what the voice coach should say (None = stay quiet)


class FeedbackManager:
    def __init__(self, exercise: Exercise, live_fault_frames: int = 6, repeat_s: float = 4.0):
        self.exercise = exercise
        self.live_fault_frames = live_fault_frames
        self.repeat_s = repeat_s
        self._streak: dict[str, int] = {}
        self._last_spoken: dict[str, float] = {}

    def live(self, faults: set[str], t: float) -> Message | None:
        """Message for a live (per-frame) fault that has persisted long enough."""
        for code in list(self._streak):
            if code not in faults:
                del self._streak[code]
        best = None
        for code in faults:
            spec = self.exercise.faults.get(code)
            if spec is None or not spec.live:
                continue
            self._streak[code] = self._streak.get(code, 0) + 1
            if self._streak[code] >= self.live_fault_frames:
                if best is None or spec.weight > self.exercise.faults[best].weight:
                    best = code
        if best is None:
            return None
        text = self.exercise.message(best)
        return Message(text, "warn", text if self.should_speak(text, t) else None)

    def for_rep(self, rep: RepResult, t: float, count: int) -> Message:
        """Message shown (and maybe spoken) after a rep finishes."""
        if not rep.valid:
            main = self._worst(rep.faults)
            text = f"No rep - {self.exercise.message(main)}" if main else "No rep"
            spoken = self.exercise.message(main) if main else "No rep"
            return Message(text, "bad", self._speak_rep(spoken, t))
        if rep.faults:
            main = self._worst(rep.faults)
            text = f"{rep.score} - {self.exercise.message(main)}"
            return Message(text, "warn", self._speak_rep(self.exercise.message(main), t, fallback=str(count)))
        return Message(f"{rep.score} - Great rep!", "good", self._speak_rep(str(count), t))

    def _speak_rep(self, text: str, t: float, fallback: str | None = None) -> str | None:
        if self.should_speak(text, t):
            return text
        return fallback  # rep counts are always spoken

    def _worst(self, faults: list[str]) -> str | None:
        known = [f for f in faults if f in self.exercise.faults]
        if not known:
            return None
        return max(known, key=lambda f: (self.exercise.faults[f].major, self.exercise.faults[f].weight))

    def should_speak(self, text: str, t: float) -> bool:
        """True unless the same text was spoken less than repeat_s seconds ago."""
        last = self._last_spoken.get(text)
        if last is not None and t - last < self.repeat_s:
            return False
        self._last_spoken[text] = t
        return True
