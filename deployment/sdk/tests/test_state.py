"""Tests for state.py — desired-state engine logic."""

import pytest
from unittest.mock import MagicMock, patch

from config import load_config, WorkspaceConfig, ItemDef, DataExpectation, ShortcutDef
from state import Resource, WorkspaceState, assess, compute_actions, display


class TestResource:
    """Test the Resource dataclass."""

    def test_to_dict(self):
        r = Resource(category="Item", label="LH.Lakehouse", key="lh_bronze", exists=True, action="skip")
        d = r.to_dict()
        assert d == {"category": "Item", "label": "LH.Lakehouse", "key": "lh_bronze",
                     "exists": True, "action": "skip"}


class TestWorkspaceState:
    """Test WorkspaceState accessors."""

    def _make_state(self):
        s = WorkspaceState(workspace_id="ws-1", workspace_name="Test")
        s.resources = [
            Resource("Item", "LH_Bronze.Lakehouse", "lakehouse_bronze", exists=True, action="skip"),
            Resource("Item", "NB.Notebook", "nb_transformations", exists=False, action="create"),
            Resource("Data", "bronze:t2", "data_t2", exists=True, action="skip"),
            Resource("Data", "bronze:t3_dev", "data_t3_dev", exists=False, action="blocked"),
            Resource("Shortcut", "bronze:t3", "sc_t3", exists=False, action="blocked"),
        ]
        s.item_ids = {"lakehouse_bronze": "id-1", "nb_transformations": ""}
        return s

    def test_get_existing(self):
        s = self._make_state()
        r = s.get("lakehouse_bronze")
        assert r is not None
        assert r.exists is True

    def test_get_missing_key(self):
        s = self._make_state()
        assert s.get("nonexistent") is None

    def test_is_done(self):
        s = self._make_state()
        assert s.is_done("lakehouse_bronze") is True
        assert s.is_done("nb_transformations") is False
        assert s.is_done("nonexistent") is False

    def test_item_id(self):
        s = self._make_state()
        assert s.item_id("lakehouse_bronze") == "id-1"
        assert s.item_id("nb_transformations") == ""
        assert s.item_id("nonexistent") == ""

    def test_missing_count(self):
        s = self._make_state()
        assert s.missing_count == 3  # nb, data_t3_dev, sc_t3

    def test_all_done_false(self):
        s = self._make_state()
        assert s.all_done is False

    def test_all_done_true(self):
        s = WorkspaceState()
        s.resources = [Resource("Item", "X", "x", exists=True)]
        assert s.all_done is True

    def test_to_dict(self):
        s = self._make_state()
        d = s.to_dict()
        assert d["workspace_id"] == "ws-1"
        assert d["summary"]["total"] == 5
        assert d["summary"]["missing"] == 3


