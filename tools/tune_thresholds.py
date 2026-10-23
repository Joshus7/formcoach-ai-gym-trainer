"""Tune config/exercises.yaml from the dataset and write reports/tuning.md.

1. Counting thresholds - from the good-form clips' reference signal (find_peaks):
   start = P10 of the rep tops minus 20 % of the range, turn = P90 of the turnarounds
   plus 20 % of the range (mirrored for "increasing" signals). The new values are kept
   only if they count at least as accurately as the current ones.
2. Form thresholds - every rep of every clip is run through the engine and the metric
   behind each threshold (Exercise.tunable) is collected. For a threshold the candidates
   are the P75..P99 values of the good-form reps; the one that keeps >= 85 % of good reps
   passing while flagging the most bad-form reps is chosen.

Tuning uses the subjects of the train split only; the report gives accuracy on the
train split and on held-out subjects (--holdout-from, default subject 18 and up).

    python tools/tune_thresholds.py              # tune, write config + report
    python tools/tune_thresholds.py --dry-run    # report only
"""
from __future__ import annotations

import argparse
import copy
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from formcoach.core import exercises  # noqa: E402
from formcoach.core.config import load_config, save_config  # noqa: E402
from formcoach.core.engine import WorkoutEngine  # noqa: E402
from formcoach.core.landmark_io import load_npz  # noqa: E402
from evaluate import evaluate_clip, summarise  # noqa: E402
from reference_counts import clips, count_reps, direction, signal_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "tuning.md"
MIN_GOOD_PASS = 0.85


def subject_id(path: Path) -> int | None:
    m = re.search(r"subject_(\d+)", path.stem)
    return int(m.group(1)) if m else None


def split(paths: list[Path], holdout_from: int) -> tuple[list[Path], list[Path]]:
    train = [p for p in paths if (subject_id(p) or 0) < holdout_from]
    test = [p for p in paths if (subject_id(p) or 0) >= holdout_from]
    if not train or not test:  # e.g. unlabelled Kaggle clips without subject ids: alternate
        train, test = paths[::2], paths[1::2]
    return train, test


# ---------------------------------------------------------------------------- counting
def suggest_counter(ex: str, paths: list[Path], cfg: dict) -> dict | None:
    tops, bottoms = [], []
    dirn = direction(ex, cfg)
    for p in paths:
        if p.parent.name == "bad":
            continue
        seq = load_npz(p)
        sig = signal_of(ex, seq, cfg)
        _, peaks = count_reps(ex, sig, seq.fps, dirn)
        if len(peaks) < 2:
            continue
        x = sig if dirn == "decreasing" else -sig
        bottoms += [np.nanmin(x[max(0, i - 2):i + 3]) for i in peaks]
        tops += [np.nanmax(x[a:b]) for a, b in zip(peaks[:-1], peaks[1:])]
    if len(tops) < 5:
        return None
    tops, bottoms = np.array(tops), np.array(bottoms)
    span = np.median(tops) - np.median(bottoms)
    start = np.percentile(tops, 10) - 0.2 * span
    turn = np.percentile(bottoms, 90) + 0.2 * span
    if turn >= start - 0.1 * span:
        return None
    sign = 1 if dirn == "decreasing" else -1
    digits = 0 if span > 5 else 2
    return {"start": round(float(sign * start), digits), "turn": round(float(sign * turn), digits)}


def count_mae(ex: str, paths: list[Path], cfg: dict) -> float:
    errs = [abs(r.attempts - r.expected) for r in (evaluate_clip(ex, p, cfg) for p in paths)]
    return float(np.mean(errs)) if errs else 0.0


