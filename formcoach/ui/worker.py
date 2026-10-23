"""Background worker: camera/video -> pose -> engine -> annotated frames, on a QThread."""
from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..core.engine import EngineOutput, State, WorkoutEngine
from ..core.overlay import draw_skeleton
from ..core.pose import ModelMissingError, PoseEstimator
from ..core.video_source import SourceError, VideoSource, pick_dataset_clip
from .widgets import bgr_to_qimage


@dataclass
class SourceSpec:
    kind: str = "webcam"            # webcam | video | dataset
    camera: int = 0
    path: str = ""
    width: int = 1280
    height: int = 720

    def describe(self) -> str:
        if self.kind == "webcam":
            return f"webcam {self.camera}"
        return self.path


class EngineWorker(QObject):
    frame_ready = Signal(object)        # QImage
    stats = Signal(dict)
    rep_done = Signal(dict)
    speak = Signal(str)
    error = Signal(str)
    source_opened = Signal(str)
    finished = Signal(object)           # Session

    def __init__(self, exercise: str, config: dict, source: SourceSpec, target_reps: int | None = None,
                 target_sets: int | None = None, user_id: int | None = None):
        super().__init__()
        self.exercise = exercise
        self.config = config
        self.source = source
        self.target_reps = target_reps
        self.target_sets = target_sets
        self.user_id = user_id
        self._stop = False
        self._paused = False
        self._next_set = False

    # Thread-safe enough for simple flags under the GIL.
    @Slot()
    def stop(self) -> None:
        self._stop = True

    @Slot(bool)
    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    @Slot()
    def next_set(self) -> None:
        self._next_set = True

    @Slot()
    def run(self) -> None:
        engine = None
        try:
            spec = self.source
            if spec.kind == "dataset":
                spec.path = str(pick_dataset_clip(self.exercise))
            src = spec.camera if spec.kind == "webcam" else spec.path
            # Open the input first so camera/file problems are reported as such.
            with VideoSource(src, spec.width, spec.height, realtime=spec.kind != "webcam") as vs:
                estimator = PoseEstimator()
                engine = WorkoutEngine(self.exercise, self.config, self.target_reps, self.target_sets,
                                       user_id=self.user_id, source=spec.describe())
                self.source_opened.emit(spec.describe())
                try:
                    self._loop(vs, estimator, engine)
                finally:
                    estimator.close()
        except ModelMissingError as exc:
            self.error.emit(str(exc))
        except SourceError as exc:
            msg = str(exc)
            if engine is not None and engine.session.reps:
                msg += " - the reps so far have been saved."
            self.error.emit(msg)
        except Exception as exc:  # never let the worker die silently
            self.error.emit(f"Unexpected error: {exc}")
        finally:
            if engine is not None:
                self.finished.emit(engine.finish())
            else:
                self.finished.emit(None)

    def _loop(self, vs: VideoSource, estimator: PoseEstimator, engine: WorkoutEngine) -> None:
        fps = 0.0
        paused_at = None
        pause_offset = 0.0
        last = time.perf_counter()
        while not self._stop:
            if self._paused:
                if paused_at is None:
                    paused_at = time.perf_counter()
                if not vs.is_camera:
                    QThread.msleep(30)
                    continue
                frame = vs.read()   # keep the camera preview alive while paused
                if frame is not None:
                    self.frame_ready.emit(bgr_to_qimage(frame.image))
                continue
            if paused_at is not None:
                paused_for = time.perf_counter() - paused_at
                if vs.is_camera:
                    pause_offset += paused_for
                else:
                    vs.shift_clock(paused_for)
                paused_at = None
            if self._next_set:
                engine.next_set()
                self._next_set = False

            frame = vs.read()
            if frame is None:
                break  # end of the video file
            img = frame.image
            if vs.is_camera:
                img = cv2.flip(img, 1)  # mirror the webcam so it feels like a mirror
            t = frame.timestamp_ms / 1000.0 - pause_offset
            res = estimator.process(img, int(t * 1000))
            out = engine.process(res.landmarks if res else None, t)
            self._draw(img, out)

            now = time.perf_counter()
            dt = now - last
            last = now
            fps = 0.9 * fps + 0.1 / max(dt, 1e-6) if fps else 1 / max(dt, 1e-6)
            self.frame_ready.emit(bgr_to_qimage(img))
            self.stats.emit(self._stats(out, fps))
            if out.new_rep is not None:
                r = out.new_rep
                self.rep_done.emit({"index": r.index, "score": r.score, "valid": r.valid,
                                    "faults": [engine.exercise.message(f) for f in r.faults]})
            if out.message is not None and out.message.say:
                self.speak.emit(out.message.say)
            if out.state == State.FINISHED:
                self.speak.emit("Workout complete. Great job!")
                break

    def _draw(self, img, out: EngineOutput) -> None:
        if out.landmarks is not None:
            draw_skeleton(img, out.landmarks, out.bad_joints, min_visibility=0.5)
        if out.state == State.COUNTDOWN and out.countdown > 0:
            h, w = img.shape[:2]
            txt = str(int(out.countdown) + 1)
            scale = h / 160
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, scale, 8)
            cv2.putText(img, txt, ((w - tw) // 2, (h + th) // 2), cv2.FONT_HERSHEY_DUPLEX, scale,
                        (255, 255, 255), 8, cv2.LINE_AA)

    @staticmethod
    def _stats(out: EngineOutput, fps: float) -> dict:
        msg = out.message
        return {
            "state": out.state.value, "reps": out.reps, "no_reps": out.no_reps, "set": out.set_number,
            "reps_in_set": out.reps_in_set, "fps": fps, "countdown": out.countdown,
            "message": msg.text if msg else "", "level": msg.level if msg else "info",
        }
