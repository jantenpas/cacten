"""KB version registry — backed by versions.json."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from cacten.config import VERSIONS_FILE
from cacten.models import KBVersion


def _load() -> list[KBVersion]:
    if not VERSIONS_FILE.exists():
        return []
    raw: list[dict[str, object]] = json.loads(VERSIONS_FILE.read_text())
    return [KBVersion.model_validate(r) for r in raw]


def _save(versions: list[KBVersion]) -> None:
    VERSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSIONS_FILE.write_text(
        json.dumps([v.model_dump(mode="json") for v in versions], indent=2)
    )


def list_versions() -> list[KBVersion]:
    return _load()


def create_version(
    document_count: int,
    chunk_count: int,
    embedding_model: str,
    notes: str | None = None,
    version_id: str | None = None,
) -> KBVersion:
    versions = _load()
    next_number = max((v.version_number for v in versions), default=0) + 1
    version = KBVersion(
        version_id=version_id or str(uuid4()),
        version_number=next_number,
        created_at=datetime.now(tz=UTC),
        document_count=document_count,
        chunk_count=chunk_count,
        embedding_model=embedding_model,
        notes=notes,
    )
    versions.append(version)
    _save(versions)
    return version


def get_version(version_id: str) -> KBVersion | None:
    return next((v for v in _load() if v.version_id == version_id), None)


def delete_version(version_id: str) -> bool:
    versions = _load()
    new_versions = [v for v in versions if v.version_id != version_id]
    if len(new_versions) == len(versions):
        return False
    _save(new_versions)
    return True
