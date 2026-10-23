import numpy as np
import pytest

from formcoach.core.rep_counter import Phase, RepCounter

FPS = 30


def rep_wave(n_reps: int, top=170.0, bottom=80.0, rep_s=2.0, hold_s=0.5) -> np.ndarray:
    """Synthetic elbow angle: hold at the top, then n smooth cosine reps."""
    hold = np.full(int(hold_s * FPS), top)
    t = np.arange(int(rep_s * FPS)) / (rep_s * FPS)
    one = bottom + (top - bottom) * (0.5 + 0.5 * np.cos(2 * np.pi * t))
    return np.concatenate([hold] + [np.concatenate([one, hold])] * n_reps)


def run(counter: RepCounter, signal) -> list:
    events = []
    for i, v in enumerate(signal):
        e = counter.update(float(v), i / FPS)
        if e is not None:
            events.append(e)
    return events


def make(**kw) -> RepCounter:
    params = dict(start=150, turn=110, direction="decreasing", hysteresis=5, min_rep_s=0.5)
    params.update(kw)
    return RepCounter(**params)


@pytest.mark.parametrize("n", [0, 1, 5, 12])
def test_counts_clean_reps_exactly(n):
    c = make()
    events = run(c, rep_wave(n))
    assert c.count == n
    assert len([e for e in events if not e.partial]) == n


def test_event_reports_extremes_and_duration():
    c = make()
    events = run(c, rep_wave(1, top=170, bottom=80, rep_s=2.0))
    e = events[0]
    assert e.extreme == pytest.approx(80, abs=1)
    assert e.start_peak == pytest.approx(170, abs=1)
    assert 1.0 < e.duration < 2.0


@pytest.mark.parametrize("seed", range(5))
def test_noisy_reps_count_exactly(seed):
    rng = np.random.default_rng(seed)
    sig = rep_wave(8) + rng.normal(0, 4, len(rep_wave(8)))
    c = make()
    run(c, sig)
    assert c.count == 8


def test_noise_around_thresholds_never_counts():
    rng = np.random.default_rng(1)
    # Jitter right at the start threshold and, separately, right at the turn threshold.
    near_start = 150 + rng.normal(0, 2, 300)
    near_turn = 110 + rng.normal(0, 3, 300)
    c = make()
    run(c, np.concatenate([np.full(10, 170), near_start, near_turn]))
    assert c.count == 0


def test_spikes_shorter_than_min_rep_time_are_ignored():
    sig = np.full(200, 170.0)
    sig[50:55] = 60   # 5-frame glitch (0.17 s) through the whole range
    sig[120:123] = 60
    c = make(min_rep_s=0.4)
    run(c, sig)
    assert c.count == 0


def test_must_start_in_start_position():
    # Starts at the bottom (e.g. person already lying down): first upswing is not a rep.
    sig = np.concatenate([np.full(30, 80), np.linspace(80, 170, 30), rep_wave(2)])
    c = make()
    run(c, sig)
    assert c.count == 2


def test_partial_reps_are_reported_not_counted():
    shallow = rep_wave(3, bottom=125)
    c = make(partial_range=20)
    events = run(c, shallow)
    assert c.count == 0
    assert c.partials == 3
    assert all(e.partial for e in events)


def test_partials_ignored_when_disabled():
    c = make(partial_range=None)
    events = run(c, rep_wave(3, bottom=125))
    assert events == [] and c.count == 0


def test_increasing_direction():
    # e.g. wrist height above shoulders: 0 = at shoulders, 1.2 = overhead
    sig = (170 - rep_wave(4)) / 90 * 1.2  # 0 -> ~1.2 -> 0
    c = RepCounter(start=0.25, turn=0.8, direction="increasing", hysteresis=0.05, min_rep_s=0.5)
    events = run(c, sig)
    assert c.count == 4
    assert events[0].extreme == pytest.approx(1.2, abs=0.05)


def test_reset_drops_rep_in_progress():
    c = make()
    sig = rep_wave(1)
    half = len(sig) // 2
    run(c, sig[:half])
    assert c.in_rep
    c.reset()
    assert c.phase == Phase.WAITING
    for i, v in enumerate(sig[half:]):
        c.update(float(v), (half + i) / FPS)
    assert c.count == 0


def test_nan_values_are_skipped():
    sig = rep_wave(3).astype(float)
    sig[::7] = np.nan
    c = make()
    run(c, sig)
    assert c.count == 3


def test_stuck_mid_rep_is_abandoned():
    sig = np.concatenate([np.full(10, 170), np.full(30 * 25, 90), np.full(10, 170)])
    c = make(max_rep_s=20)
    run(c, sig)
    assert c.count == 0


def test_invalid_config():
    with pytest.raises(ValueError):
        RepCounter(start=100, turn=150, direction="decreasing")
    with pytest.raises(ValueError):
        RepCounter(start=100, turn=50, direction="sideways")
