"""Tests for config.py — YAML loading and dataclass mapping."""

import pytest
from pathlib import Path

from config import (
    load_config,
    WorkspaceConfig,
    ItemDef,
    PhaseDef,
    ShortcutDef,
    DataExpectation,
    VerificationDef,
    UPDATABLE_TYPES,
)


class TestLoadConfig:
    """Test the load_config() function with various YAML inputs."""

    def test_loads_valid_config(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        assert isinstance(cfg, WorkspaceConfig)

    def test_fabric_settings(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        assert cfg.fabric.api_host == "api.fabric.microsoft.com"
        assert cfg.fabric.capacity_id == "cap-123"

    def test_items_parsed(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        assert len(cfg.items) == 4
        assert "lakehouse_bronze" in cfg.items
        assert "nb_transformations" in cfg.items

    def test_item_properties(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        bronze = cfg.items["lakehouse_bronze"]
        assert bronze.type == "Lakehouse"
        assert bronze.display_name == "Lakehouse_Bronze"
        assert bronze.enable_schemas is True

        nb = cfg.items["nb_transformations"]
        assert nb.type == "Notebook"
        assert nb.template_folder == "Transformations.Notebook"
        assert nb.default_lakehouse == "lakehouse_silver"

    def test_placeholders(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        assert cfg.placeholders.workspace_id == "00000000-0000-0000-0000-000000000001"
        assert cfg.placeholders.bronze_lakehouse_id == "00000000-0000-0000-0000-000000000002"

    def test_shortcuts(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        assert len(cfg.shortcuts) == 1
        sc = cfg.shortcuts["sc_t3"]
        assert sc.name == "t3"
        assert sc.location_lakehouse == "lakehouse_bronze"
        assert sc.depends_on == "data_t3_dev"

    def test_data_expectations(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        assert len(cfg.data_expectations) == 2
        de = cfg.data_expectations["data_t2"]
        assert de.lakehouse == "lakehouse_bronze"
        assert de.table == "t2"
        assert de.produced_by == ["copyjob_diabetes"]

    def test_phases(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        assert len(cfg.phases) == 3
        p1 = cfg.phases[0]
        assert p1.name == "phase_1_infra"
        assert p1.deploy == ["lakehouse_bronze", "lakehouse_silver"]
        p2 = cfg.phases[1]
        assert p2.skip_if_done == "data_t2"
        assert p2.run_jobs == ["copyjob_diabetes"]

    def test_verifications(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        assert len(cfg.verifications) == 3
        v = cfg.verifications["check_t2"]
        assert v.description == "Bronze t2 has data"
        assert "SELECT COUNT" in v.query
        assert v.expect["column_check"]["min_value"] == 1

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yml")

    def test_empty_config(self, tmp_path):
        p = tmp_path / "empty.yml"
        p.write_text("{}")
        cfg = load_config(p)
        assert cfg.items == {}
        assert cfg.phases == []


class TestItemDef:
    """Test ItemDef properties."""

    def test_supports_update_for_notebook(self):
        item = ItemDef(key="nb", type="Notebook", display_name="Test")
        assert item.supports_update_definition is True

    def test_supports_update_for_copyjob(self):
        item = ItemDef(key="cj", type="CopyJob", display_name="Test")
        assert item.supports_update_definition is True

    def test_no_update_for_lakehouse(self):
        item = ItemDef(key="lh", type="Lakehouse", display_name="Test")
        assert item.supports_update_definition is False

    def test_no_update_for_unknown_type(self):
        item = ItemDef(key="x", type="MysteryType", display_name="Test")
        assert item.supports_update_definition is False


class TestWorkspaceConfigAccessors:
    """Test convenience methods on WorkspaceConfig."""

    def test_items_of_type(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        lakehouses = cfg.items_of_type("Lakehouse")
        assert len(lakehouses) == 2

    def test_lakehouses(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        assert len(cfg.lakehouses()) == 2

    def test_notebooks(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        nbs = cfg.notebooks()
        assert len(nbs) == 1
        assert nbs[0].key == "nb_transformations"

    def test_copyjobs(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        assert len(cfg.copyjobs()) == 1

    def test_get_item(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        item = cfg.get_item("lakehouse_bronze")
        assert item.display_name == "Lakehouse_Bronze"

    def test_get_item_missing_raises(self, sample_config_yaml):
        cfg = load_config(sample_config_yaml)
        with pytest.raises(KeyError):
            cfg.get_item("nonexistent")
