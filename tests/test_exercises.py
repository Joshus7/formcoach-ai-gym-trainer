"""Per-exercise tests on real landmark sequences cut from the dataset (tests/fixtures)."""
import json
from pathlib import Path

import pytest

from formcoach.core.config import load_config
from formcoach.core.engine import WorkoutEngine
from formcoach.core.landmark_io import load_fixture

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED = json.loads((FIXTURES / "expected_counts.json").read_text())
CFG = load_config()


def run(name):
    seq, meta = load_fixture(FIXTURES / f"{name}.json")
    eng = WorkoutEngine(meta["exercise"], CFG, countdown_s=0)
    for lms, t in seq.frames():
        eng.process(lms, t)
    return eng.finish()


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_rep_count_matches_reference(name):
    session = run(name)
    exp = EXPECTED[name]["reps"]
    # The reference is an offline peak detector; allow one rep at the clip edges.
    assert abs(session.total_attempts - exp) <= 1, f"{name}: got {session.total_attempts}, expected {exp}"


def test_rep_counts_exact_on_most_fixtures():
    names = sorted(EXPECTED)
    exact = sum(run(n).total_attempts == EXPECTED[n]["reps"] for n in names)
    assert exact >= 0.75 * len(names)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_reps_are_scored(name):
    session = run(name)
    for r in session.reps:
        assert 0 <= r.score <= 100
        assert r.valid == (r.score >= CFG["general"]["no_rep_below"] and not any(
            CFG[EXPECTED[name]["exercise"]]["faults"][f].get("major") for f in r.faults))
        assert r.duration > 0


def test_fixture_files_are_small():
    for p in FIXTURES.glob("*.json"):
        assert p.stat().st_size < 400_000, p.name
