"""Frame sources: webcam, video file, or a clip from the downloaded dataset."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"

# Exercise key -> dataset folders (relative to data/raw) holding demo clips.
DATASET_DIRS = {
    "push_up": ["mendeley/push_up/good/side", "mendeley/push_up/bad/side", "kaggle_workout/push-up"],
    "squat": ["mendeley/squat/good/side", "mendeley/squat/bad/side", "kaggle_workout/squat"],
    "bicep_curl": ["mendeley/bicep_curl/good/side", "mendeley/bicep_curl/bad/side",
                   "kaggle_workout/barbell_biceps_curl"],
    "shoulder_press": ["mendeley/shoulder/good/front", "mendeley/shoulder/bad/front",
                       "kaggle_workout/shoulder_press"],
    "pull_up": ["kaggle_workout/pull_up"],
}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


class SourceError(RuntimeError):
    pass


def dataset_clips(exercise: str) -> list[Path]:
    clips: list[Path] = []
    for rel in DATASET_DIRS.get(exercise, []):
        d = DATA_RAW / rel
        if d.is_dir():
            clips += sorted(p for p in d.iterdir() if p.suffix.lower() in VIDEO_EXT)
    return clips


def pick_dataset_clip(exercise: str, seed: int | None = None) -> Path:
    clips = dataset_clips(exercise)
    if not clips:
        raise SourceError(
            f"No dataset clips for '{exercise}'. Run: python scripts/download_data.py")
    return random.Random(seed).choice(clips)


@dataclass
class Frame:
    image: np.ndarray
    timestamp_ms: int
    index: int


class VideoSource:
    """Uniform reader. For files, timestamps come from the file (so analysis is
    deterministic); with ``realtime=True`` reading is paced to the file's FPS."""

    def __init__(self, source: int | str | Path, width: int | None = None, height: int | None = None,
                 realtime: bool = False, loop: bool = False):
        self.is_camera = isinstance(source, int)
        self.source = source
        self.realtime = realtime
        self.loop = loop
        if self.is_camera:
            self.cap = cv2.VideoCapture(source)
            if width:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            if height:
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        else:
            path = Path(source)
            if not path.exists():
                raise SourceError(f"Video file not found: {path}")
            self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise SourceError(f"Could not open camera {source}" if self.is_camera
                              else f"Could not open video {source}")
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.fps = fps if fps and 1 <= fps <= 240 else 30.0
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) if not self.is_camera else 0
        self._index = 0
        self._t0 = time.monotonic()
        self._loop_offset_ms = 0
        self._last_ts = 0

    def read(self) -> Frame | None:
        """Next frame, or None at end of file. Raises SourceError if a camera disconnects."""
        ok, img = self.cap.read()
        if not ok or img is None:
            if self.is_camera:
                raise SourceError("Camera disconnected or stopped sending frames")
            if self.loop and self._index > 0:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self._loop_offset_ms = self._last_ts + int(1000 / self.fps)
                ok, img = self.cap.read()
            if not ok or img is None:
                return None
        if self.is_camera:
            ts = int((time.monotonic() - self._t0) * 1000)
        else:
            ts = self._loop_offset_ms + int(round(self._index_in_file() * 1000 / self.fps))
            if self.realtime:
                delay = ts / 1000 - (time.monotonic() - self._t0)
                if delay > 0:
                    time.sleep(delay)
        self._last_ts = ts
        frame = Frame(img, ts, self._index)
        self._index += 1
        return frame

    def _index_in_file(self) -> int:
        pos = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
        return int(pos) - 1 if pos else self._index

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()

    def __iter__(self):
        while True:
            f = self.read()
            if f is None:
                return
            yield f


def list_cameras(max_index: int = 4) -> list[int]:
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            found.append(i)
        cap.release()
    return found
