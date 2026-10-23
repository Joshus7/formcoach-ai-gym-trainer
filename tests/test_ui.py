"""Headless UI tests (Qt offscreen platform)."""
import ast
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from formcoach.core.config import load_config  # noqa: E402
from formcoach.core.exercises.base import RepResult  # noqa: E402
from formcoach.core.session import Session  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_core_has_no_qt_imports():
    for path in (ROOT / "formcoach" / "core").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(n.startswith(("PySide6", "PyQt", "pyqtgraph")) for n in names), path


def make_session():
    s = Session("push_up", source="test")
    for i, (score, valid, faults) in enumerate([(100, True, []), (70, True, ["hips_out_of_line"]),
                                                 (45, False, ["not_deep", "no_lockout"])], 1):
        s.add_rep(RepResult(i, score, faults, valid, 1.2, i * 2.0, i * 2.0 + 1.2))
    s.finish()
    return s


def test_summary_view_shows_session(app):
    from formcoach.ui.summary_view import SummaryView
    from formcoach.ui.theme import DARK
    v = SummaryView(DARK)
    v.show_session(make_session(), {"not_deep": "Go lower", "hips_out_of_line": "Keep your hips in line",
                                    "no_lockout": "Straighten your arms"})
    assert v.cards["reps"].value.text() == "2"
    assert v.cards["split"].value.text() == "2 / 1"
    assert v.cards["best"].value.text() == "#1 (100)"
    assert v.cards["worst"].value.text() == "#3 (45)"


def test_live_view_updates(app):
    from formcoach.ui.live_view import LiveView
    from formcoach.ui.theme import DARK
    v = LiveView(DARK)
    v.reset("Squat", True)
    v.update_stats({"state": "active", "reps": 4, "no_reps": 1, "set": 2, "reps_in_set": 1, "fps": 29.5,
                    "countdown": 0, "message": "Keep your chest up", "level": "warn"})
    assert v.reps.text() == "4" and "Set 2" in v.set_label.text()
    v.show_rep({"index": 5, "score": 40, "valid": False, "faults": ["Go lower"]})
    assert v.score.text().startswith("NO REP")


def test_home_view_emits_request(app):
    from formcoach.ui.home_view import HomeView
    v = HomeView()
    v.set_users([(1, "Asha"), (2, "Ravi")], current=2)
    got = []
    v.start_requested.connect(got.append)
    v._tiles["squat"].click()
    v.reps_spin.setValue(10)
    v.start_btn.click()
    assert got and got[0]["exercise"] == "squat" and got[0]["target_reps"] == 10 and got[0]["user_id"] == 2


def test_worker_reports_missing_video_without_crashing(app):
    from formcoach.ui.worker import EngineWorker, SourceSpec
    w = EngineWorker("push_up", load_config(), SourceSpec(kind="video", path="/no/such/file.mp4"))
    errors, finished = [], []
    w.error.connect(errors.append)
    w.finished.connect(finished.append)
    w.run()  # synchronous for the test
    QCoreApplication.processEvents()
    assert errors and "not found" in errors[0]
    assert finished


def test_worker_reports_missing_camera(app):
    from formcoach.ui.worker import EngineWorker, SourceSpec
    w = EngineWorker("push_up", load_config(), SourceSpec(kind="webcam", camera=97))
    errors = []
    w.error.connect(errors.append)
    w.run()
    assert errors and "camera" in errors[0].lower()


def test_worker_reports_missing_model(app, monkeypatch, tmp_path):
    from formcoach.core import pose
    from formcoach.ui.worker import EngineWorker, SourceSpec
    monkeypatch.setattr(pose, "DEFAULT_MODEL", tmp_path / "missing.task")
    import cv2
    import numpy as np
    vw = cv2.VideoWriter(str(tmp_path / "tiny.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    for _ in range(3):
        vw.write(np.zeros((48, 64, 3), np.uint8))
    vw.release()
    w = EngineWorker("push_up", load_config(), SourceSpec(kind="video", path=str(tmp_path / "tiny.mp4")))
    errors = []
    w.error.connect(errors.append)
    w.run()
    assert errors and "download_models.py" in errors[0]
