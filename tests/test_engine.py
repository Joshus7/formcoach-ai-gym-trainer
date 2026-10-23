"""Engine behaviour on synthetic push-up landmarks: countdown, visibility, sets, scoring."""
import math

import numpy as np

from formcoach.core import landmarks as L
from formcoach.core.config import load_config
from formcoach.core.engine import State, WorkoutEngine
from formcoach.core.feedback import FeedbackManager
from formcoach.core import exercises

FPS = 30
CFG = load_config()


def plank(depth: float, hips: float = 0.0) -> np.ndarray:
    """Side-view push-up pose facing left. depth 0 = arms straight, 1 = chest at the floor."""
    lms = np.zeros((33, 4), np.float32)
    lms[:, 3] = 0.2  # far-side / face points: low visibility
    floor = 400.0
    arm = 120.0
    sh_y = floor - arm * (1 - 0.6 * depth)
    elbow_bend = 0.6 * depth
    pts = {
        "shoulder": (200, sh_y), "wrist": (200, floor),
        "elbow": (200 + 60 * math.sin(elbow_bend * 2.2), (sh_y + floor) / 2),
        "hip": (400, sh_y + 40 + hips), "knee": (500, sh_y + 60), "ankle": (600, sh_y + 80),
        "heel": (610, sh_y + 75), "foot": (615, sh_y + 90), "ear": (170, sh_y - 20),
    }
    for j, (x, y) in pts.items():
        lms[L.SIDE["left"][j]] = (x, y, 0, 0.99)
    # Right-side torso points (needed for torso length), lower visibility.
    lms[L.RIGHT_SHOULDER] = (205, sh_y, 0, 0.5)
    lms[L.RIGHT_HIP] = (405, sh_y + 40 + hips, 0, 0.5)
    lms[L.NOSE] = (160, sh_y, 0, 0.9)
    return lms


def depth_wave(n_reps, rep_s=1.6, hold_s=1.0, depth=1.0):
    hold = np.zeros(int(hold_s * FPS))
    t = np.arange(int(rep_s * FPS)) / (rep_s * FPS)
    one = depth * (0.5 - 0.5 * np.cos(2 * np.pi * t))
    return np.concatenate([hold] + [np.concatenate([one, np.zeros(int(0.4 * FPS))])] * n_reps)


def feed(engine, depths, t0=0.0, hips=0.0):
    outs = []
    for i, d in enumerate(depths):
        outs.append(engine.process(plank(d, hips), t0 + i / FPS))
    return outs


def test_counts_synthetic_push_ups():
    eng = WorkoutEngine("push_up", CFG, countdown_s=0)
    feed(eng, depth_wave(5))
    s = eng.finish()
    assert s.total_attempts == 5
    assert s.good_reps == 5


def test_countdown_blocks_counting_then_starts():
    eng = WorkoutEngine("push_up", CFG, countdown_s=3)
    outs = feed(eng, np.zeros(2 * FPS))
    assert outs[0].state == State.COUNTDOWN
    assert outs[-1].countdown > 0
    outs = feed(eng, np.concatenate([np.zeros(2 * FPS), depth_wave(3)]), t0=2.0)
    assert any(o.state == State.ACTIVE for o in outs)
    assert eng.session.total_attempts == 3


def test_no_pose_and_hidden_joints_pause_with_message():
    eng = WorkoutEngine("push_up", CFG, countdown_s=0)
    out = eng.process(None, 0.0)
    assert out.state == State.NO_POSE
    assert "visible" in out.message.text
    hidden = plank(0)
    hidden[L.LEFT_WRIST, 3] = 0.1
    hidden[L.RIGHT_WRIST, 3] = 0.1
    out = eng.process(hidden, 1.0)
    assert out.state == State.NOT_VISIBLE


