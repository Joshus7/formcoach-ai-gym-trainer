"""Reference ("expected") rep counts from the angle signal with scipy.signal.find_peaks.

This is deliberately a different method from the app's state machine: the whole
clip is available, so the signal is smoothed offline and every turnaround with
enough prominence is a rep. tools/evaluate.py compares the engine against it.

    python tools/reference_counts.py --exercise push_up          # print counts
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks, savgol_filter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from formcoach.core import exercises  # noqa: E402
from formcoach.core.config import load_config  # noqa: E402
from formcoach.core.landmark_io import LandmarkSequence, load_npz  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LANDMARKS = ROOT / "data" / "landmarks"

# Minimum prominence of a turnaround (signal units) and minimum time between reps.
PEAK_PARAMS = {
    "push_up": dict(prominence=20, distance_s=0.8),
    "squat": dict(prominence=35, distance_s=0.9),
    "bicep_curl": dict(prominence=50, distance_s=0.8),
    "shoulder_press": dict(prominence=0.45, distance_s=0.8),
    "pull_up": dict(prominence=35, distance_s=1.0),
}


def signal_of(exercise_key: str, seq: LandmarkSequence, cfg: dict, min_vis: float = 0.5) -> np.ndarray:
    """The exercise's rep signal per frame (NaN where the joints are not visible)."""
    ex = exercises.create(exercise_key, cfg)
    valid = ~np.isnan(seq.landmarks[:, 0, 0])
    if not valid.any():
        return np.full(len(seq), np.nan)
    # One side for the whole clip: the one with the best average visibility.
    mean_lms = np.nanmean(seq.landmarks[valid], axis=0)
    side = ex.choose_side(mean_lms)
    sig = np.full(len(seq), np.nan)
    for i, (lms, t) in enumerate(seq.frames()):
        if lms is not None and ex.visibility_ok(lms, side, min_vis):
            sig[i] = ex.measure(lms, side, t).signal
    return sig


def count_reps(exercise_key: str, sig: np.ndarray, fps: float, direction: str = "decreasing"
               ) -> tuple[int, np.ndarray]:
    """Number of reps and the frame index of each turnaround."""
    p = PEAK_PARAMS[exercise_key]
    ok = ~np.isnan(sig)
    if ok.sum() < 10:
        return 0, np.array([], int)
    # Fill short gaps by interpolation, then smooth.
    idx = np.arange(len(sig))
    filled = np.interp(idx, idx[ok], sig[ok])
    win = max(5, int(fps * 0.4) | 1)
    smooth = savgol_filter(filled, win, 2) if len(filled) > win else filled
    x = -smooth if direction == "decreasing" else smooth  # turnarounds become maxima
    peaks, _ = find_peaks(x, prominence=p["prominence"], distance=max(1, int(p["distance_s"] * fps)))
    return len(peaks), peaks


def direction(exercise_key: str, cfg: dict) -> str:
    return cfg[exercise_key]["counter"].get("direction", "decreasing")


def clips(exercise_key: str) -> list[Path]:
    return sorted(LANDMARKS.glob(f"*/{exercise_key}/*/*.npz"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exercise", choices=sorted(PEAK_PARAMS), action="append")
    args = ap.parse_args()
    cfg = load_config()
    result = {}
    for ex in args.exercise or sorted(PEAK_PARAMS):
        for path in clips(ex):
            seq = load_npz(path)
            n, _ = count_reps(ex, signal_of(ex, seq, cfg), seq.fps, direction(ex, cfg))
            result[f"{ex}/{path.parent.name}/{path.stem}"] = n
            print(f"{ex:15s} {path.parent.name:5s} {path.stem:45s} {n:3d}")
    out = ROOT / "data" / "reference_counts.json"
    out.write_text(json.dumps(result, indent=1))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
