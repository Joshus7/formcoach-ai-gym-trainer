import numpy as np

from formcoach.core.smoothing import LandmarkSmoother, OneEuroFilter


def test_constant_signal_is_unchanged():
    f = OneEuroFilter()
    out = [f(5.0, i / 30) for i in range(30)]
    assert np.allclose(out, 5.0)


def test_reduces_jitter():
    rng = np.random.default_rng(0)
    f = OneEuroFilter(min_cutoff=1.0, beta=0.0)
    noisy = 100 + rng.normal(0, 3, 300)
    out = np.array([f(v, i / 30) for i, v in enumerate(noisy)])
    assert out[50:].std() < noisy[50:].std() / 2


def test_follows_fast_motion_with_beta():
    t = np.arange(0, 2, 1 / 30)
    sig = 90 + 70 * np.sin(2 * np.pi * 1.0 * t)
    slow = OneEuroFilter(min_cutoff=0.5, beta=0.0)
    fast = OneEuroFilter(min_cutoff=0.5, beta=0.05)
    err_slow = np.abs([slow(v, ti) - v for v, ti in zip(sig, t)])[15:].mean()
    err_fast = np.abs([fast(v, ti) - v for v, ti in zip(sig, t)])[15:].mean()
    assert err_fast < err_slow


def test_array_and_nan_handling():
    f = OneEuroFilter()
    f(np.array([1.0, 2.0]), 0.0)
    out = f(np.array([np.nan, 2.0]), 1 / 30)
    assert not np.isnan(out).any()
    assert out[0] == 1.0


def test_duplicate_timestamp_returns_last():
    f = OneEuroFilter()
    f(1.0, 0.0)
    a = f(2.0, 0.1)
    assert f(50.0, 0.1) == a


def test_landmark_smoother_keeps_visibility_and_resets():
    s = LandmarkSmoother(reset_after_s=0.5)
    lms = np.zeros((33, 4))
    lms[:, 3] = 0.7
    s(lms, 0.0)
    moved = lms.copy()
    moved[:, :2] = 100
    out = s(moved, 1 / 30)
    assert np.allclose(out[:, 3], 0.7)
    assert (out[:, 0] < 100).all()           # smoothed
    out2 = s(moved, 2.0)                     # long gap -> reset, no lag
    assert np.allclose(out2[:, 0], 100)
