"""Desired-state vs current-state engine for Fabric workspace bootstrap.

The state engine reads the workspace configuration (``WorkspaceConfig``) and
queries the Fabric workspace to build a complete picture of what exists and
what is missing.  It is the foundation for idempotent, re-runnable deployments.

Key types:
    ``Resource``         – a single tracked resource (item, data, shortcut).
    ``WorkspaceState``   – full assessment result with convenience accessors.
    ``assess()``         – queries Fabric and returns a ``WorkspaceState``.
    ``display()``        – pretty-prints the assessment table.
"""

import logging
from dataclasses import dataclass, field

from config import WorkspaceConfig
from fabric_client import FabricClient, FabricError

logger = logging.getLogger(__name__)


# ── Core types ────────────────────────────────────────────────────────────────

@dataclass
class Resource:
    """A single resource tracked in the state assessment."""
    category: str       # Item, Data, Shortcut
    label: str          # Human-readable name
    key: str            # Unique lookup key (matches config keys)
    exists: bool = False
    action: str = ""    # Computed: create, update, skip, run, blocked, ""

    def to_dict(self) -> dict:
        return {"category": self.category, "label": self.label, "key": self.key,
                "exists": self.exists, "action": self.action}


@dataclass
class WorkspaceState:
    """Full desired-vs-current state of a workspace."""
    workspace_id: str = ""
    workspace_name: str = ""

    # Resolved item IDs (populated during assessment)
    item_ids: dict[str, str] = field(default_factory=dict)      # config key → item id

    # Lakehouse properties (populated for lakehouses that exist)
    lakehouse_props: dict[str, dict] = field(default_factory=dict)  # config key → props dict

    # All tracked resources
    resources: list[Resource] = field(default_factory=list)

    def get(self, key: str) -> Resource | None:
        for r in self.resources:
            if r.key == key:
                return r
        return None

    def is_done(self, key: str) -> bool:
        r = self.get(key)
        return r is not None and r.exists

    def item_id(self, key: str) -> str:
        return self.item_ids.get(key, "")

    def lakehouse_sql_conn_string(self, key: str) -> str:
        return (self.lakehouse_props.get(key, {})
                .get("sqlEndpointProperties", {})
                .get("connectionString", ""))

    def lakehouse_sql_endpoint_id(self, key: str) -> str:
        return (self.lakehouse_props.get(key, {})
                .get("sqlEndpointProperties", {})
                .get("id", ""))

    @property
    def missing_count(self) -> int:
        return sum(1 for r in self.resources if not r.exists)

    @property
    def all_done(self) -> bool:
        return self.missing_count == 0

    def to_dict(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "workspace_name": self.workspace_name,
            "resources": [r.to_dict() for r in self.resources],
            "summary": {"total": len(self.resources), "exists": len(self.resources) - self.missing_count, "missing": self.missing_count},
        }


# ── Assessment ────────────────────────────────────────────────────────────────

def assess(client: FabricClient, workspace_id: str, cfg: WorkspaceConfig) -> WorkspaceState:
    """Query the workspace and build a full state assessment driven by config."""
    state = WorkspaceState(workspace_id=workspace_id)

    ws = client.get_workspace(workspace_id)
    state.workspace_name = ws.get("displayName", "")

    # Fetch all items in one call
    items = client.list_items(workspace_id)
    items_by_name: dict[str, dict] = {}
    for item in items:
        items_by_name[item["displayName"]] = item

    # ── Check each declared item ──────────────────────────────
    for item_def in cfg.items.values():
        item = items_by_name.get(item_def.display_name)
        exists = (item is not None
                  and item.get("type", "").lower() == item_def.type.lower())
        state.resources.append(Resource(
            "Item",
            f"{item_def.display_name}.{item_def.type}",
            item_def.key,
            exists,
        ))
        if exists:
            state.item_ids[item_def.key] = item["id"]

    # ── Lakehouse properties ──────────────────────────────────
    for lh_def in cfg.lakehouses():
        lh_id = state.item_id(lh_def.key)
        if not lh_id:
            continue
        try:
            lh = client.get_lakehouse(workspace_id, lh_id)
            state.lakehouse_props[lh_def.key] = lh.get("properties", {})
        except FabricError:
            logger.warning("Could not retrieve lakehouse properties for %s", lh_def.display_name)

    # ── Data expectations ─────────────────────────────────────
    table_cache: dict[str, set[str]] = {}   # lakehouse key → set of table names
    for de in cfg.data_expectations.values():
        lh_id = state.item_id(de.lakehouse)
        if lh_id and de.lakehouse not in table_cache:
            tables = client.list_lakehouse_tables(workspace_id, lh_id)
            table_cache[de.lakehouse] = {t.get("name", "") for t in tables}
        lh_tables = table_cache.get(de.lakehouse, set())
        state.resources.append(Resource(
            "Data",
            f"{de.lakehouse}:{de.table}",
            de.key,
            de.table in lh_tables,
        ))

    # ── Shortcuts ─────────────────────────────────────────────
    shortcut_cache: dict[str, set[str]] = {}  # lakehouse key → set of shortcut names
    for sc in cfg.shortcuts.values():
        lh_id = state.item_id(sc.location_lakehouse)
        if lh_id and sc.location_lakehouse not in shortcut_cache:
            shortcuts = client.list_shortcuts(workspace_id, lh_id)
            shortcut_cache[sc.location_lakehouse] = {s.get("name", "") for s in shortcuts}
        names = shortcut_cache.get(sc.location_lakehouse, set())
        state.resources.append(Resource(
            "Shortcut",
            f"{sc.location_lakehouse}:{sc.name} → {sc.target_lakehouse}",
            sc.key,
            sc.name in names,
        ))

    return state


