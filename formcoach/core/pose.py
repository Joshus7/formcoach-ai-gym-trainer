"""Thin wrapper around the MediaPipe Tasks PoseLandmarker (pose_landmarker_full).

Landmarks are returned as an (33, 4) float array in *pixel* units:
``[x_px, y_px, z (scaled like x), visibility]``. Pixel units keep angles correct
for non-square frames.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = ROOT / "models" / "pose_landmarker_full.task"


class ModelMissingError(FileNotFoundError):
    pass


@dataclass
class PoseResult:
    landmarks: np.ndarray       # (33, 4) pixels + visibility
    width: int
    height: int
    timestamp_ms: int


class PoseEstimator:
    """Synchronous (VIDEO running mode) pose estimator.

    Timestamps passed to :meth:`process` must increase; the wrapper fixes up
    duplicates so callers can pass video-file timestamps directly.
    """

    def __init__(self, model_path: str | Path | None = None, min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5, use_gpu: bool = False):
        model_path = Path(model_path or DEFAULT_MODEL)
        if not model_path.exists():
            raise ModelMissingError(
                f"Pose model not found at {model_path}. Run: python scripts/download_models.py")
        delegate = BaseOptions.Delegate.GPU if use_gpu else BaseOptions.Delegate.CPU
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path), delegate=delegate),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._last_ts = -1

    def process(self, frame_bgr: np.ndarray, timestamp_ms: int) -> PoseResult | None:
        ts = int(timestamp_ms)
        if ts <= self._last_ts:
            ts = self._last_ts + 1
        self._last_ts = ts
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, ts)
        if not result.pose_landmarks:
            return None
        pts = result.pose_landmarks[0]
        arr = np.array([[p.x * w, p.y * h, p.z * w, p.visibility if p.visibility is not None else 0.0]
                        for p in pts], dtype=np.float32)
        return PoseResult(arr, w, h, ts)

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
