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
