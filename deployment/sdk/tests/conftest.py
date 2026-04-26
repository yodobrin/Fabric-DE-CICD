"""Shared fixtures for SDK tests."""

import sys
from pathlib import Path

import pytest

# Add the SDK source directory to sys.path so tests can import modules directly
SDK_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SDK_DIR))


@pytest.fixture
def sample_config_yaml(tmp_path):
    """Write a minimal workspace_config.yml and return its path."""
    content = """\
fabric:
  api_host: api.fabric.microsoft.com
  capacity_id: cap-123

items:
  lakehouse_bronze:
    type: Lakehouse
    display_name: Lakehouse_Bronze
    enable_schemas: true
  lakehouse_silver:
    type: Lakehouse
    display_name: Lakehouse_Silver
    enable_schemas: true
  nb_transformations:
    type: Notebook
    display_name: Transformations
    template_folder: Transformations.Notebook
    default_lakehouse: lakehouse_silver
  copyjob_diabetes:
    type: CopyJob
    display_name: CopyJob_Diabetes
    template_folder: CopyJob_Diabetes.CopyJob

placeholders:
  workspace_id: "00000000-0000-0000-0000-000000000001"
  bronze_lakehouse_id: "00000000-0000-0000-0000-000000000002"
  silver_lakehouse_id: "00000000-0000-0000-0000-000000000003"
  silver_sql_conn_str: "placeholder-conn-str"
  silver_sql_conn_id: "00000000-0000-0000-0000-000000000004"
  semantic_model_id: "00000000-0000-0000-0000-000000000005"

shortcuts:
  sc_t3:
    name: t3
    location_lakehouse: lakehouse_bronze
    path: Tables/dbo
    target_lakehouse: lakehouse_bronze
    target_path: Tables/dbo/t3_dev
    depends_on: data_t3_dev

data_expectations:
  data_t2:
    lakehouse: lakehouse_bronze
    table: t2
    produced_by:
      - copyjob_diabetes
  data_t3_dev:
    lakehouse: lakehouse_bronze
    table: t3_dev
    produced_by:
      - nb_transformations

phases:
  - name: phase_1_infra
    description: Create lakehouses
    deploy:
      - lakehouse_bronze
      - lakehouse_silver
  - name: phase_2_ingest
    description: Run copy jobs
    deploy:
      - copyjob_diabetes
    run_jobs:
      - copyjob_diabetes
    skip_if_done: data_t2
  - name: phase_3_transform
    description: Run transformations
    deploy:
      - nb_transformations
    run_jobs:
      - nb_transformations
    actions:
      - shortcut:sc_t3

verifications:
  check_t2:
    description: "Bronze t2 has data"
    lakehouse: lakehouse_bronze
    query: "SELECT COUNT(*) as cnt FROM dbo.t2"
    expect:
      column_check:
        column: cnt
        min_value: 1
  check_t1:
    description: "Silver t1 has data"
    lakehouse: lakehouse_silver
    query: "SELECT COUNT(*) FROM dbo.t1"
    expect:
      column_check:
        column: cnt
        min_value: 1
  check_shortcuts:
    description: "Shortcuts exist"
    lakehouse: lakehouse_bronze
    query: "SHORTCUT_CHECK: t3"
    expect: {}
"""
    config_path = tmp_path / "workspace_config.yml"
    config_path.write_text(content)
    return config_path
