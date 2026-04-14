"""Verification runner — validates lakehouse data post-deployment.

Runs post-deployment checks declared in ``workspace_config.yml`` under
``verifications:``.  Each check queries a lakehouse via the OneLake DFS API
to verify that expected tables exist and have data (Delta log + parquet files).

For deeper SQL-level validation, run the ``Validations`` notebook via::

    python3 bootstrap.py run-job --item nb_validations ...
"""

import json
import logging
from dataclasses import dataclass

import requests

from config import WorkspaceConfig, VerificationDef
from fabric_client import FabricClient, FabricError
from state import WorkspaceState

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    key: str
    description: str
    passed: bool
    message: str
    details: dict | None = None

    def to_dict(self) -> dict:
        d = {"key": self.key, "description": self.description,
             "passed": self.passed, "message": self.message}
        if self.details:
            d["details"] = self.details
        return d


def run_verifications(
    client: FabricClient,
    workspace_id: str,
    cfg: WorkspaceConfig,
    state: WorkspaceState,
    keys: list[str] | None = None,
) -> list[VerificationResult]:
    """Execute verification checks and return results.

    Uses OneLake DFS to check table existence and file counts (as a proxy
    for row existence).  This avoids the need for a SQL connection.
    """
    results: list[VerificationResult] = []

    for vdef in cfg.verifications.values():
        if keys and vdef.key not in keys:
            continue
        result = _run_one(client, workspace_id, vdef, state)
        results.append(result)

    return results


def _run_one(
    client: FabricClient,
    workspace_id: str,
    vdef: VerificationDef,
    state: WorkspaceState,
) -> VerificationResult:
    """Run a single verification check via DFS table inspection."""
    lh_id = state.item_ids.get(vdef.lakehouse, "")
    if not lh_id:
        return VerificationResult(
            key=vdef.key, description=vdef.description, passed=False,
            message=f"Lakehouse {vdef.lakehouse} not found in workspace",
        )

    # Special case: shortcut existence check
    if vdef.query.startswith("SHORTCUT_CHECK:"):
        return _check_shortcuts(client, workspace_id, lh_id, vdef)

    # Get DFS URL from lakehouse properties
    props = state.lakehouse_props.get(vdef.lakehouse, {})
    tables_path = props.get("oneLakeTablesPath", "")
    if not tables_path:
        return VerificationResult(
            key=vdef.key, description=vdef.description, passed=False,
            message=f"No oneLakeTablesPath for {vdef.lakehouse}",
        )

    dfs_base = tables_path.rsplit("/Tables", 1)[0]
    schema = props.get("defaultSchema", "dbo")

    # Extract table name from the query (simple parse: "FROM dbo.<table>")
    table_name = _extract_table_from_query(vdef.query, schema)
    if not table_name:
        return VerificationResult(
            key=vdef.key, description=vdef.description, passed=False,
            message=f"Could not parse table name from query: {vdef.query[:60]}",
        )

    # Check if the table's _delta_log exists via DFS
    token = client._get_onelake_token()
    headers = {"Authorization": f"Bearer {token}"}

    # List contents of Tables/ recursively, find the table
    try:
        resp = requests.get(
            dfs_base,
            headers=headers,
            params={"resource": "filesystem", "directory": "Tables", "recursive": "true"},
        )
        if resp.status_code != 200:
            return VerificationResult(
                key=vdef.key, description=vdef.description, passed=False,
                message=f"DFS listing failed: HTTP {resp.status_code}",
            )

        paths = resp.json().get("paths", [])
        schema_marker = f"/{schema}/"

        # Find delta log for this table
        has_delta_log = False
        parquet_count = 0
        for p in paths:
            name = p.get("name", "")
            if schema_marker not in name:
                continue
            after_schema = name.split(schema_marker, 1)[-1]
            parts = after_schema.split("/")
            if parts[0] != table_name:
                continue
            if "_delta_log" in name:
                has_delta_log = True
            if name.endswith(".parquet") and "_delta_log" not in name:
                parquet_count += 1

    except Exception as e:
        return VerificationResult(
            key=vdef.key, description=vdef.description, passed=False,
            message=f"DFS error: {e}",
        )

    if not has_delta_log:
        return VerificationResult(
            key=vdef.key, description=vdef.description, passed=False,
            message=f"Table {schema}.{table_name} not found (no _delta_log)",
            details={"table": table_name, "parquet_files": 0},
        )

    # Validate expectations
    expect = vdef.expect
    min_val = (expect.get("column_check", {}).get("min_value", 0)
               if expect.get("column_check") else 0)

    # Parquet file count is a rough proxy — if min_value > 0 and no parquet files, fail
    if min_val and parquet_count == 0:
        return VerificationResult(
            key=vdef.key, description=vdef.description, passed=False,
            message=f"Table {schema}.{table_name} exists but has 0 parquet files",
            details={"table": table_name, "parquet_files": parquet_count},
        )

    return VerificationResult(
        key=vdef.key, description=vdef.description, passed=True,
        message=f"OK — {schema}.{table_name} ({parquet_count} parquet file(s))",
        details={"table": table_name, "parquet_files": parquet_count},
    )


def _check_shortcuts(
    client: FabricClient, workspace_id: str, lh_id: str, vdef: VerificationDef,
) -> VerificationResult:
    """Verify that expected shortcuts exist in the lakehouse."""
    expected = [s.strip() for s in vdef.query.split(":", 1)[1].split(",")]
    try:
        shortcuts = client.list_shortcuts(workspace_id, lh_id)
        found = {s.get("name", "") for s in shortcuts}
    except FabricError as e:
        return VerificationResult(
            key=vdef.key, description=vdef.description, passed=False,
            message=f"Could not list shortcuts: {e}",
        )
    missing = [n for n in expected if n not in found]
    if missing:
        return VerificationResult(
            key=vdef.key, description=vdef.description, passed=False,
            message=f"Missing shortcuts: {', '.join(missing)}",
            details={"expected": expected, "found": sorted(found)},
        )
    return VerificationResult(
        key=vdef.key, description=vdef.description, passed=True,
        message=f"OK — shortcuts {', '.join(expected)} all present",
        details={"found": sorted(found)},
    )


def _extract_table_from_query(query: str, schema: str) -> str:
    """Simple extraction of table name from SQL query."""
    import re
    # Match FROM dbo.t2, FROM dbo.t1, etc.
    m = re.search(rf'FROM\s+(?:{schema}\.)?(\w+)', query, re.IGNORECASE)
    if m:
        return m.group(1)
    # Match SELECT ... FROM ... but just get the first table
    m = re.search(r'FROM\s+(\w+)', query, re.IGNORECASE)
    return m.group(1) if m else ""


def display_verifications(results: list[VerificationResult], output_format: str = "table"):
    """Print verification results."""
    if output_format == "json":
        print(json.dumps([r.to_dict() for r in results], indent=2))
        return

    print(f"\n{'═' * 75}")
    print(f"  Verification Results")
    print(f"{'═' * 75}")
    print(f"\n  {'RESULT':<8}  {'CHECK':<35}  MESSAGE")
    print(f"  {'─' * 8}  {'─' * 35}  {'─' * 30}")

    for r in results:
        marker = "✓ PASS" if r.passed else "✗ FAIL"
        print(f"  {marker:<8}  {r.description[:35]:<35}  {r.message}")

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\n  {passed}/{total} checks passed.")
    if passed < total:
        print(f"  {total - passed} check(s) FAILED.")
    print()
