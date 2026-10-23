"""Synthetic front-view tests for pull-ups (no labelled dataset by default) and shoulder press."""
import math

import numpy as np

from formcoach.core import landmarks as L
from formcoach.core.config import load_config
from formcoach.core.engine import WorkoutEngine

FPS = 30
CFG = load_config()


def set_pt(lms, idx, x, y, vis=0.98):
    lms[idx] = (x, y, 0, vis)


def pull_up_pose(lift: float, chin_over: bool = True, hip_shift: float = 0.0) -> np.ndarray:
    """lift 0 = dead hang, 1 = top. Bar (wrists) fixed at y=100."""
    lms = np.zeros((33, 4), np.float32)
    bar_y, arm = 100.0, 140.0
    top_gap = 10.0 if chin_over else 70.0         # shoulder below bar at the top
    sh_y = bar_y + arm - lift * (arm - top_gap)
    for side, sx, wx in (("left", 260, 230), ("right", 340, 370)):
        S = L.SIDE[side]
        set_pt(lms, S["wrist"], wx, bar_y)
        set_pt(lms, S["shoulder"], sx, sh_y)
        # Elbow bows outwards as the arm bends.
        bend = math.sin(lift * math.pi / 2) * 55
        ex = (sx + wx) / 2 + (-bend if side == "left" else bend)
        set_pt(lms, S["elbow"], ex, (sh_y + bar_y) / 2)
        set_pt(lms, S["hip"], sx + 5 + hip_shift, sh_y + 150)
        set_pt(lms, S["knee"], sx + 5 + hip_shift, sh_y + 230)
        set_pt(lms, S["ankle"], sx + 5 + hip_shift, sh_y + 310)
    nose_y = sh_y - (60 if chin_over else 40)
    set_pt(lms, L.NOSE, 300, nose_y)
    return lms


def wave(n, rep_s=2.0, hold_s=1.0):
    hold = np.zeros(int(hold_s * FPS))
    t = np.arange(int(rep_s * FPS)) / (rep_s * FPS)
    one = 0.5 - 0.5 * np.cos(2 * np.pi * t)
    return np.concatenate([hold] + [np.concatenate([one, np.zeros(int(0.5 * FPS))])] * n)


def run(exercise, poses):
    eng = WorkoutEngine(exercise, CFG, countdown_s=0)
    for i, p in enumerate(poses):
        eng.process(p, i / FPS)
    return eng.finish()


def test_pull_ups_counted_and_clean():
    s = run("pull_up", [pull_up_pose(x) for x in wave(4)])
    assert s.total_attempts == 4
    assert s.good_reps == 4, [r.faults for r in s.reps]


def test_pull_up_without_chin_over_bar_is_no_rep():
    s = run("pull_up", [pull_up_pose(x * 0.75, chin_over=False) for x in wave(3)])
    assert s.total_attempts == 3
    assert s.no_reps == 3
    assert all("chin_not_over" in r.faults for r in s.reps)


def test_pull_up_kipping_detected():
    w = wave(3)
    poses = [pull_up_pose(x, hip_shift=80 * math.sin(i / FPS * 2 * math.pi)) for i, x in enumerate(w)]
    s = run("pull_up", poses)
    assert s.total_attempts == 3
    assert all("kipping" in r.faults for r in s.reps)


def press_pose(lift: float, uneven: float = 0.0) -> np.ndarray:
    """lift 0 = dumbbells at shoulder level, 1 = arms locked out overhead."""
    lms = np.zeros((33, 4), np.float32)
    sh_y = 300.0
    for side, sx in (("left", 250), ("right", 350)):
        S = L.SIDE[side]
        l = lift * (1 - uneven) if side == "right" else lift
        set_pt(lms, S["shoulder"], sx, sh_y)
        set_pt(lms, S["hip"], sx + (10 if side == "left" else -10), sh_y + 180)
        out = -1 if side == "left" else 1
        # Bottom: elbow out to the side and down, wrist above elbow. Top: straight arm.
        elbow = (sx + out * 70 * (1 - l), sh_y - 80 * l + 20 * (1 - l))
        wrist = (sx + out * 70 * (1 - l), sh_y - 160 * l - 40 * (1 - l))
        set_pt(lms, S["elbow"], *elbow)
        set_pt(lms, S["wrist"], *wrist)
    set_pt(lms, L.NOSE, 300, sh_y - 60)
    return lms


def test_shoulder_press_counted():
    s = run("shoulder_press", [press_pose(x) for x in wave(5)])
    assert s.total_attempts == 5
    assert s.good_reps == 5, [r.faults for r in s.reps]


def test_shoulder_press_uneven_flagged():
    s = run("shoulder_press", [press_pose(x, uneven=0.35) for x in wave(3)])
    assert s.total_attempts == 3
    assert all("uneven" in r.faults for r in s.reps)
