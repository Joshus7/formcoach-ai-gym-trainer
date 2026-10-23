"""Load and save config/exercises.yaml."""
from __future__ import annotations

import copy
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "exercises.yaml"


def load_config(path: str | Path | None = None) -> dict:
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def save_config(cfg: dict, path: str | Path | None = None) -> None:
    """Write cfg back to the YAML file.

    Values are updated in place line by line so the comments in the file survive;
    if the structure no longer matches (new keys), the whole file is re-dumped.
    """
    path = Path(path or DEFAULT_CONFIG)
    if path.exists():
        text = _update_in_place(path.read_text(encoding="utf-8"), cfg)
        if text is not None and yaml.safe_load(text) == cfg:
            path.write_text(text, encoding="utf-8")
            return
    path.write_text(yaml.safe_dump(cfg, sort_keys=False, default_flow_style=None, width=120), encoding="utf-8")


_LINE = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z_][\w]*):(?P<sp> *)(?P<value>[^#]*?)(?P<rest> *#.*)?$")


def _update_in_place(text: str, cfg: dict) -> str | None:
    out, stack = [], []  # stack of (indent, key)
    for line in text.splitlines():
        m = _LINE.match(line)
        if not m or line.lstrip().startswith("#"):
            out.append(line)
            continue
        indent = len(m["indent"])
        while stack and stack[-1][0] >= indent:
            stack.pop()
        keys = [k for _, k in stack] + [m["key"]]
        value = m["value"]
        if value == "":
            stack.append((indent, m["key"]))
            out.append(line)
            continue
        node = cfg
        try:
            for k in keys:
                node = node[k]
        except (KeyError, TypeError):
            return None
        new_value = _dump_value(node)
        out.append(f"{m['indent']}{m['key']}:{m['sp'] or ' '}{new_value}{m['rest'] or ''}")
    return "\n".join(out) + "\n"


def _dump_value(v) -> str:
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {_dump_value(x)}" for k, x in v.items()) + "}"
    if isinstance(v, list):
        return "[" + ", ".join(_dump_value(x) for x in v) + "]"
    return yaml.safe_dump(v, default_flow_style=True).strip().removesuffix("...").strip()


def merged(cfg: dict, overrides: dict) -> dict:
    """Deep-merge overrides (e.g. from the Settings screen) onto a copy of cfg."""
    out = copy.deepcopy(cfg)
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merged(out[k], v)
        else:
            out[k] = v
    return out
