"""Tests for config path helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from cacten import config


def test_get_active_version_id_no_file(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"
    with patch.object(config, "CONFIG_FILE", cfg_file):
        assert config.get_active_version_id() is None


def test_get_active_version_id_missing_key(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("{}")
    with patch.object(config, "CONFIG_FILE", cfg_file):
        assert config.get_active_version_id() is None


def test_set_active_creates_file(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"
    with patch.object(config, "CONFIG_FILE", cfg_file):
        config.set_active_version_id("abc-123")
        assert cfg_file.exists()
        assert config.get_active_version_id() == "abc-123"


def test_set_active_updates_existing(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"
    with patch.object(config, "CONFIG_FILE", cfg_file):
        config.set_active_version_id("first")
        config.set_active_version_id("second")
        assert config.get_active_version_id() == "second"


def test_ensure_dirs(tmp_path: Path) -> None:
    qdrant = tmp_path / "qdrant"
    logs = tmp_path / "logs"
    with (
        patch.object(config, "QDRANT_PATH", qdrant),
        patch.object(config, "LOGS_DIR", logs),
    ):
        config.ensure_dirs()
    assert qdrant.exists()
    assert logs.exists()
