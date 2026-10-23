"""User-level app settings stored as JSON in the app data folder (no Qt dependency)."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


def app_data_dir() -> Path:
    """Per-user folder for the database, settings and exports (overridable with FORMCOACH_HOME)."""
    if os.environ.get("FORMCOACH_HOME"):
        d = Path(os.environ["FORMCOACH_HOME"])
    elif sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "FormCoach"
    elif sys.platform == "win32":
        d = Path(os.environ.get("APPDATA", Path.home())) / "FormCoach"
    else:
        d = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "formcoach"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class AppSettings:
    camera_index: int = 0
    width: int = 1280
    height: int = 720
    voice_on: bool = True
    voice_rate: int = 175
    theme: str = "dark"
    last_user_id: int | None = None
    # Threshold overrides edited in Settings > Advanced, merged over config/exercises.yaml.
    overrides: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "AppSettings":
        path = path or app_data_dir() / "settings.json"
        try:
            data = json.loads(path.read_text())
            known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            return cls(**known)
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self, path: Path | None = None) -> None:
        path = path or app_data_dir() / "settings.json"
        path.write_text(json.dumps(asdict(self), indent=1))
