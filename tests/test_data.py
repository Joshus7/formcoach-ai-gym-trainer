"""SQLite storage and CSV/PDF export (temporary database)."""
import csv
from datetime import datetime, timedelta

import pytest

from formcoach.core.exercises.base import RepResult
from formcoach.core.session import Session
from formcoach.data.db import Database
from formcoach.data.export import history_to_csv, session_to_csv, session_to_pdf


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


def session(user_id, exercise="push_up", n=5, start=None):
    s = Session(exercise, user_id=user_id, started_at=start or datetime(2026, 1, 1, 10, 0), source="test")
    for i in range(1, n + 1):
        valid = i % 3 != 0
        s.add_rep(RepResult(i, 100 if valid else 40, [] if valid else ["not_deep"], valid, 1.5, i * 2.0, i * 2.0 + 1.5))
    s.ended_at = s.started_at + timedelta(minutes=2)
    return s


def test_users(db):
    a = db.add_user("Asha")
    assert db.add_user("Asha") == a          # unique, idempotent
    b = db.add_user(" Ravi ")
    assert db.list_users() == [(a, "Asha"), (b, "Ravi")]
    assert db.user_name(b) == "Ravi" and db.user_name(999) == "Guest"
    with pytest.raises(ValueError):
        db.add_user("  ")


def test_default_user_created_once(db):
    uid = db.default_user()
    assert db.default_user() == uid
    assert db.list_users() == [(uid, "Guest")]


def test_save_and_load_roundtrip(db):
    uid = db.add_user("Asha")
    s = session(uid, n=6)
    sid = db.save_session(s)
    rows = db.list_sessions(uid)
    assert len(rows) == 1
    r = rows[0]
    assert r["total_reps"] == 4 and r["no_reps"] == 2 and r["most_common_fault"] == "not_deep"
    assert r["avg_score"] == pytest.approx((4 * 100 + 2 * 40) / 6, abs=0.01)
    loaded = db.load_session(sid)
    assert loaded.exercise == "push_up" and len(loaded.reps) == 6
    assert loaded.reps[2].faults == ["not_deep"] and loaded.reps[2].valid is False
    assert loaded.started_at == s.started_at and loaded.duration_s == pytest.approx(120)


def test_filters_and_ordering(db):
    a, b = db.add_user("A"), db.add_user("B")
    db.save_session(session(a, "squat", start=datetime(2026, 1, 3)))
    db.save_session(session(a, "push_up", start=datetime(2026, 1, 1)))
    db.save_session(session(b, "squat", start=datetime(2026, 1, 2)))
    assert [r["exercise"] for r in db.list_sessions(a)] == ["push_up", "squat"]
    assert len(db.list_sessions(a, "squat")) == 1
    assert len(db.list_sessions(None, "squat")) == 2


def test_delete_cascades(db):
    uid = db.add_user("A")
    sid = db.save_session(session(uid))
    db.delete_session(sid)
    assert db.list_sessions(uid) == []
    assert db.conn.execute("SELECT COUNT(*) FROM reps").fetchone()[0] == 0
    db.save_session(session(uid))
    db.delete_user(uid)
    assert db.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_session_csv(tmp_path):
    p = session_to_csv(session(1, n=3), tmp_path / "s.csv", {"not_deep": "Go lower"})
    rows = list(csv.DictReader(open(p)))
    assert len(rows) == 3
    assert rows[2]["valid"] == "no rep" and rows[2]["faults"] == "Go lower"


def test_history_csv(db, tmp_path):
    uid = db.add_user("Asha")
    db.save_session(session(uid, "squat", start=datetime(2026, 1, 1)))
    db.save_session(session(uid, "push_up", start=datetime(2026, 1, 2)))
    rows = list(csv.DictReader(open(history_to_csv(db, uid, tmp_path / "h.csv"))))
    assert [r["exercise"] for r in rows] == ["squat", "push_up"]
    assert rows[0]["user"] == "Asha"
    assert len(list(csv.DictReader(open(history_to_csv(db, uid, tmp_path / "h2.csv", "squat"))))) == 1


@pytest.mark.parametrize("n", [0, 5, 60])
def test_pdf_is_one_page(tmp_path, n):
    p = session_to_pdf(session(1, n=n), tmp_path / "s.pdf", "Asha", {"not_deep": "Go lower"})
    data = p.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"/Count 1 " in data or b"/Count 1\n" in data or b"/Count 1/" in data   # page tree has one page
