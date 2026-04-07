"""Tests for manifest loading, validation, snapshotting, and file resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from cacten.manifest import (
    ManifestConfig,
    bootstrap_manifest,
    load_manifest,
    manifest_path,
    resolve_files,
    snapshot_manifest,
)

MINIMAL_TOML = """\
version = 1
include = ["*.md"]
"""

FULL_TOML = """\
version = 1
include = ["*.md", "src/**/*.py"]
exclude = ["**/__pycache__/**"]
"""


# ---------------------------------------------------------------------------
# ManifestConfig validation
# ---------------------------------------------------------------------------


def test_valid_manifest() -> None:
    m = ManifestConfig(version=1, include=["*.md"])
    assert m.version == 1
    assert m.exclude == []


def test_version_zero_rejected() -> None:
    with pytest.raises(Exception):
        ManifestConfig(version=0, include=["*.md"])


def test_empty_include_rejected() -> None:
    with pytest.raises(Exception):
        ManifestConfig(version=1, include=[])


# ---------------------------------------------------------------------------
# load_manifest
# ---------------------------------------------------------------------------


def test_load_manifest_success(tmp_path: Path) -> None:
    cacten_dir = tmp_path / ".cacten"
    cacten_dir.mkdir()
    (cacten_dir / "sources.toml").write_text(FULL_TOML)

    m = load_manifest(tmp_path)
    assert m.version == 1
    assert "*.md" in m.include
    assert "**/__pycache__/**" in m.exclude


def test_load_manifest_missing_raises(tmp_path: Path) -> None:
    (tmp_path / ".cacten").mkdir()
    with pytest.raises(FileNotFoundError):
        load_manifest(tmp_path)


def test_load_manifest_missing_version_raises(tmp_path: Path) -> None:
    cacten_dir = tmp_path / ".cacten"
    cacten_dir.mkdir()
    (cacten_dir / "sources.toml").write_text('include = ["*.md"]\n')

    with pytest.raises(Exception):
        load_manifest(tmp_path)


# ---------------------------------------------------------------------------
# bootstrap_manifest
# ---------------------------------------------------------------------------


def test_bootstrap_copies_example(tmp_path: Path) -> None:
    cacten_dir = tmp_path / ".cacten"
    cacten_dir.mkdir()
    (cacten_dir / "sources-example.toml").write_text(MINIMAL_TOML)

    created = bootstrap_manifest(tmp_path)

    assert created == manifest_path(tmp_path)
    assert created.exists()
    assert created.read_text() == MINIMAL_TOML


def test_bootstrap_raises_without_example(tmp_path: Path) -> None:
    (tmp_path / ".cacten").mkdir()
    with pytest.raises(FileNotFoundError):
        bootstrap_manifest(tmp_path)


# ---------------------------------------------------------------------------
# snapshot_manifest
# ---------------------------------------------------------------------------


def test_snapshot_creates_file(tmp_path: Path) -> None:
    cacten_dir = tmp_path / ".cacten"
    cacten_dir.mkdir()
    (cacten_dir / "sources.toml").write_text(MINIMAL_TOML)

    snap_path, digest = snapshot_manifest(tmp_path)

    assert snap_path.exists()
    assert snap_path.parent.name == "manifest-history"
    assert snap_path.read_text() == MINIMAL_TOML
    assert len(digest) == 64  # sha256 hex


def test_snapshot_filename_has_timestamp(tmp_path: Path) -> None:
    cacten_dir = tmp_path / ".cacten"
    cacten_dir.mkdir()
    (cacten_dir / "sources.toml").write_text(MINIMAL_TOML)

    snap_path, _ = snapshot_manifest(tmp_path)

    assert snap_path.name.startswith("sources_")
    assert snap_path.suffix == ".toml"


# ---------------------------------------------------------------------------
# resolve_files
# ---------------------------------------------------------------------------


def test_resolve_includes_matching_files(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("hello")
    (tmp_path / "b.md").write_text("world")
    (tmp_path / "c.py").write_text("code")

    m = ManifestConfig(version=1, include=["*.md"])
    files = resolve_files(m, tmp_path)

    names = {f.name for f in files}
    assert names == {"a.md", "b.md"}


def test_resolve_excludes_patterns(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("code")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "main.cpython-312.pyc").write_text("bytecode")

    m = ManifestConfig(version=1, include=["**/*.py", "**/*.pyc"], exclude=["**/__pycache__/**"])
    files = resolve_files(m, tmp_path)

    names = {f.name for f in files}
    assert "main.py" in names
    assert "main.cpython-312.pyc" not in names


def test_resolve_returns_sorted(tmp_path: Path) -> None:
    for name in ["c.md", "a.md", "b.md"]:
        (tmp_path / name).write_text("x")

    m = ManifestConfig(version=1, include=["*.md"])
    files = resolve_files(m, tmp_path)

    assert files == sorted(files)


def test_resolve_no_matches_returns_empty(tmp_path: Path) -> None:
    m = ManifestConfig(version=1, include=["*.md"])
    files = resolve_files(m, tmp_path)
    assert files == []


def test_resolve_skips_directories(tmp_path: Path) -> None:
    (tmp_path / "subdir").mkdir()
    (tmp_path / "file.md").write_text("content")

    m = ManifestConfig(version=1, include=["*"])
    files = resolve_files(m, tmp_path)

    assert all(f.is_file() for f in files)


def test_resolve_supports_absolute_include_patterns(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    notes = outside / "notes"
    notes.mkdir()
    target = notes / "doc.md"
    target.write_text("content")

    m = ManifestConfig(version=1, include=[str(outside / "**/*.md")])
    files = resolve_files(m, tmp_path)

    assert files == [target.resolve()]


def test_resolve_supports_parent_relative_patterns(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    sibling = tmp_path / "other-project"
    sibling.mkdir()
    target = sibling / "notes.md"
    target.write_text("content")

    m = ManifestConfig(version=1, include=["../other-project/*.md"])
    files = resolve_files(m, repo)

    assert files == [target.resolve()]


def test_resolve_supports_dot_prefixed_patterns(tmp_path: Path) -> None:
    cacten_dir = tmp_path / ".cacten"
    cacten_dir.mkdir()
    target = cacten_dir / "sources.toml"
    target.write_text('version = 1\ninclude = ["*.md"]\n')

    m = ManifestConfig(version=1, include=[".cacten/*.toml"])
    files = resolve_files(m, tmp_path)

    assert files == [target.resolve()]


def test_resolve_relative_exclude_applies_to_absolute_includes(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    drafts = outside / "drafts"
    drafts.mkdir(parents=True)
    keep = outside / "keep.md"
    drop = drafts / "drop.md"
    keep.write_text("keep")
    drop.write_text("drop")

    m = ManifestConfig(
        version=1,
        include=[str(outside / "**/*.md")],
        exclude=["**/drafts/**"],
    )
    files = resolve_files(m, tmp_path)

    assert files == [keep.resolve()]


def test_resolve_absolute_exclude_patterns(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    keep = outside / "keep.md"
    drop = outside / "drop.md"
    keep.write_text("keep")
    drop.write_text("drop")

    m = ManifestConfig(
        version=1,
        include=[str(outside / "*.md")],
        exclude=[str(outside / "drop.md")],
    )
    files = resolve_files(m, tmp_path)

    assert files == [keep.resolve()]
