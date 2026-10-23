"""One workout session: the exercise, every rep and summary statistics."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime

from .exercises.base import RepResult


@dataclass
class Session:
    exercise: str
    user_id: int | None = None
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: datetime | None = None
    target_reps: int | None = None
    target_sets: int | None = None
    reps: list[RepResult] = field(default_factory=list)
    sets_completed: int = 0
    source: str = ""

    def add_rep(self, rep: RepResult) -> None:
        self.reps.append(rep)

    def finish(self) -> None:
        if self.ended_at is None:
            self.ended_at = datetime.now()

    # ------------------------------------------------------------------ stats
    @property
    def good_reps(self) -> int:
        return sum(r.valid for r in self.reps)

    @property
    def no_reps(self) -> int:
        return sum(not r.valid for r in self.reps)

    @property
    def total_attempts(self) -> int:
        return len(self.reps)

    @property
    def avg_score(self) -> float:
        return sum(r.score for r in self.reps) / len(self.reps) if self.reps else 0.0

    @property
    def best_rep(self) -> RepResult | None:
        return max(self.reps, key=lambda r: (r.score, -r.index)) if self.reps else None

    @property
    def worst_rep(self) -> RepResult | None:
        return min(self.reps, key=lambda r: (r.score, r.index)) if self.reps else None

    @property
    def duration_s(self) -> float:
        end = self.ended_at or datetime.now()
        return max(0.0, (end - self.started_at).total_seconds())

    @property
    def time_under_tension_s(self) -> float:
        return sum(r.duration for r in self.reps)

    @property
    def fault_counts(self) -> Counter:
        return Counter(f for r in self.reps for f in r.faults)

    @property
    def most_common_fault(self) -> str | None:
        c = self.fault_counts
        return c.most_common(1)[0][0] if c else None

    def summary(self) -> dict:
        return {
            "exercise": self.exercise,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "ended_at": self.ended_at.isoformat(timespec="seconds") if self.ended_at else None,
            "total_reps": self.good_reps,
            "no_reps": self.no_reps,
            "attempts": self.total_attempts,
            "avg_score": round(self.avg_score, 1),
            "best_rep": self.best_rep.index if self.best_rep else None,
            "worst_rep": self.worst_rep.index if self.worst_rep else None,
            "duration_s": round(self.duration_s, 1),
            "time_under_tension_s": round(self.time_under_tension_s, 1),
            "most_common_fault": self.most_common_fault,
            "sets_completed": self.sets_completed,
            "reps": [asdict(r) for r in self.reps],
        }
