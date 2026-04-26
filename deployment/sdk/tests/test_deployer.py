"""Tests for deployer.py — phased orchestration logic."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from config import load_config, WorkspaceConfig, ItemDef, PhaseDef
from state import WorkspaceState, Resource


class TestDeployerInit:
    """Test Deployer construction."""

    @patch("deployer.prepare_staging")
    def test_init_sets_fields(self, mock_staging, sample_config_yaml):
        from deployer import Deployer

        mock_staging.return_value = Path("/tmp/staging")

        client = MagicMock()
        cfg = load_config(sample_config_yaml)
        deployer = Deployer(
            client=client,
            workspace_id="ws-1",
            cfg=cfg,
            base_dir=Path("/tmp"),
            on_exists="skip",
        )
        assert deployer.workspace_id == "ws-1"
        assert deployer.on_exists == "skip"
        assert deployer.state is None


class TestEnsureLakehouse:
    """Test lakehouse creation logic."""

    @patch("deployer.prepare_staging")
    def test_skip_existing(self, mock_staging, sample_config_yaml, capsys):
        from deployer import Deployer

        mock_staging.return_value = Path("/tmp/staging")

        client = MagicMock()
        cfg = load_config(sample_config_yaml)
        deployer = Deployer(client=client, workspace_id="ws-1", cfg=cfg,
                           base_dir=Path("/tmp"), on_exists="skip")

        state = WorkspaceState(workspace_id="ws-1")
        state.resources = [Resource("Item", "LH.Lakehouse", "lakehouse_bronze", exists=True)]
        state.item_ids = {"lakehouse_bronze": "id-1"}
        deployer.state = state

        deployer._ensure_lakehouse(cfg.items["lakehouse_bronze"])
        out = capsys.readouterr().out
        assert "[skip]" in out
        client.create_lakehouse.assert_not_called()

    @patch("deployer.prepare_staging")
    def test_create_missing(self, mock_staging, sample_config_yaml, capsys):
        from deployer import Deployer

        mock_staging.return_value = Path("/tmp/staging")

        client = MagicMock()
        cfg = load_config(sample_config_yaml)
        deployer = Deployer(client=client, workspace_id="ws-1", cfg=cfg,
                           base_dir=Path("/tmp"), on_exists="skip")

        state = WorkspaceState(workspace_id="ws-1")
        state.resources = [Resource("Item", "LH.Lakehouse", "lakehouse_bronze", exists=False)]
        state.item_ids = {}
        deployer.state = state

        deployer._ensure_lakehouse(cfg.items["lakehouse_bronze"])
        client.create_lakehouse.assert_called_once_with(
            "ws-1", "Lakehouse_Bronze", enable_schemas=True)


class TestEnsureImport:
    """Test item import logic with different on_exists strategies."""

    @patch("deployer.prepare_staging")
    def test_skip_existing_item(self, mock_staging, sample_config_yaml, capsys):
        from deployer import Deployer

        mock_staging.return_value = Path("/tmp/staging")

        client = MagicMock()
        cfg = load_config(sample_config_yaml)
        deployer = Deployer(client=client, workspace_id="ws-1", cfg=cfg,
                           base_dir=Path("/tmp"), on_exists="skip")

        state = WorkspaceState(workspace_id="ws-1")
        state.resources = [Resource("Item", "NB.Notebook", "nb_transformations", exists=True)]
        state.item_ids = {"nb_transformations": "id-nb"}
        deployer.state = state

        deployer._ensure_import(cfg.items["nb_transformations"])
        out = capsys.readouterr().out
        assert "[skip]" in out

    @patch("deployer.prepare_staging")
    def test_update_existing_notebook(self, mock_staging, sample_config_yaml, capsys):
        from deployer import Deployer

        mock_staging.return_value = Path("/tmp/staging")

        client = MagicMock()
        cfg = load_config(sample_config_yaml)
        deployer = Deployer(client=client, workspace_id="ws-1", cfg=cfg,
                           base_dir=Path("/tmp"), on_exists="update")

        state = WorkspaceState(workspace_id="ws-1")
        state.resources = [Resource("Item", "NB.Notebook", "nb_transformations", exists=True)]
        state.item_ids = {"nb_transformations": "id-nb"}
        deployer.state = state

        with patch.object(deployer, "_import_via_fabric_cicd") as mock_import:
            deployer._ensure_import(cfg.items["nb_transformations"])
            mock_import.assert_called_once_with("Notebook")


class TestDoRunJobs:
    """Test job execution orchestration."""

    @patch("deployer.prepare_staging")
    def test_skips_if_item_not_found(self, mock_staging, sample_config_yaml, capsys):
        from deployer import Deployer

        mock_staging.return_value = Path("/tmp/staging")

        client = MagicMock()
        cfg = load_config(sample_config_yaml)
        deployer = Deployer(client=client, workspace_id="ws-1", cfg=cfg,
                           base_dir=Path("/tmp"), on_exists="skip")

        state = WorkspaceState(workspace_id="ws-1")
        state.resources = []
        state.item_ids = {}
        deployer.state = state

        deployer._do_run_jobs(["copyjob_diabetes"])
        out = capsys.readouterr().out
        assert "[skip]" in out
        client.run_job.assert_not_called()

    @patch("deployer.prepare_staging")
    def test_runs_job_with_correct_type(self, mock_staging, sample_config_yaml, capsys):
        from deployer import Deployer

        mock_staging.return_value = Path("/tmp/staging")

        client = MagicMock()
        client.run_job.return_value = "job-run-id-123"
        client.wait_for_job.return_value = {"status": "Completed"}
        cfg = load_config(sample_config_yaml)
        deployer = Deployer(client=client, workspace_id="ws-1", cfg=cfg,
                           base_dir=Path("/tmp"), on_exists="skip")

        state = WorkspaceState(workspace_id="ws-1")
        state.resources = [Resource("Item", "CJ.CopyJob", "copyjob_diabetes", exists=True)]
        state.item_ids = {"copyjob_diabetes": "cj-id"}
        deployer.state = state

        deployer._do_run_jobs(["copyjob_diabetes"])
        client.run_job.assert_called_once_with("ws-1", "cj-id", job_type="CopyJob")
