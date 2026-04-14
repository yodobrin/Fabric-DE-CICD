"""Workspace configuration loader.

Reads ``workspace_config.yml`` and exposes its contents as typed dataclasses
that the rest of the SDK consumes.  All hardcoded item names, placeholder GUIDs,
shortcut definitions, and phase ordering live in the YAML — this module is the
single bridge between the config file and the Python runtime.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_NAME = "workspace_config.yml"


# ── Typed sections ────────────────────────────────────────────────────────────

@dataclass
class FabricSettings:
    api_host: str = "api.fabric.microsoft.com"
    capacity_id: str = ""


# Item types that support the updateDefinition REST API.
# See: https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/item-definition-overview
UPDATABLE_TYPES: set[str] = {
    "Notebook", "CopyJob", "Environment", "SemanticModel", "Report",
    "DataPipeline", "Dataflow", "SparkJobDefinition", "KQLQueryset",
    "KQLDashboard", "Eventhouse", "Eventstream", "Reflex",
}


@dataclass
class ItemDef:
    """A single Fabric item declared in the config."""
    key: str                          # logical key (e.g. "lakehouse_bronze")
    type: str                         # Fabric item type (e.g. "Lakehouse")
    display_name: str                 # display name in workspace
    template_folder: str = ""         # subfolder in workshop_template/
    enable_schemas: bool = False      # Lakehouse-only
    default_lakehouse: str = ""       # Notebook-only: key of the default lakehouse

    @property
    def supports_update_definition(self) -> bool:
        """Whether this item type supports ``updateDefinition`` (in-place update)."""
        return self.type in UPDATABLE_TYPES


@dataclass
class PlaceholderDef:
    workspace_id: str = ""
    bronze_lakehouse_id: str = ""
    silver_lakehouse_id: str = ""
    silver_sql_conn_str: str = ""
    silver_sql_conn_id: str = ""
    semantic_model_id: str = ""


@dataclass
class ShortcutDef:
    key: str
    name: str
    location_lakehouse: str        # item key
    path: str
    target_lakehouse: str          # item key
    target_path: str
    depends_on: str = ""           # data expectation key


@dataclass
class DataExpectation:
    key: str
    lakehouse: str                 # item key
    table: str
    produced_by: list[str] = field(default_factory=list)


@dataclass
class VerificationDef:
    """A SQL query run against a lakehouse SQL endpoint to verify data."""
    key: str
    description: str
    lakehouse: str                 # item key
    query: str
    expect: dict = field(default_factory=dict)  # min_rows, column_check etc.


@dataclass
class PhaseDef:
    name: str
    description: str = ""
    deploy: list[str] = field(default_factory=list)
    run_jobs: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    skip_if_done: str = ""


@dataclass
class WorkspaceConfig:
    """Fully parsed workspace configuration."""
    fabric: FabricSettings = field(default_factory=FabricSettings)
    items: dict[str, ItemDef] = field(default_factory=dict)
    placeholders: PlaceholderDef = field(default_factory=PlaceholderDef)
    shortcuts: dict[str, ShortcutDef] = field(default_factory=dict)
    data_expectations: dict[str, DataExpectation] = field(default_factory=dict)
    phases: list[PhaseDef] = field(default_factory=list)
    verifications: dict[str, VerificationDef] = field(default_factory=dict)

    # ── convenience accessors ─────────────────────────────────

    def items_of_type(self, item_type: str) -> list[ItemDef]:
        return [i for i in self.items.values() if i.type == item_type]

    def get_item(self, key: str) -> ItemDef:
        return self.items[key]

    def lakehouses(self) -> list[ItemDef]:
        return self.items_of_type("Lakehouse")

    def notebooks(self) -> list[ItemDef]:
        return self.items_of_type("Notebook")

    def copyjobs(self) -> list[ItemDef]:
        return self.items_of_type("CopyJob")


# ── Loader ────────────────────────────────────────────────────────────────────

def load_config(path: Path | str | None = None) -> WorkspaceConfig:
    """Load and validate a workspace_config.yml file.

    Args:
        path: Explicit path to the YAML file.  When *None*, looks for
            ``workspace_config.yml`` next to this module.
    """
    if path is None:
        path = Path(__file__).resolve().parent / DEFAULT_CONFIG_NAME
    else:
        path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    raw: dict[str, Any] = yaml.safe_load(path.read_text())

    cfg = WorkspaceConfig()

    # fabric
    fb = raw.get("fabric", {})
    cfg.fabric = FabricSettings(
        api_host=fb.get("api_host", "api.fabric.microsoft.com"),
        capacity_id=fb.get("capacity_id", ""),
    )

    # items
    for key, val in raw.get("items", {}).items():
        cfg.items[key] = ItemDef(
            key=key,
            type=val["type"],
            display_name=val["display_name"],
            template_folder=val.get("template_folder", ""),
            enable_schemas=val.get("enable_schemas", False),
            default_lakehouse=val.get("default_lakehouse", ""),
        )

    # placeholders
    ph = raw.get("placeholders", {})
    cfg.placeholders = PlaceholderDef(
        workspace_id=ph.get("workspace_id", ""),
        bronze_lakehouse_id=ph.get("bronze_lakehouse_id", ""),
        silver_lakehouse_id=ph.get("silver_lakehouse_id", ""),
        silver_sql_conn_str=ph.get("silver_sql_conn_str", ""),
        silver_sql_conn_id=ph.get("silver_sql_conn_id", ""),
        semantic_model_id=ph.get("semantic_model_id", ""),
    )

    # shortcuts
    for key, val in raw.get("shortcuts", {}).items():
        cfg.shortcuts[key] = ShortcutDef(
            key=key,
            name=val["name"],
            location_lakehouse=val["location_lakehouse"],
            path=val["path"],
            target_lakehouse=val["target_lakehouse"],
            target_path=val["target_path"],
            depends_on=val.get("depends_on", ""),
        )

    # data expectations
    for key, val in raw.get("data_expectations", {}).items():
        cfg.data_expectations[key] = DataExpectation(
            key=key,
            lakehouse=val["lakehouse"],
            table=val["table"],
            produced_by=val.get("produced_by", []),
        )

    # phases
    for p in raw.get("phases", []):
        cfg.phases.append(PhaseDef(
            name=p["name"],
            description=p.get("description", ""),
            deploy=p.get("deploy", []),
            run_jobs=p.get("run_jobs", []),
            actions=p.get("actions", []),
            skip_if_done=p.get("skip_if_done", ""),
        ))

    # verifications
    for key, val in raw.get("verifications", {}).items():
        cfg.verifications[key] = VerificationDef(
            key=key,
            description=val.get("description", ""),
            lakehouse=val["lakehouse"],
            query=val["query"],
            expect=val.get("expect", {}),
        )

    logger.info("Loaded config: %d items, %d shortcuts, %d phases, %d verifications",
                len(cfg.items), len(cfg.shortcuts), len(cfg.phases), len(cfg.verifications))
    return cfg
