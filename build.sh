#!/usr/bin/env bash
# Build a standalone FormCoach app with PyInstaller (macOS / Linux).
#   ./build.sh            -> dist/FormCoach (and dist/FormCoach.app on macOS)
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-.venv/bin/python}

"$PY" scripts/download_models.py

"$PY" -m PyInstaller --noconfirm --clean --windowed --name FormCoach \
  --collect-data mediapipe --collect-binaries mediapipe \
  --add-data "config/exercises.yaml:config" \
  --add-data "models/pose_landmarker_full.task:models" \
  --hidden-import pyttsx3.drivers --hidden-import pyttsx3.drivers.nsss \
  --hidden-import pyttsx3.drivers.espeak --hidden-import pyttsx3.drivers.sapi5 \
  --exclude-module tkinter \
  run_formcoach.py

echo "Built: dist/FormCoach"
