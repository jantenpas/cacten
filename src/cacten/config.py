"""Cacten config — paths and active KB version."""

import json
from pathlib import Path

CACTEN_DIR = Path.home() / ".cacten"
KB_DIR = CACTEN_DIR / "kb"
QDRANT_PATH = KB_DIR / "qdrant"
VERSIONS_FILE = KB_DIR / "versions.json"
CONFIG_FILE = CACTEN_DIR / "config.json"
LOGS_DIR = CACTEN_DIR / "logs" / "sessions"

COLLECTION_NAME = "personal_kb"
EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768


def ensure_dirs() -> None:
    QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def get_active_version_id() -> str | None:
    if not CONFIG_FILE.exists():
        return None
    data: dict[str, object] = json.loads(CONFIG_FILE.read_text())
    v = data.get("active_version_id")
    return str(v) if v is not None else None


def set_active_version_id(version_id: str) -> None:
    data: dict[str, object] = {}
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text())
    data["active_version_id"] = version_id
    CONFIG_FILE.write_text(json.dumps(data, indent=2))
