"""Cut short landmark sequences from the dataset into tests/fixtures (small enough to commit).

For each exercise, up to N good and N bad clips are taken (evenly spread over the
subjects), cut to at most --max-frames frames, ending at a moment the person is in the
start position so no rep is cut in half. The expected rep count of each cut clip comes
from the find_peaks reference (tools/reference_counts.py) and is stored in
tests/fixtures/expected_counts.json.

    python tools/make_fixtures.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from formcoach.core.config import load_config  # noqa: E402
from formcoach.core.exercises import EXERCISES  # noqa: E402
from formcoach.core.landmark_io import load_npz, save_fixture  # noqa: E402
from reference_counts import clips, count_reps, direction, signal_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def cut_point(sig: np.ndarray, max_frames: int, start: float, decreasing: bool) -> int:
    """Last frame <= max_frames where the signal is in the start position."""
    end = min(len(sig), max_frames)
    for i in range(end - 1, end // 2, -1):
        v = sig[i]
        if not np.isnan(v) and (v >= start if decreasing else v <= start):
            return i + 1
    return end


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-label", type=int, default=2, help="clips per good/bad label per exercise")
    ap.add_argument("--max-frames", type=int, default=240)
    args = ap.parse_args()
    cfg = load_config()
    FIXTURES.mkdir(parents=True, exist_ok=True)
    expected_path = FIXTURES / "expected_counts.json"
    expected = json.loads(expected_path.read_text()) if expected_path.exists() else {}
    for ex in EXERCISES:
        paths = clips(ex)
        if not paths:
            print(f"{ex}: no cached landmarks, skipped")
            continue
        # Drop this exercise's old fixtures; they are regenerated below.
        for old in FIXTURES.glob(f"{ex}__*.json"):
            old.unlink()
        expected = {k: v for k, v in expected.items() if not k.startswith(f"{ex}__")}
        dirn = direction(ex, cfg)
        start = cfg[ex]["counter"]["start"]
        for label in ("good", "bad", "unlabelled"):
            group = [p for p in paths if p.parent.name == label]
            if not group:
                continue
            picks = [group[int(i)] for i in np.linspace(0, len(group) - 1, min(args.per_label, len(group)))]
            for p in picks:
                seq = load_npz(p)
                sig = signal_of(ex, seq, cfg)
                cut = seq.slice(0, cut_point(sig, args.max_frames, start, dirn == "decreasing"))
                n, _ = count_reps(ex, signal_of(ex, cut, cfg), cut.fps, dirn)
                name = f"{ex}__{label}__{p.stem}"
                save_fixture(cut, FIXTURES / f"{name}.json", {"exercise": ex, "label": label, "source": p.stem})
                expected[name] = {"exercise": ex, "label": label, "reps": n}
                size = (FIXTURES / f"{name}.json").stat().st_size / 1024
                print(f"{name}: {len(cut)} frames, {n} reps, {size:.0f} KB")
    expected_path.write_text(json.dumps(dict(sorted(expected.items())), indent=1))
    print(f"wrote {expected_path}")


if __name__ == "__main__":
    main()
