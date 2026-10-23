import math

import numpy as np
import pytest

from formcoach.core import geometry as g
from formcoach.core import landmarks as L


def test_right_angle():
    assert g.angle((1, 0), (0, 0), (0, 1)) == pytest.approx(90.0)


def test_straight_and_folded():
    assert g.angle((-1, 0), (0, 0), (1, 0)) == pytest.approx(180.0)
    assert g.angle((1, 0), (0, 0), (1, 0)) == pytest.approx(0.0)


def test_angle_45_and_degenerate():
    assert g.angle((1, 0), (0, 0), (1, 1)) == pytest.approx(45.0)
    assert math.isnan(g.angle((0, 0), (0, 0), (1, 1)))


def test_angle_ignores_z_and_visibility():
    assert g.angle((1, 0, 5, 0.9), (0, 0, 1, 0.1), (0, 1, -3, 1.0)) == pytest.approx(90.0)


def test_distance():
    assert g.distance((0, 0), (3, 4)) == pytest.approx(5.0)


def test_line_deviation_and_sign():
    assert g.line_deviation((0, 0), (5, 0), (10, 0)) == pytest.approx(0.0)
    # b below the line (larger y) = sag -> positive
    assert g.signed_line_deviation((0, 0), (5, 2), (10, 0)) > 0
    assert g.signed_line_deviation((0, 0), (5, -2), (10, 0)) < 0
    assert abs(g.signed_line_deviation((0, 0), (5, 2), (10, 0))) == pytest.approx(
        g.line_deviation((0, 0), (5, 2), (10, 0)))


def test_angle_to_vertical():
    assert g.angle_to_vertical((0, 0), (0, 10)) == pytest.approx(0.0)    # straight up
    assert g.angle_to_vertical((10, 10), (0, 10)) == pytest.approx(90.0)  # horizontal
    assert g.angle_to_vertical((10, 0), (0, 10)) == pytest.approx(45.0)


def test_torso_length_and_normalisation():
    lms = np.zeros((33, 4))
    lms[L.LEFT_SHOULDER, :2] = (100, 100)
    lms[L.RIGHT_SHOULDER, :2] = (140, 100)
    lms[L.LEFT_HIP, :2] = (100, 300)
    lms[L.RIGHT_HIP, :2] = (140, 300)
    assert g.torso_length(lms) == pytest.approx(200.0)
    assert g.normalised(50.0, 200.0) == pytest.approx(0.25)
    # The same pose at half the size gives the same normalised value.
    assert g.normalised(25.0, g.torso_length(lms * 0.5)) == pytest.approx(0.25)
