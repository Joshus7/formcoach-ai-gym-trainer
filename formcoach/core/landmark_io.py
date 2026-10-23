"""Read/write cached landmark sequences (.npz from tools/extract_landmarks.py, .json test fixtures)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class LandmarkSequence:
    landmarks: np.ndarray   # (T, 33, 4), NaN rows where no pose was found
    timestamps: np.ndarray  # (T,) seconds
    fps: float
    width: int
    height: int
    name: str = ""

    def __len__(self) -> int:
        return len(self.timestamps)

    def frames(self):
        for lms, t in zip(self.landmarks, self.timestamps):
            yield (None if np.isnan(lms[0, 0]) else lms), float(t)

    def slice(self, start: int, stop: int) -> "LandmarkSequence":
        return LandmarkSequence(self.landmarks[start:stop], self.timestamps[start:stop] - self.timestamps[start],
                                self.fps, self.width, self.height, self.name)


def load_npz(path: str | Path) -> LandmarkSequence:
    d = np.load(path)
    return LandmarkSequence(d["landmarks"], d["timestamps"].astype(float) / 1000.0, float(d["fps"]),
                            int(d["width"]), int(d["height"]), Path(path).stem)


def save_fixture(seq: LandmarkSequence, path: str | Path, meta: dict | None = None) -> None:
    """Compact JSON fixture: coordinates rounded to 0.1 px, visibility to 0.01."""
    rows = []
    for lms in seq.landmarks:
        if np.isnan(lms[0, 0]):
            rows.append(None)
        else:
            rows.append([[round(float(x), 1), round(float(y), 1), round(float(v), 2)] for x, y, _, v in lms])
    data = {"name": seq.name, "fps": seq.fps, "width": seq.width, "height": seq.height,
            "timestamps": [round(float(t), 3) for t in seq.timestamps], "frames": rows, "meta": meta or {}}
    Path(path).write_text(json.dumps(data, separators=(",", ":")))


def load_fixture(path: str | Path) -> tuple[LandmarkSequence, dict]:
    d = json.loads(Path(path).read_text())
    arr = np.full((len(d["frames"]), 33, 4), np.nan, np.float32)
    for i, f in enumerate(d["frames"]):
        if f is not None:
            a = np.asarray(f, np.float32)
            arr[i, :, 0], arr[i, :, 1], arr[i, :, 3] = a[:, 0], a[:, 1], a[:, 2]
            arr[i, :, 2] = 0.0
    seq = LandmarkSequence(arr, np.asarray(d["timestamps"], float), d["fps"], d["width"], d["height"], d["name"])
    return seq, d.get("meta", {})
