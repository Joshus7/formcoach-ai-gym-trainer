"""Run the full FormCoach engine over one clip and print every rep.

    python tools/run_clip.py --exercise push_up path/to/clip.mp4        # video (runs pose)
    python tools/run_clip.py --exercise push_up data/landmarks/.../x.npz # cached landmarks
    python tools/run_clip.py --exercise push_up --dataset                # all cached push-up clips
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from formcoach.core.config import load_config  # noqa: E402
from formcoach.core.engine import WorkoutEngine  # noqa: E402
from formcoach.core.landmark_io import load_npz  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def frames_from(path: Path):
    if path.suffix == ".npz":
        yield from load_npz(path).frames()
        return
    from formcoach.core.pose import PoseEstimator
    from formcoach.core.video_source import VideoSource
    with PoseEstimator() as est, VideoSource(path) as vs:
        for f in vs:
            r = est.process(f.image, f.timestamp_ms)
            yield (r.landmarks if r else None), f.timestamp_ms / 1000


def run(exercise: str, path: Path, cfg: dict, verbose: bool = True):
    eng = WorkoutEngine(exercise, cfg, countdown_s=0)
    for lms, t in frames_from(path):
        out = eng.process(lms, t)
        if out.new_rep and verbose:
            r = out.new_rep
            tag = "REP   " if r.valid else "NO REP"
            print(f"  {tag} #{r.index:2d} t={r.end_t:6.1f}s score={r.score:3d} "
                  f"faults={','.join(r.faults) or '-'} extreme={r.metrics['extreme']:.1f} "
                  f"start={r.metrics['start_peak']:.1f}")
    return eng.finish()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exercise", required=True)
    ap.add_argument("clips", nargs="*", type=Path)
    ap.add_argument("--dataset", action="store_true", help="all cached clips for the exercise")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    clips = list(args.clips)
    if args.dataset:
        clips += sorted((ROOT / "data" / "landmarks").glob(f"*/{args.exercise}/*/*.npz"))
    for c in clips:
        print(f"{c.name}")
        s = run(args.exercise, c, cfg, verbose=not args.quiet)
        print(f"  -> {s.good_reps} reps, {s.no_reps} no-reps, avg score {s.avg_score:.0f}")


if __name__ == "__main__":
    main()
