"""Project-local manifest loading, validation, and file resolution."""

from __future__ import annotations

import glob as glob_module
import hashlib
import shutil
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

MANIFEST_FILENAME = "sources.toml"
MANIFEST_EXAMPLE_FILENAME = "sources-example.toml"
MANIFEST_HISTORY_DIR = "manifest-history"
PROJECT_MANIFEST_DIR = ".cacten"


class ManifestConfig(BaseModel):
    version: int
    include: list[str]
    exclude: list[str] = Field(default_factory=list)

    @field_validator("version")
    @classmethod
    def version_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("version must be a positive integer")
        return v

    @field_validator("include")
    @classmethod
    def include_must_not_be_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("include must contain at least one pattern")
        return v


def manifest_path(project_root: Path) -> Path:
    return project_root / PROJECT_MANIFEST_DIR / MANIFEST_FILENAME


def example_manifest_path(project_root: Path) -> Path:
    return project_root / PROJECT_MANIFEST_DIR / MANIFEST_EXAMPLE_FILENAME


def load_manifest(project_root: Path) -> ManifestConfig:
    """Load and validate .cacten/sources.toml from the project root.

    Raises FileNotFoundError if the manifest does not exist.
    Raises ValidationError if the TOML parses but fails the ManifestConfig schema.
    """
    path = manifest_path(project_root)
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("rb") as f:
        raw = tomllib.load(f)
    return ManifestConfig.model_validate(raw)


def bootstrap_manifest(project_root: Path) -> Path:
    """Copy sources-example.toml → sources.toml if the example exists.

    Returns the path to the newly created manifest.
    Raises FileNotFoundError if the example does not exist either.
    """
    example = example_manifest_path(project_root)
    if not example.exists():
        raise FileNotFoundError(
            f"No manifest found at {manifest_path(project_root)} "
            f"and no example file found at {example}. "
            "Create .cacten/sources-example.toml or run `cacten init`."
        )
    dest = manifest_path(project_root)
    dest.write_text(example.read_text())
    return dest


def snapshot_manifest(project_root: Path) -> tuple[Path, str]:
    """Copy the live manifest into manifest-history/ with a UTC timestamp filename.

    Returns (snapshot_path, sha256_hex) so callers can record provenance without
    re-reading the file.
    """
    src = manifest_path(project_root)
    history_dir = project_root / PROJECT_MANIFEST_DIR / MANIFEST_HISTORY_DIR
    history_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    dest = history_dir / f"sources_{timestamp}.toml"
    shutil.copy2(src, dest)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    return dest, digest


def _expand_glob_pattern(pattern: str, project_root: Path) -> set[Path]:
    """Expand a manifest glob into resolved file paths.

    Relative patterns are anchored to project_root. Absolute patterns are used
    as-is. Only regular files are returned.
    """
    raw_pattern = pattern if Path(pattern).is_absolute() else str(project_root / pattern)
    return {
        Path(match).resolve()
        for match in glob_module.glob(raw_pattern, recursive=True)
        if Path(match).is_file()
    }


def _matches_exclude_pattern(path: Path, pattern: str, project_root: Path) -> bool:
    """Return True when an included path should be removed by an exclude pattern."""
    if path.is_relative_to(project_root) and path.relative_to(project_root).match(pattern):
        return True
    return path.match(pattern)


def resolve_files(manifest: ManifestConfig, project_root: Path) -> list[Path]:
    """Expand include globs, apply exclude patterns, return sorted unique paths.

    Patterns may be absolute or relative (resolved against project_root).
    Only regular files are returned (directories are skipped).
    """
    root = project_root.resolve()

    included: set[Path] = set()
    for pattern in manifest.include:
        included.update(_expand_glob_pattern(pattern, root))

    excluded: set[Path] = set()
    for exc_pattern in manifest.exclude:
        excluded.update(_expand_glob_pattern(exc_pattern, root))
        for path in included:
            if _matches_exclude_pattern(path, exc_pattern, root):
                excluded.add(path)

    return sorted(included - excluded)
