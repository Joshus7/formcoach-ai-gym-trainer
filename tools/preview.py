"""Quick OpenCV preview: skeleton overlay + FPS on a webcam, a video file or a dataset clip.

    python tools/preview.py --webcam 0
    python tools/preview.py --video path/to/clip.mp4
    python tools/preview.py --dataset push_up        # random clip from data/raw
    python tools/preview.py --dataset squat --headless --out reports/preview.jpg
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from formcoach.core.overlay import draw_fps, draw_skeleton  # noqa: E402
from formcoach.core.pose import PoseEstimator  # noqa: E402
from formcoach.core.video_source import VideoSource, pick_dataset_clip  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--webcam", type=int)
    src.add_argument("--video")
    src.add_argument("--dataset", help="exercise key, e.g. push_up")
    ap.add_argument("--headless", action="store_true", help="no window; print FPS and save a frame")
    ap.add_argument("--out", default=None, help="save the middle annotated frame here")
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args()

    if args.webcam is not None:
        source = args.webcam
    elif args.video:
        source = args.video
    else:
        source = str(pick_dataset_clip(args.dataset))
        print(f"Dataset clip: {source}")

    estimator = PoseEstimator()
    n = detected = 0
    t_start = time.perf_counter()
    fps = 0.0
    saved = None
    with VideoSource(source, realtime=not args.headless and args.webcam is None) as vs:
        target_save = vs.frame_count // 2 if vs.frame_count else 30
        for frame in vs:
            t0 = time.perf_counter()
            res = estimator.process(frame.image, frame.timestamp_ms)
            dt = time.perf_counter() - t0
            fps = 0.9 * fps + 0.1 * (1 / max(dt, 1e-6)) if n else 1 / max(dt, 1e-6)
            img = frame.image
            if res is not None:
                detected += 1
                draw_skeleton(img, res.landmarks)
            draw_fps(img, fps)
            n += 1
            if n == target_save:
                saved = img.copy()
            if not args.headless:
                cv2.imshow("FormCoach preview (q to quit)", img)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            if args.max_frames and n >= args.max_frames:
                break
    estimator.close()
    cv2.destroyAllWindows()
    total = time.perf_counter() - t_start
    print(f"frames={n} pose_detected={detected} ({100 * detected / max(n, 1):.0f}%) "
          f"pipeline_fps={n / total:.1f} inference_fps~{fps:.1f}")
    if args.out and saved is not None:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(args.out, saved)
        print(f"saved {args.out}")


if __name__ == "__main__":
    main()