def test_frontal_view_asks_to_turn_sideways():
    eng = WorkoutEngine("push_up", CFG, countdown_s=0)
    lms = np.zeros((33, 4), np.float32)
    lms[:, 3] = 0.95
    lms[L.LEFT_SHOULDER] = (250, 200, 0, 0.95)
    lms[L.RIGHT_SHOULDER] = (350, 200, 0, 0.95)
    lms[L.LEFT_HIP] = (270, 350, 0, 0.95)
    lms[L.RIGHT_HIP] = (330, 350, 0, 0.95)
    for idx in (L.LEFT_WRIST, L.RIGHT_WRIST, L.LEFT_ELBOW, L.RIGHT_ELBOW, L.LEFT_ANKLE, L.RIGHT_ANKLE):
        lms[idx, 3] = 0.3
    out = eng.process(lms, 0.0)
    assert out.message.text == "Turn sideways to the camera"


def test_short_dropout_does_not_lose_the_rep():
    eng = WorkoutEngine("push_up", CFG, countdown_s=0)
    depths = depth_wave(2)
    for i, d in enumerate(depths):
        lms = None if i in (50, 51, 52) else plank(d)  # 0.1 s gap mid-rep
        eng.process(lms, i / FPS)
    assert eng.session.total_attempts == 2


def test_long_loss_resets_rep_in_progress():
    eng = WorkoutEngine("push_up", CFG, countdown_s=0)
    feed(eng, np.zeros(60))
    feed(eng, np.linspace(0, 1, 20), t0=2.0)       # half-way down
    for i in range(60):                            # 2 s without a person
        eng.process(None, 2.7 + i / FPS)
    feed(eng, np.linspace(1, 0, 20), t0=5.0)       # comes back up
    assert eng.session.total_attempts == 0


def test_shallow_reps_are_no_reps():
    eng = WorkoutEngine("push_up", CFG, countdown_s=0)
    feed(eng, depth_wave(3, depth=0.4))
    s = eng.finish()
    assert s.no_reps == 3 and s.good_reps == 0
    assert all("not_deep" in r.faults for r in s.reps)


def test_sagging_hips_are_flagged_and_marked_red():
    eng = WorkoutEngine("push_up", CFG, countdown_s=0)
    outs = feed(eng, depth_wave(2), hips=60)
    s = eng.finish()
    assert all("hips_out_of_line" in r.faults for r in s.reps)
    assert any(L.LEFT_HIP in o.bad_joints for o in outs)
    assert any(o.message and o.message.text == "Keep your hips in line" for o in outs)


def test_target_reps_and_sets():
    eng = WorkoutEngine("push_up", CFG, countdown_s=0, target_reps=2, target_sets=2)
    outs = feed(eng, depth_wave(5))
    assert sum(o.set_completed for o in outs) == 2
    assert eng.state == State.FINISHED
    assert eng.session.sets_completed == 2
    assert eng.session.good_reps == 4   # the 5th rep happens after the workout finished


def test_session_summary():
    eng = WorkoutEngine("push_up", CFG, countdown_s=0)
    feed(eng, np.concatenate([depth_wave(2), depth_wave(2, depth=0.4)]))
    s = eng.finish().summary()
    assert s["attempts"] == 4 and s["total_reps"] == 2 and s["no_reps"] == 2
    assert s["most_common_fault"] == "not_deep"
    assert s["worst_rep"] in (3, 4) and s["best_rep"] in (1, 2)
    assert 0 < s["avg_score"] < 100


def test_voice_rate_limit():
    fm = FeedbackManager(exercises.create("push_up", CFG), live_fault_frames=1, repeat_s=4)
    assert fm.should_speak("Go lower", 0.0)
    assert not fm.should_speak("Go lower", 3.9)
    assert fm.should_speak("Keep your hips in line", 3.9)
    assert fm.should_speak("Go lower", 4.1)


def test_all_exercises_construct_from_config():
    for key in exercises.EXERCISES:
        ex = exercises.create(key, CFG)
        ex.make_counter()
        assert ex.name and ex.tip and ex.view in ("side", "front")
        for code, spec in ex.faults.items():
            assert spec.message and spec.weight >= 0
