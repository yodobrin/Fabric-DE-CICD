"""Tests for templates.py — staging preparation and placeholder replacement."""

import pytest
from pathlib import Path

from config import load_config, PlaceholderDef, WorkspaceConfig, FabricSettings
from templates import (
    prepare_staging,
    cleanup_staging,
    replace_in_file,
    replace_all_placeholders,
    WORKSHOP_TEMPLATE_DIR,
    STAGING_DIR,
)


class TestPrepareStaging:
    """Test staging directory creation."""

    def test_copies_template_dir(self, tmp_path):
        # Create a mock workshop_template/
        src = tmp_path / WORKSHOP_TEMPLATE_DIR
        src.mkdir()
        (src / "notebook.py").write_text("# hello")
        (src / "sub").mkdir()
        (src / "sub" / "file.json").write_text('{"key": "val"}')

        dst = prepare_staging(tmp_path)
        assert dst == tmp_path / STAGING_DIR
        assert (dst / "notebook.py").read_text() == "# hello"
        assert (dst / "sub" / "file.json").read_text() == '{"key": "val"}'

    def test_creates_parameter_yml_if_missing(self, tmp_path):
        src = tmp_path / WORKSHOP_TEMPLATE_DIR
        src.mkdir()
        (src / "file.txt").write_text("x")

        dst = prepare_staging(tmp_path)
        param = dst / "parameter.yml"
        assert param.exists()
        assert "find_replace" in param.read_text()

    def test_preserves_existing_parameter_yml(self, tmp_path):
        src = tmp_path / WORKSHOP_TEMPLATE_DIR
        src.mkdir()
        (src / "parameter.yml").write_text("custom: true\n")

        dst = prepare_staging(tmp_path)
        assert (dst / "parameter.yml").read_text() == "custom: true\n"

    def test_removes_previous_staging(self, tmp_path):
        src = tmp_path / WORKSHOP_TEMPLATE_DIR
        src.mkdir()
        (src / "a.txt").write_text("new")

        # Create pre-existing staging with stale file
        old_staging = tmp_path / STAGING_DIR
        old_staging.mkdir()
        (old_staging / "stale.txt").write_text("old")

        dst = prepare_staging(tmp_path)
        assert not (dst / "stale.txt").exists()
        assert (dst / "a.txt").exists()


class TestCleanupStaging:
    """Test staging cleanup."""

    def test_removes_staging_dir(self, tmp_path):
        staging = tmp_path / STAGING_DIR
        staging.mkdir()
        (staging / "file.txt").write_text("x")

        cleanup_staging(tmp_path)
        assert not staging.exists()

    def test_noop_if_no_staging(self, tmp_path):
        # Should not raise
        cleanup_staging(tmp_path)


class TestReplaceInFile:
    """Test single-file string replacement."""

    def test_replaces_match(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"id": "PLACEHOLDER_ID"}')
        replace_in_file(f, "PLACEHOLDER_ID", "real-guid-123")
        assert f.read_text() == '{"id": "real-guid-123"}'

    def test_no_match_no_change(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"id": "something-else"}')
        replace_in_file(f, "PLACEHOLDER_ID", "real-guid-123")
        assert f.read_text() == '{"id": "something-else"}'

    def test_empty_old_is_noop(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text("content")
        replace_in_file(f, "", "replacement")
        assert f.read_text() == "content"

    def test_skips_binary_file(self, tmp_path):
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        # Should not crash
        replace_in_file(f, "PNG", "JPG")


class TestReplaceAllPlaceholders:
    """Test full placeholder replacement across staging directory."""

    def test_replaces_workspace_id(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        f = staging / "config.json"
        f.write_text('{"workspace": "00000000-0000-0000-0000-000000000001"}')

        cfg = WorkspaceConfig()
        cfg.placeholders = PlaceholderDef(
            workspace_id="00000000-0000-0000-0000-000000000001",
            bronze_lakehouse_id="00000000-0000-0000-0000-000000000002",
            silver_lakehouse_id="",
        )

        replace_all_placeholders(
            staging, cfg,
            workspace_id="real-ws-id",
            resolved_ids={"lakehouse_bronze": "real-bronze-id"},
        )
        assert "real-ws-id" in f.read_text()
        assert "00000000-0000-0000-0000-000000000001" not in f.read_text()

    def test_replaces_multiple_placeholders(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        f = staging / "notebook.py"
        f.write_text(
            'ws = "PH_WS"\n'
            'bronze = "PH_BRONZE"\n'
            'silver = "PH_SILVER"\n'
        )

        cfg = WorkspaceConfig()
        cfg.placeholders = PlaceholderDef(
            workspace_id="PH_WS",
            bronze_lakehouse_id="PH_BRONZE",
            silver_lakehouse_id="PH_SILVER",
        )

        replace_all_placeholders(
            staging, cfg,
            workspace_id="ws-real",
            resolved_ids={"lakehouse_bronze": "bronze-real", "lakehouse_silver": "silver-real"},
        )
        content = f.read_text()
        assert "ws-real" in content
        assert "bronze-real" in content
        assert "silver-real" in content
        assert "PH_" not in content

    def test_handles_nested_files(self, tmp_path):
        staging = tmp_path / "staging"
        (staging / "sub" / "deep").mkdir(parents=True)
        f = staging / "sub" / "deep" / "file.json"
        f.write_text('{"lakehouse": "PH_BRONZE"}')

        cfg = WorkspaceConfig()
        cfg.placeholders = PlaceholderDef(bronze_lakehouse_id="PH_BRONZE")

        replace_all_placeholders(
            staging, cfg,
            workspace_id="",
            resolved_ids={"lakehouse_bronze": "real-id"},
        )
        assert "real-id" in f.read_text()

    def test_skips_binary_files(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        f = staging / "image.png"
        f.write_bytes(b"\x89PNG" + b"\x00" * 50)

        cfg = WorkspaceConfig()
        cfg.placeholders = PlaceholderDef(workspace_id="PH_WS")

        # Should not crash
        replace_all_placeholders(staging, cfg, workspace_id="x", resolved_ids={})
