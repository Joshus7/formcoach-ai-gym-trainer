"""SQLite storage for users, workout sessions and reps (no images or video are ever stored)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from ..core.exercises.base import RepResult
from ..core.session import Session

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER REFERENCES users(id) ON DELETE CASCADE,
    exercise           TEXT NOT NULL,
    started_at         TEXT NOT NULL,
    ended_at           TEXT,
    total_reps         INTEGER NOT NULL DEFAULT 0,
    no_reps            INTEGER NOT NULL DEFAULT 0,
    avg_score          REAL NOT NULL DEFAULT 0,
    duration_s         REAL NOT NULL DEFAULT 0,
    tut_s              REAL NOT NULL DEFAULT 0,
    sets_completed     INTEGER NOT NULL DEFAULT 0,
    target_reps        INTEGER,
    target_sets        INTEGER,
    most_common_fault  TEXT,
    source             TEXT
);
CREATE TABLE IF NOT EXISTS reps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    idx         INTEGER NOT NULL,
    score       INTEGER NOT NULL,
    valid       INTEGER NOT NULL,
    faults      TEXT NOT NULL DEFAULT '[]',
    duration    REAL NOT NULL,
    start_t     REAL,
    end_t       REAL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, started_at);
CREATE INDEX IF NOT EXISTS idx_reps_session ON reps(session_id, idx);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ users
    def add_user(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Name must not be empty")
        row = self.conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"]
        cur = self.conn.execute("INSERT INTO users (name, created_at) VALUES (?, ?)",
                                (name, datetime.now().isoformat(timespec="seconds")))
        self.conn.commit()
        return cur.lastrowid

    def list_users(self) -> list[tuple[int, str]]:
        return [(r["id"], r["name"]) for r in self.conn.execute("SELECT id, name FROM users ORDER BY name")]

    def default_user(self) -> int:
        users = self.list_users()
        return users[0][0] if users else self.add_user("Guest")

    def user_name(self, user_id: int | None) -> str:
        row = self.conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
        return row["name"] if row else "Guest"

    # ------------------------------------------------------------------ sessions
    def save_session(self, s: Session) -> int:
        cur = self.conn.execute(
            """INSERT INTO sessions (user_id, exercise, started_at, ended_at, total_reps, no_reps, avg_score,
                   duration_s, tut_s, sets_completed, target_reps, target_sets, most_common_fault, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (s.user_id, s.exercise, s.started_at.isoformat(timespec="seconds"),
             s.ended_at.isoformat(timespec="seconds") if s.ended_at else None, s.good_reps, s.no_reps,
             round(s.avg_score, 2), round(s.duration_s, 2), round(s.time_under_tension_s, 2), s.sets_completed,
             s.target_reps, s.target_sets, s.most_common_fault, s.source))
        sid = cur.lastrowid
        self.conn.executemany(
            "INSERT INTO reps (session_id, idx, score, valid, faults, duration, start_t, end_t) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(sid, r.index, r.score, int(r.valid), json.dumps(r.faults), r.duration, r.start_t, r.end_t)
             for r in s.reps])
        self.conn.commit()
        return sid

    def list_sessions(self, user_id: int | None = None, exercise: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM sessions WHERE 1=1", []
        if user_id is not None:
            q += " AND user_id = ?"
            args.append(user_id)
        if exercise:
            q += " AND exercise = ?"
            args.append(exercise)
        q += " ORDER BY started_at"
        return [dict(r) for r in self.conn.execute(q, args)]

    def get_reps(self, session_id: int) -> list[RepResult]:
        rows = self.conn.execute("SELECT * FROM reps WHERE session_id = ? ORDER BY idx", (session_id,))
        return [RepResult(r["idx"], r["score"], json.loads(r["faults"]), bool(r["valid"]), r["duration"],
                          r["start_t"] or 0.0, r["end_t"] or 0.0) for r in rows]

    def load_session(self, session_id: int) -> Session | None:
        r = self.conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if r is None:
            return None
        s = Session(r["exercise"], user_id=r["user_id"], started_at=datetime.fromisoformat(r["started_at"]),
                    ended_at=datetime.fromisoformat(r["ended_at"]) if r["ended_at"] else None,
                    target_reps=r["target_reps"], target_sets=r["target_sets"],
                    sets_completed=r["sets_completed"], source=r["source"] or "")
        s.reps = self.get_reps(session_id)
        return s

    def delete_session(self, session_id: int) -> None:
        self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.conn.commit()

    def delete_user(self, user_id: int) -> None:
        self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()
