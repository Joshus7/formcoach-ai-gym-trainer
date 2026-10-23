# FormCoach: AI Gym Trainer

Desktop AI personal trainer: counts reps, checks your form in real time and talks you through every set.

> Work in progress - full documentation arrives in Phase 6.

## Quick start
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/download_models.py
python scripts/download_data.py
python tools/preview.py --dataset push_up     # skeleton overlay on a dataset clip
python tools/preview.py --webcam 0            # skeleton overlay on the webcam
```
