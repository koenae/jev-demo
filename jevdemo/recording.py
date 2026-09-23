"""Record real API responses to `recordings/` and replay them without network."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from jevdemo.config import RECORDINGS_DIR, package_versions
from jevdemo.errors import RecordingMissingError

Mode = Literal["live", "record", "offline"]
SOURCE_LIVE = "live"
SOURCE_PLACEHOLDER = "synthetic-placeholder"


def parse_mode(*, record: bool = False, offline: bool = False) -> Mode:
    if record and offline:
        raise ValueError("--record and --offline are mutually exclusive.")
    return "record" if record else "offline" if offline else "live"


def recording_path(name: str) -> Path:
    return RECORDINGS_DIR / f"{name}.json"


def save_recording(name: str, data: dict[str, Any], *, source: str = SOURCE_LIVE) -> Path:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    envelope = {
        "demo": name,
        "source": source,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "versions": package_versions(),
        "data": data,
    }
    path = recording_path(name)
    path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_recording(name: str) -> dict[str, Any]:
    """Return the full envelope (`source`, `recorded_at`, `versions`, `data`)."""
    path = recording_path(name)
    if not path.exists():
        raise RecordingMissingError(
            f"No recording found at {path.relative_to(RECORDINGS_DIR.parent)}.",
            hint="Run the matching demo once with --record while online "
            "(see README: 'Offline-modus gebruiken').",
        )
    return json.loads(path.read_text(encoding="utf-8"))


def origin_of(envelope: dict[str, Any]) -> str:
    """Describe where a replayed result came from, for badges in CLI and slides."""
    if envelope.get("source") == SOURCE_PLACEHOLDER:
        return "placeholder"
    return "recording"


def is_placeholder(envelope: dict[str, Any]) -> bool:
    return envelope.get("source") == SOURCE_PLACEHOLDER