class TestComputeActions:
    """Test compute_actions() logic — the decision engine."""

    def _make_config_and_state(self):
        """Build a minimal config and state for testing actions."""
        from config import WorkspaceConfig, ItemDef, DataExpectation, ShortcutDef

        cfg = WorkspaceConfig()
        cfg.items = {
            "lh_bronze": ItemDef(key="lh_bronze", type="Lakehouse", display_name="LH_Bronze"),
            "nb_trans": ItemDef(key="nb_trans", type="Notebook", display_name="Transformations"),
            "cj_diab": ItemDef(key="cj_diab", type="CopyJob", display_name="CopyJob_Diabetes"),
        }
        cfg.data_expectations = {
            "data_t2": DataExpectation(key="data_t2", lakehouse="lh_bronze", table="t2",
                                       produced_by=["cj_diab"]),
            "data_t3": DataExpectation(key="data_t3", lakehouse="lh_bronze", table="t3_dev",
                                       produced_by=["nb_trans"]),
        }
        cfg.shortcuts = {
            "sc_t3": ShortcutDef(key="sc_t3", name="t3", location_lakehouse="lh_bronze",
                                  path="Tables/dbo", target_lakehouse="lh_bronze",
                                  target_path="Tables/dbo/t3_dev", depends_on="data_t3"),
        }

        state = WorkspaceState(workspace_id="ws-1")
        state.item_ids = {"lh_bronze": "id-1", "nb_trans": "id-2", "cj_diab": "id-3"}
        return cfg, state

    def test_item_missing_gets_create(self):
        cfg, state = self._make_config_and_state()
        state.resources = [
            Resource("Item", "LH_Bronze.Lakehouse", "lh_bronze", exists=False),
        ]
        compute_actions(state, cfg, on_exists="skip")
        assert state.resources[0].action == "create"

    def test_item_exists_skip(self):
        cfg, state = self._make_config_and_state()
        state.resources = [
            Resource("Item", "LH_Bronze.Lakehouse", "lh_bronze", exists=True),
        ]
        compute_actions(state, cfg, on_exists="skip")
        assert state.resources[0].action == "skip"

    def test_item_exists_force(self):
        cfg, state = self._make_config_and_state()
        state.resources = [
            Resource("Item", "LH_Bronze.Lakehouse", "lh_bronze", exists=True),
        ]
        compute_actions(state, cfg, on_exists="force")
        assert state.resources[0].action == "recreate"

    def test_item_exists_update_supports(self):
        cfg, state = self._make_config_and_state()
        state.resources = [
            Resource("Item", "Transformations.Notebook", "nb_trans", exists=True),
        ]
        compute_actions(state, cfg, on_exists="update")
        assert state.resources[0].action == "update"

    def test_item_exists_update_no_support(self):
        """Lakehouse doesn't support updateDefinition — should skip."""
        cfg, state = self._make_config_and_state()
        state.resources = [
            Resource("Item", "LH_Bronze.Lakehouse", "lh_bronze", exists=True),
        ]
        compute_actions(state, cfg, on_exists="update")
        assert state.resources[0].action == "skip"

    def test_data_missing_producers_ready(self):
        """Data missing but all producers exist — action = run."""
        cfg, state = self._make_config_and_state()
        # Mark cj_diab as existing
        state.resources = [
            Resource("Item", "CJ.CopyJob", "cj_diab", exists=True),
            Resource("Data", "bronze:t2", "data_t2", exists=False),
        ]
        compute_actions(state, cfg, on_exists="skip")
        data_r = state.resources[1]
        assert data_r.action == "run"

    def test_data_missing_producers_not_ready(self):
        """Data missing and producers not deployed — action = blocked."""
        cfg, state = self._make_config_and_state()
        # nb_trans doesn't exist
        state.resources = [
            Resource("Item", "NB.Notebook", "nb_trans", exists=False),
            Resource("Data", "bronze:t3_dev", "data_t3", exists=False),
        ]
        compute_actions(state, cfg, on_exists="skip")
        data_r = state.resources[1]
        assert data_r.action == "blocked"

    def test_data_exists_skip(self):
        cfg, state = self._make_config_and_state()
        state.resources = [
            Resource("Data", "bronze:t2", "data_t2", exists=True),
        ]
        compute_actions(state, cfg, on_exists="skip")
        assert state.resources[0].action == "skip"

    def test_shortcut_missing_dependency_ready(self):
        """Shortcut missing but depends_on data exists — action = create."""
        cfg, state = self._make_config_and_state()
        state.resources = [
            Resource("Data", "bronze:t3_dev", "data_t3", exists=True),
            Resource("Shortcut", "bronze:t3", "sc_t3", exists=False),
        ]
        compute_actions(state, cfg, on_exists="skip")
        sc_r = state.resources[1]
        assert sc_r.action == "create"

    def test_shortcut_missing_dependency_not_ready(self):
        """Shortcut missing and depends_on data also missing — action = blocked."""
        cfg, state = self._make_config_and_state()
        state.resources = [
            Resource("Data", "bronze:t3_dev", "data_t3", exists=False),
            Resource("Shortcut", "bronze:t3", "sc_t3", exists=False),
        ]
        compute_actions(state, cfg, on_exists="skip")
        sc_r = state.resources[1]
        assert sc_r.action == "blocked"

    def test_shortcut_exists_skip(self):
        cfg, state = self._make_config_and_state()
        state.resources = [
            Resource("Shortcut", "bronze:t3", "sc_t3", exists=True),
        ]
        compute_actions(state, cfg, on_exists="skip")
        assert state.resources[0].action == "skip"


class TestDisplay:
    """Test display() doesn't crash — output correctness is visual."""

    def test_display_table(self, capsys):
        s = WorkspaceState(workspace_id="ws-1", workspace_name="Test WS")
        s.resources = [
            Resource("Item", "LH.Lakehouse", "lh", exists=True, action="skip"),
            Resource("Data", "lh:t2", "data_t2", exists=False, action="run"),
        ]
        display(s, output_format="table")
        captured = capsys.readouterr()
        assert "Test WS" in captured.out
        assert "skip" in captured.out
        assert "run" in captured.out

    def test_display_json(self, capsys):
        s = WorkspaceState(workspace_id="ws-1", workspace_name="Test WS")
        s.resources = [Resource("Item", "X", "x", exists=True, action="skip")]
        display(s, output_format="json")
        captured = capsys.readouterr()
        assert '"workspace_id": "ws-1"' in captured.out