# ---------------------------------------------------------------------------- form
def collect_metrics(ex: str, paths: list[Path], cfg: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {"good": [], "bad": []}
    for p in paths:
        label = p.parent.name
        if label not in out:
            continue
        eng = WorkoutEngine(ex, cfg, countdown_s=0, keep_windows=True)
        for lms, t in load_npz(p).frames():
            eng.process(lms, t)
        for w in eng.windows:
            if not w.event.partial:
                out[label].append(eng.exercise.rep_metrics(w))
    return out


def choose_threshold(kind: str, good: np.ndarray, bad: np.ndarray) -> tuple[float, float, float] | None:
    """Return (threshold, good pass rate, bad flag rate)."""
    good, bad = good[~np.isnan(good)], bad[~np.isnan(bad)]
    if len(good) < 5:
        return None
    best = None
    for q in range(75, 100):
        t = np.percentile(good, q if kind == "max" else 100 - q)
        passing = np.mean(good <= t) if kind == "max" else np.mean(good >= t)
        flagged = (np.mean(bad > t) if kind == "max" else np.mean(bad < t)) if len(bad) else 0.0
        if passing < MIN_GOOD_PASS:
            continue
        score = passing + flagged
        if best is None or score > best[0] + 1e-9:
            best = (score, float(t), float(passing), float(flagged))
    return best[1:] if best else None


def tune_form(ex: str, train: list[Path], cfg: dict) -> list[tuple]:
    cls = exercises.EXERCISES[ex]
    metrics = collect_metrics(ex, train, cfg)
    rows = []
    for key, (kind, name) in cls.tunable.items():
        g = np.array([m.get(name, np.nan) for m in metrics["good"]], float)
        b = np.array([m.get(name, np.nan) for m in metrics["bad"]], float)
        res = choose_threshold(kind, g, b)
        old = cfg[ex]["thresholds"][key]
        if res is None:
            rows.append((key, kind, old, old, None, None))
            continue
        t, passing, flagged = res
        digits = 0 if abs(t) >= 5 else 2
        new = round(t, digits)
        cfg[ex]["thresholds"][key] = new
        rows.append((key, kind, old, new, passing, flagged))
    return rows


# ---------------------------------------------------------------------------- report
def fmt_summary(s: dict) -> str:
    acc = f"{s['rep_count_accuracy']:.1%}" if s["rep_count_accuracy"] is not None else "-"
    form = f"{s['form_accuracy']:.0%}" if s["form_accuracy"] is not None else "-"
    return (f"| {s['clips']} | {s['count_exact']} | {s['count_within_1']} | {s['count_mae']:.2f} | {acc} | "
            f"{s['good_correct']}/{s['good_total']} | {s['bad_correct']}/{s['bad_total']} | {form} |")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exercise", choices=sorted(exercises.EXERCISES), action="append")
    ap.add_argument("--holdout-from", type=int, default=18)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    original = copy.deepcopy(cfg)
    lines = [f"# Threshold tuning report\n", f"Generated by `tools/tune_thresholds.py` on {date.today()}.\n",
             f"Train subjects: < {args.holdout_from}; held-out test subjects: >= {args.holdout_from}. "
             "Expected rep counts come from `scipy.signal.find_peaks` on the smoothed signal "
             "(`tools/reference_counts.py`); good/bad labels come from the dataset filenames. "
             f"A clip is classified *bad* when at least half of its reps have a form fault.\n"]
    header = ("| split | clips | exact count | within +-1 | MAE | rep-count acc. | good clips ok | bad clips ok "
              "| form acc. |\n|---|---|---|---|---|---|---|---|---|")
    for ex in args.exercise or list(exercises.EXERCISES):
        paths = clips(ex)
        if not paths:
            lines.append(f"\n## {exercises.EXERCISES[ex].name}\n\nNo dataset clips available - thresholds left "
                         "at their defaults.\n")
            print(f"{ex}: no data, skipped")
            continue
        train, test = split(paths, args.holdout_from)
        print(f"{ex}: {len(train)} train / {len(test)} test clips")
        before = {name: summarise([evaluate_clip(ex, p, cfg) for p in part]) for name, part in
                  (("train", train), ("test", test))}

        counter_note = "kept (suggestion not better)"
        sugg = suggest_counter(ex, train, cfg)
        if sugg:
            trial = copy.deepcopy(cfg)
            trial[ex]["counter"].update(sugg)
            try:
                old_mae, new_mae = count_mae(ex, train, cfg), count_mae(ex, train, trial)
            except ValueError:
                old_mae, new_mae = 0, 1
            if new_mae < old_mae:  # ties keep the hand-set values
                cfg[ex]["counter"].update(sugg)
                counter_note = f"updated (train MAE {old_mae:.2f} -> {new_mae:.2f})"
            else:
                counter_note = f"kept (suggested {sugg} had train MAE {new_mae:.2f} vs {old_mae:.2f})"
        rows = tune_form(ex, train, cfg)
        after = {name: summarise([evaluate_clip(ex, p, cfg) for p in part]) for name, part in
                 (("train", train), ("test", test))}

        lines.append(f"\n## {exercises.EXERCISES[ex].name}\n")
        c = cfg[ex]["counter"]
        lines.append(f"Counter: start={c['start']}, turn={c['turn']} - {counter_note}.\n")
        lines.append("| threshold | rule | before | after | good reps passing | bad reps flagged |\n|---|---|---|---|---|---|")
        for key, kind, old, new, passing, flagged in rows:
            rule = "fault if above" if kind == "max" else "fault if below"
            pp = f"{passing:.0%}" if passing is not None else "-"
            ff = f"{flagged:.0%}" if flagged is not None else "-"
            lines.append(f"| `{key}` | {rule} | {old} | {new} | {pp} | {ff} |")
        lines.append("\n" + header)
        for name in ("train", "test"):
            lines.append(f"| {name} (before) " + fmt_summary(before[name]))
            lines.append(f"| {name} (after) " + fmt_summary(after[name]))
        print(f"  test after: count acc {after['test']['rep_count_accuracy']}, form acc {after['test']['form_accuracy']}")

    lines.append("\n_Notes_: bad-form clips contain a mix of fault types (and some reps in them are fine), so "
                 "\"bad reps flagged\" for a single threshold is naturally low. Thresholds are rounded.\n")
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")
    print(f"wrote {REPORT}")
    if not args.dry_run and cfg != original:
        save_config(cfg)
        print("updated config/exercises.yaml")


if __name__ == "__main__":
    main()
