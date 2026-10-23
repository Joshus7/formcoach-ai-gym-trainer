@echo off
REM Build a standalone FormCoach app with PyInstaller (Windows).
REM   build.bat   ->  dist\FormCoach\FormCoach.exe
cd /d "%~dp0"
if "%PYTHON%"=="" set PYTHON=.venv\Scripts\python.exe

%PYTHON% scripts\download_models.py || exit /b 1

%PYTHON% -m PyInstaller --noconfirm --clean --windowed --name FormCoach ^
  --collect-data mediapipe --collect-binaries mediapipe ^
  --add-data "config/exercises.yaml;config" ^
  --add-data "models/pose_landmarker_full.task;models" ^
  --hidden-import pyttsx3.drivers --hidden-import pyttsx3.drivers.sapi5 ^
  --exclude-module tkinter ^
  run_formcoach.py || exit /b 1

echo Built: dist\FormCoach\FormCoach.exe
