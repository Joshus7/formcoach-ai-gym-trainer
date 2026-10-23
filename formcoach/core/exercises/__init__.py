"""Exercise registry."""
from __future__ import annotations

from .base import Exercise, FaultSpec, FrameMetrics, RepResult, RepWindow
from .bicep_curl import BicepCurl
from .pull_up import PullUp
from .push_up import PushUp
from .shoulder_press import ShoulderPress
from .squat import Squat

EXERCISES: dict[str, type[Exercise]] = {
    cls.key: cls for cls in (PushUp, PullUp, Squat, BicepCurl, ShoulderPress)
}


def create(key: str, config: dict) -> Exercise:
    """Instantiate an exercise from the loaded YAML config."""
    if key not in EXERCISES:
        raise KeyError(f"Unknown exercise '{key}'. Choose from: {', '.join(EXERCISES)}")
    return EXERCISES[key](config[key], config.get("general", {}))


__all__ = ["EXERCISES", "Exercise", "FaultSpec", "FrameMetrics", "RepResult", "RepWindow", "create"]
