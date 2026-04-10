"""Tests for KB version registry."""

from pathlib import Path
from unittest.mock import patch

import pytest

from cacten import versions


@pytest.fixture()
def tmp_versions_file(tmp_path: Path) -> Path:
    return tmp_path / "versions.json"


@pytest.fixture()
def tmp_version_files_dir(tmp_path: Path) -> Path:
    return tmp_path / "version-files"


def test_create_and_list(tmp_versions_file: Path) -> None:
    with (
        patch.object(versions, "VERSIONS_FILE", tmp_versions_file),
        patch.object(versions, "VERSION_FILES_DIR", tmp_versions_file.parent / "version-files"),
    ):
        v = versions.create_version(
            document_count=1,
            chunk_count=10,
            embedding_model="nomic-embed-text",
        )
        assert v.version_number == 1
        assert v.chunk_count == 10

        all_v = versions.list_versions()
        assert len(all_v) == 1
        assert all_v[0].version_id == v.version_id


def test_monotonic_numbering(tmp_versions_file: Path) -> None:
    with (
        patch.object(versions, "VERSIONS_FILE", tmp_versions_file),
        patch.object(versions, "VERSION_FILES_DIR", tmp_versions_file.parent / "version-files"),
    ):
        v1 = versions.create_version(1, 5, "nomic-embed-text")
        v2 = versions.create_version(1, 8, "nomic-embed-text")
        assert v2.version_number == v1.version_number + 1


def test_delete(tmp_versions_file: Path) -> None:
    with (
        patch.object(versions, "VERSIONS_FILE", tmp_versions_file),
        patch.object(versions, "VERSION_FILES_DIR", tmp_versions_file.parent / "version-files"),
    ):
        v = versions.create_version(1, 5, "nomic-embed-text")
        deleted = versions.delete_version(v.version_id)
        assert deleted is True
        assert versions.list_versions() == []


def test_delete_nonexistent(tmp_versions_file: Path) -> None:
    with (
        patch.object(versions, "VERSIONS_FILE", tmp_versions_file),
        patch.object(versions, "VERSION_FILES_DIR", tmp_versions_file.parent / "version-files"),
    ):
        assert versions.delete_version("does-not-exist") is False


def test_custom_version_id(tmp_versions_file: Path) -> None:
    with (
        patch.object(versions, "VERSIONS_FILE", tmp_versions_file),
        patch.object(versions, "VERSION_FILES_DIR", tmp_versions_file.parent / "version-files"),
    ):
        custom_id = "aaaaaaaa-0000-0000-0000-000000000000"
        v = versions.create_version(1, 5, "nomic-embed-text", version_id=custom_id)
        assert v.version_id == custom_id


def test_save_and_load_version_files(
    tmp_versions_file: Path,
    tmp_version_files_dir: Path,
) -> None:
    from cacten.models import VersionFileRecord

    records = [
        VersionFileRecord(
            path="/tmp/file.md",
            file_hash="abc123",
            file_size=42,
            content_type="markdown",
            embedding_model="nomic-embed-text",
            sparse_encoder_version=2,
            chunk_profile="default",
            chunk_count=2,
            chunk_ids=["c1", "c2"],
        )
    ]

    with (
        patch.object(versions, "VERSIONS_FILE", tmp_versions_file),
        patch.object(versions, "VERSION_FILES_DIR", tmp_version_files_dir),
    ):
        versions.save_version_files("v1", records)
        loaded = versions.load_version_files("v1")

    assert loaded == records
