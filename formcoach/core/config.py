"""Load and save config/exercises.yaml."""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "exercises.yaml"


def load_config(path: str | Path | None = None) -> dict:
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def save_config(cfg: dict, path: str | Path | None = None) -> None:
    """Write the config back, keeping the explanatory header comment of the original file."""
    path = Path(path or DEFAULT_CONFIG)
    header = ""
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        header = "".join(line for line in _leading_comments(lines))
    body = yaml.safe_dump(cfg, sort_keys=False, default_flow_style=None, width=120)
    path.write_text(header + "\n" + body if header else body, encoding="utf-8")


def _leading_comments(lines):
    for line in lines:
        if line.startswith("#"):
            yield line
        elif line.strip():
            break


def merged(cfg: dict, overrides: dict) -> dict:
    """Deep-merge overrides (e.g. from the Settings screen) onto a copy of cfg."""
    out = copy.deepcopy(cfg)
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merged(out[k], v)
        else:
            out[k] = v
    return out