def compute_actions(state: WorkspaceState, cfg: WorkspaceConfig, on_exists: str = "skip"):
    """Enrich each resource with its planned action (create/update/skip/run/blocked)."""
    for r in state.resources:
        if r.category == "Item":
            item_def = cfg.items.get(r.key)
            if r.exists:
                if on_exists == "force":
                    r.action = "recreate"
                elif on_exists == "update" and item_def and item_def.supports_update_definition:
                    r.action = "update"
                else:
                    r.action = "skip"
            else:
                r.action = "create"
        elif r.category == "Data":
            de = cfg.data_expectations.get(r.key)
            if r.exists:
                r.action = "skip"
            else:
                # Check if producing items exist
                producers_ready = de and all(state.is_done(p) for p in de.produced_by) if de else False
                r.action = "run" if producers_ready else "blocked"
        elif r.category == "Shortcut":
            sc = cfg.shortcuts.get(r.key)
            if r.exists:
                r.action = "skip"
            elif sc and sc.depends_on and not state.is_done(sc.depends_on):
                r.action = "blocked"
            else:
                r.action = "create"


# ── Display ───────────────────────────────────────────────────────────────────

_ACTION_SYMBOLS = {
    "skip": ("─", "skip"),
    "create": ("+", "create"),
    "update": ("~", "update"),
    "recreate": ("!", "recreate"),
    "run": ("▶", "run"),
    "blocked": ("⊘", "blocked"),
    "": ("?", "unknown"),
}


def display(state: WorkspaceState, output_format: str = "table"):
    """Display the state assessment.

    Args:
        output_format: ``"table"`` for human-readable, ``"json"`` for structured.
    """
    if output_format == "json":
        import json
        print(json.dumps(state.to_dict(), indent=2))
        return

    print(f"\n{'═' * 65}")
    print(f"  State Assessment: {state.workspace_name}")
    print(f"  Workspace ID:     {state.workspace_id}")
    print(f"{'═' * 65}")
    print(f"\n  {'CATEGORY':<12}  {'RESOURCE':<38}  {'STATE':<9}  ACTION")
    print(f"  {'─' * 12}  {'─' * 38}  {'─' * 9}  {'─' * 10}")

    for r in state.resources:
        exists_marker = "✓" if r.exists else "·"
        exists_text = "exists" if r.exists else "missing"
        sym, action_text = _ACTION_SYMBOLS.get(r.action, ("?", r.action))
        print(f"  {r.category:<12}  {r.label:<38}  {exists_marker} {exists_text:<7}  {sym} {action_text}")

    print()
    if state.all_done:
        print("  All resources are in desired state. Nothing to do.")
    else:
        actions = {}
        for r in state.resources:
            if r.action and r.action != "skip":
                actions[r.action] = actions.get(r.action, 0) + 1
        parts = [f"{n} {a}" for a, n in actions.items()]
        print(f"  {state.missing_count} resource(s) need action: {', '.join(parts)}")
    print()
