"""Download the public datasets FormCoach uses for tuning, testing and demos.

Sources
-------
1. Mendeley Data "A Multi-View Raw Video Dataset of Seven Fitness Exercises with
   Good/Bad Form Labels" (CC BY 4.0) - push-up, squat, bicep curl, shoulder press.
   Downloaded through the public Mendeley API (no key needed).
2. Kaggle "Workout/Exercises Video" (hasyimabdillah/workoutfitness-video) - used
   for pull-ups, which the Mendeley set does not contain. Needs Kaggle
   credentials (~/.kaggle/access_token, ~/.kaggle/kaggle.json, KAGGLE_API_TOKEN or
   KAGGLE_USERNAME / KAGGLE_KEY).

Everything goes into data/raw/ (git-ignored). The script is re-runnable: files that
already exist with the expected size are skipped.

Usage:
    python scripts/download_data.py                 # everything
    python scripts/download_data.py --only mendeley
    python scripts/download_data.py --max-per-folder 5   # quick small subset
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

MENDELEY_ID = "kgbb3yn47p"
MENDELEY_VERSION = 2
MENDELEY_API = "https://data.mendeley.com/public-api/datasets"

# (dataset exercise folder, camera view) pairs that FormCoach needs. Each exercise
# is downloaded in the camera view the app recommends for it.
MENDELEY_SELECTION = [
    ("push_up", "side"),
    ("squat", "side"),
    ("bicep_curl", "side"),
    ("shoulder", "front"),
]

KAGGLE_DATASET = "hasyimabdillah/workoutfitness-video"
# Folder names inside the Kaggle archive we keep (matched case-insensitively).
KAGGLE_CLASSES = ["pull up", "push-up", "squat", "barbell biceps curl", "shoulder press"]


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def download_file(url: str, dest: Path, expected_size: int | None = None, retries: int = 3) -> bool:
    """Download url to dest. Returns True if downloaded, False if skipped.

    The file is written to a .part file first and only renamed when its size matches
    (Mendeley occasionally answers with a short JSON error instead of the file).
    """
    if dest.exists() and (expected_size is None or dest.stat().st_size == expected_size):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
        if expected_size is None or tmp.stat().st_size == expected_size:
            tmp.replace(dest)
            return True
        time.sleep(2 * attempt)
    tmp.unlink(missing_ok=True)
    raise requests.RequestException(f"size mismatch after {retries} attempts")


# --------------------------------------------------------------------------- Mendeley
def mendeley_folders() -> dict[str, str]:
    """Return {"Dataset Exercise-wise/push_up/good/side": folder_id, ...}."""
    url = f"{MENDELEY_API}/{MENDELEY_ID}/folders/{MENDELEY_VERSION}?version={MENDELEY_VERSION}"
    folders = requests.get(url, timeout=60).json()
    by_id = {f["id"]: f for f in folders}

    def path(f: dict) -> str:
        parts = []
        while f:
            parts.append(f["name"])
            f = by_id.get(f.get("parent_id"))
        return "/".join(reversed(parts))

    return {path(f): f["id"] for f in folders}


def mendeley_files(folder_id: str) -> list[dict]:
    url = f"{MENDELEY_API}/{MENDELEY_ID}/files?folder_id={folder_id}&version={MENDELEY_VERSION}"
    return requests.get(url, timeout=60).json()


def download_mendeley(max_per_folder: int | None, workers: int = 8) -> None:
    print("== Mendeley: Multi-View Fitness Exercise Video Dataset (CC BY 4.0)")
    try:
        folders = mendeley_folders()
    except (requests.RequestException, ValueError) as exc:
        print(f"!! Could not reach the Mendeley API ({exc}).")
        print_mendeley_manual_steps()
        return
    total_new = total_skip = 0
    for exercise, view in MENDELEY_SELECTION:
        for quality in ("good", "bad"):
            key = f"Dataset Exercise-wise/{exercise}/{quality}/{view}"
            folder_id = folders.get(key)
            if folder_id is None:
                print(f"!! folder not found: {key}")
                continue
            files = sorted(mendeley_files(folder_id), key=lambda f: f["filename"])
            if max_per_folder:
                files = files[:max_per_folder]
            out_dir = RAW / "mendeley" / exercise / quality / view
            size = sum(f["size"] for f in files)
            print(f"-- {exercise}/{quality}/{view}: {len(files)} videos ({human(size)})")
            def fetch(f: dict) -> tuple[str, str]:
                dest = out_dir / f["filename"]
                try:
                    new = download_file(f["content_details"]["download_url"], dest, f["size"])
                except requests.RequestException as exc:
                    return f["filename"], f"FAILED: {exc}"
                return f["filename"], "downloaded" if new else "exists, skipped"

            # Mendeley serves each file slowly, so several downloads run in parallel.
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for i, (name, status) in enumerate(pool.map(fetch, files), 1):
                    total_new += status == "downloaded"
                    total_skip += status.startswith("exists")
                    print(f"   [{i}/{len(files)}] {name} ({status})", flush=True)
    print(f"== Mendeley done: {total_new} downloaded, {total_skip} already present\n")


def print_mendeley_manual_steps() -> None:
    print(
        "   Manual download:\n"
        "   1. Open https://data.mendeley.com/datasets/kgbb3yn47p/2\n"
        "   2. Click 'Download All' and unzip it.\n"
        "   3. Copy 'Dataset Exercise-wise/<exercise>/<good|bad>/<view>' folders to\n"
        f"      {RAW / 'mendeley'}/<exercise>/<good|bad>/<view>/\n"
        "      for: push_up/side, squat/side, bicep_curl/side, shoulder/front"
    )


# --------------------------------------------------------------------------- Kaggle
def kaggle_credentials_present() -> bool:
    if os.environ.get("KAGGLE_API_TOKEN"):
        return True
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    home = Path.home() / ".kaggle"
    return (home / "access_token").exists() or (home / "kaggle.json").exists()


def download_kaggle(max_per_folder: int | None) -> None:
    print(f"== Kaggle: {KAGGLE_DATASET} (pull-ups and extra clips)")
    out_dir = RAW / "kaggle_workout"
    marker = out_dir / ".complete"
    if marker.exists():
        print("   already downloaded, skipped\n")
        return
    if not kaggle_credentials_present():
        print(
            "!! Kaggle credentials not found - pull-up clips skipped.\n"
            "   1. Sign in at https://www.kaggle.com/settings -> 'API' -> 'Generate New Token' and copy it\n"
            "   2. mkdir -p ~/.kaggle && pbpaste > ~/.kaggle/access_token && chmod 600 ~/.kaggle/access_token\n"
            "      (Linux/Windows: save the token text to ~/.kaggle/access_token; a legacy kaggle.json also works)\n"
            "   3. Re-run: python scripts/download_data.py --only kaggle\n"
        )
        return
    kaggle = shutil.which("kaggle") or str(Path(sys.executable).parent / "kaggle")
    zip_dir = RAW / "_kaggle_zip"
    zip_dir.mkdir(parents=True, exist_ok=True)
    print("   downloading archive (this can take a few minutes)...", flush=True)
    result = subprocess.run([kaggle, "datasets", "download", "-d", KAGGLE_DATASET, "-p", str(zip_dir)])
    if result.returncode != 0:
        print(
            "!! Kaggle download failed. Search for an equivalent dataset with:\n"
            '   kaggle datasets list -s "workout exercises video"\n'
            "   and update KAGGLE_DATASET in scripts/download_data.py"
        )
        return
    zips = list(zip_dir.glob("*.zip"))
    wanted = [c.lower() for c in KAGGLE_CLASSES]
    kept = 0
    for zpath in zips:
        with zipfile.ZipFile(zpath) as zf:
            per_class: dict[str, int] = {}
            for name in zf.namelist():
                parts = Path(name).parts
                if len(parts) < 2 or name.endswith("/"):
                    continue
                cls = parts[-2].lower()
                if cls not in wanted:
                    continue
                if max_per_folder and per_class.get(cls, 0) >= max_per_folder:
                    continue
                per_class[cls] = per_class.get(cls, 0) + 1
                dest = out_dir / cls.replace(" ", "_") / Path(name).name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                kept += 1
            for cls, n in sorted(per_class.items()):
                print(f"   {cls}: {n} clips")
    shutil.rmtree(zip_dir, ignore_errors=True)
    marker.write_text(json.dumps({"dataset": KAGGLE_DATASET, "clips": kept}))
    print(f"== Kaggle done: {kept} clips kept\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=["mendeley", "kaggle"], help="download only one source")
    ap.add_argument("--max-per-folder", type=int, default=None, help="limit videos per class/quality folder")
    ap.add_argument("--workers", type=int, default=8, help="parallel downloads")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    if args.only in (None, "mendeley"):
        download_mendeley(args.max_per_folder, args.workers)
    if args.only in (None, "kaggle"):
        download_kaggle(args.max_per_folder)


if __name__ == "__main__":
    main()
