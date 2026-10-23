"""Evaluate the full FormCoach engine on the cached dataset landmarks.

For every clip of every exercise:
  * rep-count accuracy - engine attempts (reps + no-reps) vs. the find_peaks
    reference count (tools/reference_counts.py); a clip is "exact" when equal,
    and the mean absolute error is reported too;
  * form accuracy - a clip is predicted "bad" when at least ``bad_share`` of its
    reps have a fault; compared with the good/bad label from the dataset filename.

    python tools/evaluate.py
    python tools/evaluate.py --exercise push_up --verbose
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from formcoach.core.config import load_config  # noqa: E402
from formcoach.core.engine import WorkoutEngine  # noqa: E402
from formcoach.core.exercises import EXERCISES  # noqa: E402
from formcoach.core.landmark_io import LandmarkSequence, load_npz  # noqa: E402
from reference_counts import clips, count_reps, direction, signal_of  # noqa: E402

BAD_SHARE = 0.5


@dataclass
class ClipResult:
    name: str
    label: str
    expected: int
    attempts: int
    good_reps: int
    no_reps: int
    faulty_share: float
    faults: dict = field(default_factory=dict)

    @property
    def predicted(self) -> str:
        return "bad" if self.faulty_share >= BAD_SHARE else "good"


def run_engine(exercise: str, seq: LandmarkSequence, cfg: dict):
    eng = WorkoutEngine(exercise, cfg, countdown_s=0)
    for lms, t in seq.frames():
        eng.process(lms, t)
    return eng.finish()


def evaluate_clip(exercise: str, path: Path, cfg: dict) -> ClipResult:
    seq = load_npz(path)
    expected, _ = count_reps(exercise, signal_of(exercise, seq, cfg), seq.fps, direction(exercise, cfg))
    s = run_engine(exercise, seq, cfg)
    faulty = sum(bool(r.faults) for r in s.reps)
    return ClipResult(path.stem, path.parent.name, expected, s.total_attempts, s.good_reps, s.no_reps,
                      faulty / s.total_attempts if s.total_attempts else 0.0, dict(s.fault_counts))


def summarise(results: list[ClipResult]) -> dict:
    n = len(results)
    labelled = [r for r in results if r.label in ("good", "bad")]
    exact = sum(r.attempts == r.expected for r in results)
    within1 = sum(abs(r.attempts - r.expected) <= 1 for r in results)
    mae = sum(abs(r.attempts - r.expected) for r in results) / n if n else 0.0
    total_exp = sum(r.expected for r in results)
    total_err = sum(abs(r.attempts - r.expected) for r in results)
    form_ok = sum(r.predicted == r.label for r in labelled)
    by_label = {lab: [r for r in labelled if r.label == lab] for lab in ("good", "bad")}
    return {
        "clips": n,
        "count_exact": exact, "count_within_1": within1, "count_mae": round(mae, 2),
        "rep_count_accuracy": round(1 - total_err / total_exp, 3) if total_exp else None,
        "form_clips": len(labelled), "form_correct": form_ok,
        "form_accuracy": round(form_ok / len(labelled), 3) if labelled else None,
        "good_correct": sum(r.predicted == "good" for r in by_label["good"]), "good_total": len(by_label["good"]),
        "bad_correct": sum(r.predicted == "bad" for r in by_label["bad"]), "bad_total": len(by_label["bad"]),
    }


def evaluate(exercises: list[str], cfg: dict, verbose: bool = False) -> dict:
    report = {}
    for ex in exercises:
        paths = clips(ex)
        if not paths:
            continue
        results = [evaluate_clip(ex, p, cfg) for p in paths]
        if verbose:
            for r in results:
                print(f"  {ex:14s} {r.label:4s} {r.name:42s} expected={r.expected:3d} got={r.attempts:3d} "
                      f"(good {r.good_reps}, no-rep {r.no_reps}) faulty={r.faulty_share:.0%} -> {r.predicted} "
                      f"{r.faults}")
        report[ex] = {"summary": summarise(results), "clips": [r.__dict__ for r in results]}
    return report


def print_table(report: dict) -> None:
    print(f"{'exercise':15s} {'clips':>5s} {'exact':>6s} {'+-1':>5s} {'MAE':>5s} {'rep acc':>8s} "
          f"{'form acc':>9s} {'good ok':>8s} {'bad ok':>7s}")
    for ex, r in report.items():
        s = r["summary"]
        fa = f"{s['form_accuracy']:.0%}" if s["form_accuracy"] is not None else "-"
        ra = f"{s['rep_count_accuracy']:.1%}" if s["rep_count_accuracy"] is not None else "-"
        print(f"{ex:15s} {s['clips']:5d} {s['count_exact']:6d} {s['count_within_1']:5d} {s['count_mae']:5.2f} "
              f"{ra:>8s} {fa:>9s} {s['good_correct']:>3d}/{s['good_total']:<4d} {s['bad_correct']:>3d}/{s['bad_total']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exercise", choices=sorted(EXERCISES), action="append")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json", type=Path, help="also write the full report here")
    args = ap.parse_args()
    report = evaluate(args.exercise or list(EXERCISES), load_config(), args.verbose)
    if not report:
        print("No cached landmarks. Run scripts/download_data.py and tools/extract_landmarks.py first.")
        return
    print_table(report)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
