# Evaluation on the dataset

Full engine (smoothing, rep state machine, form rules, scoring) run over every cached clip by `tools/evaluate.py`. Expected counts: `scipy.signal.find_peaks` reference (`tools/reference_counts.py`). Form: a clip is predicted *bad* when at least half of its reps have a fault; labels come from the dataset filenames. All subjects are included here - see `reports/tuning.md` for held-out-subject numbers.

| exercise | clips | exact count | within +-1 | MAE | rep-count accuracy | good clips correct | bad clips correct | form accuracy |
|---|---|---|---|---|---|---|---|---|
| push_up | 48 | 38 | 45 | 0.27 | 97.6% | 18/24 | 14/24 | 67% |
| squat | 50 | 39 | 46 | 1.04 | 92.5% | 25/25 | 11/25 | 72% |
| bicep_curl | 50 | 44 | 49 | 0.14 | 98.4% | 15/25 | 19/25 | 68% |
| shoulder_press | 50 | 39 | 44 | 0.70 | 93.9% | 21/25 | 11/25 | 64% |
