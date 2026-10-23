# Design decisions

Choices made where the brief was ambiguous, with the reasoning.

## Environment
- **Python 3.12** (Homebrew) - the newest version with MediaPipe wheels for macOS arm64; satisfies "3.11+".
- **`opencv-contrib-python` instead of `opencv-python`** - MediaPipe depends on the contrib build; installing both
  puts two copies of `cv2` in the venv, so only the contrib build is pinned.
- **`PySide6-Essentials`** instead of the full `PySide6` meta-package - it contains QtCore/QtGui/QtWidgets, which is
  everything the app uses, and is a fraction of the download/bundle size.

## Data
- **Mendeley subset**: only the camera view the app recommends is downloaded for each exercise
  (push-up/squat/bicep curl: side; shoulder press: front), good and bad form, all 24 subjects
  (~190 videos, ~700 MB). The "Exercise-wise" folder organisation is used because it splits by view.
- **Pull-ups** come from Kaggle `hasyimabdillah/workoutfitness-video` (the Mendeley set has none).

## Pose / landmarks
- Landmarks are kept in **pixel units** (not MediaPipe's normalised 0-1) so angles are correct on 16:9 frames.
- PoseLandmarker runs in **VIDEO mode** (synchronous, uses tracking between frames); inference runs in a QThread so
  the UI never blocks.

## Rep counting
- The rep counter uses **lenient counting thresholds** (e.g. push-up: start >= 145 deg, turn <= 110 deg) while the
  brief's stricter numbers (elbow < 90 then > 160) are **form criteria**. A shallow push-up is therefore still seen
  and recorded as a scored "no rep" ("Go lower") instead of being silently ignored.
- Movements that leave the start position by at least `partial_range` but never reach the turn zone are recorded as
  no-reps too, so the user gets feedback on half reps.
- **Lockout is judged at the start of each rep** (how straight the arms/legs were before the rep began), because the
  end-of-rep lockout is only known after the next rep starts. The last rep of a set is therefore not judged on
  lockout.
- Visibility dropouts shorter than 0.5 s do not pause counting (MediaPipe occasionally drops a frame).

## Signals (found while tuning on the dataset)
- **Push-up counting uses shoulder height, not the elbow angle.** On the side-view clips the 2-D elbow angle from
  MediaPipe is unreliable: for some subjects a chest-to-floor rep reads ~120 deg, for others locked-out arms read
  ~130 deg. The counting signal is the shoulder's height above the wrist as a **percentage of the person's own
  arms-straight height** (rolling 90th percentile over 6 s), which self-calibrates to body size and camera angle.
  The elbow angle is still used for form ("Go lower" fires only if *both* the shoulder drop and the elbow bend are
  insufficient; "Straighten your arms" uses the elbow angle before the rep).
- **Shoulder press height is normalised by arm length** (shoulder-elbow + elbow-wrist) instead of torso length:
  in the front view this reads ~1.0 at lockout for every subject (std 0.02 vs 0.05 with torso length).
- The brief's angle numbers (push-up elbow 90/160, squat knee 100/165, curl 45/150) are the starting values of the
  *form* thresholds; `tools/tune_thresholds.py` adjusted them to what good-form reps actually measure in 2-D, e.g.
  curl top 45 -> 70 deg (the forearm is foreshortened at the top in a side view) and squat depth relaxed because
  "good" dataset squats rarely reach hip-below-knee in the image.

## Tuning and evaluation
- **Expected rep counts are automatic**: `scipy.signal.find_peaks` on the smoothed whole-clip signal
  (`tools/reference_counts.py`) - an offline method independent of the live state machine.
- **Subject-level train/test split** (subjects < 18 train, >= 18 test) so the reported accuracy is on people the
  thresholds were not tuned on. Counter thresholds are only replaced when the suggestion is strictly better on the
  training subjects.
- **Clip-level form label**: a clip is predicted "bad" when at least half of its reps have any fault. The dataset
  labels whole clips, and bad clips contain different kinds of mistakes, so per-rule accuracy can't be measured.
- Fixture clips for tests are cut to <= 240 frames, ending in the start position, with landmarks rounded to 0.1 px
  (~145 KB each). They contain landmark coordinates only - no images.

## Pull-ups
- The Mendeley dataset has no pull-ups and the Kaggle dataset needs credentials that are not set up yet.
  Hugging Face was searched first (`pull-up`, `workout`, `exercise video`): the only video sets were either
  free-text captioned without class labels (`prithivMLmods/Gym-Exercise-Video-Analysis`) or under a restrictive
  research licence (`Voxel51/qualcomm-exercise-video-dataset-benchmark`). Until the Kaggle clips are downloaded,
  pull-up thresholds are hand-set defaults covered by synthetic tests (`tests/test_front_view_exercises.py`);
  after `scripts/download_data.py --only kaggle`, run `tools/extract_landmarks.py --exercise pull_up` and
  `tools/tune_thresholds.py --exercise pull_up`.
