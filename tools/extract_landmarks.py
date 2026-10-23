"""Run PoseLandmarker over every downloaded dataset video and cache the landmarks.

Output: data/landmarks/<source>/<exercise>/<quality>/<clip>.npz with
    landmarks  (T, 33, 4) float32 pixels + visibility (NaN rows = no person)
    timestamps (T,) int64 milliseconds
    fps, width, height
Clips already extracted are skipped, so the script is re-runnable.

    python tools/extract_landmarks.py
    python tools/extract_landmarks.py --exercise push_up --limit 5
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from formcoach.core.pose import PoseEstimator  # noqa: E402
from formcoach.core.video_source import DATA_RAW, DATASET_DIRS, VIDEO_EXT, VideoSource  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "landmarks"


def clip_quality(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    if "good" in parts or "_good_" in path.name:
        return "good"
    if "bad" in parts or "_bad_" in path.name:
        return "bad"
    return "unlabelled"


def output_path(exercise: str, clip: Path) -> Path:
    source = clip.relative_to(DATA_RAW).parts[0]
    return OUT / source / exercise / clip_quality(clip) / (clip.stem + ".npz")


def extract(clip: Path) -> dict:
    estimator = PoseEstimator()  # fresh tracker state per clip
    lms, ts = [], []
    with VideoSource(clip) as vs:
        fps, w, h = vs.fps, None, None
        for frame in vs:
            h, w = frame.image.shape[:2]
            res = estimator.process(frame.image, frame.timestamp_ms)
            lms.append(res.landmarks if res is not None else np.full((33, 4), np.nan, np.float32))
            ts.append(frame.timestamp_ms)
    estimator.close()
    return dict(landmarks=np.asarray(lms, np.float32), timestamps=np.asarray(ts, np.int64),
                fps=np.float32(fps), width=np.int32(w or 0), height=np.int32(h or 0))


def all_clips(exercises: list[str]) -> list[tuple[str, Path]]:
    out = []
    for ex in exercises:
        for rel in DATASET_DIRS[ex]:
            d = DATA_RAW / rel
            if d.is_dir():
                out += [(ex, p) for p in sorted(d.iterdir()) if p.suffix.lower() in VIDEO_EXT]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exercise", choices=sorted(DATASET_DIRS), action="append")
    ap.add_argument("--limit", type=int, default=0, help="max clips per exercise")
    args = ap.parse_args()
    exercises = args.exercise or sorted(DATASET_DIRS)
    clips = all_clips(exercises)
    if args.limit:
        per: dict[str, int] = {}
        kept = []
        for ex, p in clips:
            if per.get(ex, 0) < args.limit:
                kept.append((ex, p))
                per[ex] = per.get(ex, 0) + 1
        clips = kept
    if not clips:
        print("No clips found. Run: python scripts/download_data.py")
        return
    done = skipped = 0
    for i, (ex, clip) in enumerate(clips, 1):
        out = output_path(ex, clip)
        if out.exists():
            skipped += 1
            continue
        t0 = time.perf_counter()
        data = extract(clip)
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(out, **data)
        n = len(data["timestamps"])
        found = int((~np.isnan(data["landmarks"][:, 0, 0])).sum())
        print(f"[{i}/{len(clips)}] {ex}: {clip.name} -> {n} frames, pose in {found} "
              f"({time.perf_counter() - t0:.1f}s)", flush=True)
        done += 1
    print(f"Done: {done} extracted, {skipped} already present -> {OUT}")


if __name__ == "__main__":
    main()
