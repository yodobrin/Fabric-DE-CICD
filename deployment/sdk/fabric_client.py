"""Thin REST client for the Microsoft Fabric API."""

import time
import logging
from typing import Any

import requests
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
ONELAKE_SCOPE = "https://storage.azure.com/.default"
DEFAULT_BASE_HOST = "api.fabric.microsoft.com"
API_VERSION = "v1"


# ── TTL cache ─────────────────────────────────────────────────────────────────

class _TTLCache:
    """Simple in-memory cache with per-key TTL (seconds)."""

    def __init__(self, default_ttl: float = 30.0):
        self._store: dict[str, tuple[float, Any]] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expiry, value = entry
        if time.time() > expiry:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: float | None = None):
        self._store[key] = (time.time() + (ttl or self.default_ttl), value)

    def invalidate(self, prefix: str = ""):
        """Drop all keys (or those starting with *prefix*)."""
        if not prefix:
            self._store.clear()
        else:
            for k in list(self._store):
                if k.startswith(prefix):
                    del self._store[k]


class FabricError(Exception):
    """Raised when a Fabric API call returns an error."""

    def __init__(self, status_code: int, error_code: str, message: str):
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(f"[{error_code}] {message} (HTTP {status_code})")


class FabricClient:
    """Authenticated REST client for the Fabric data-plane API.

    Args:
        base_host: API hostname, e.g. ``"dailyapi.powerbi.com"`` for the
            daily ring or the default ``"api.fabric.microsoft.com"``.
        credential: An ``azure-identity`` credential instance.  Falls back
            to :class:`DefaultAzureCredential` when *None*.
        max_retries: How many times to retry on transient / 429 errors.
        base_delay: Initial retry delay in seconds (doubles each attempt).
    """

    def __init__(
        self,
        base_host: str = DEFAULT_BASE_HOST,
        credential=None,
        max_retries: int = 6,
        base_delay: float = 5.0,
    ):
        self._base = f"https://{base_host}/{API_VERSION}"
        self._credential = credential or DefaultAzureCredential()
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._token: str | None = None
        self._token_expiry: float = 0
        self._onelake_token: str | None = None
        self._onelake_token_expiry: float = 0
        self._cache = _TTLCache(default_ttl=30.0)

    # ── auth ──────────────────────────────────────────────────────

    def _get_token(self) -> str:
        now = time.time()
        if self._token is None or now >= self._token_expiry - 60:
            tok = self._credential.get_token(FABRIC_SCOPE)
            self._token = tok.token
            self._token_expiry = tok.expires_on
        return self._token

    def _get_onelake_token(self) -> str:
        now = time.time()
        if self._onelake_token is None or now >= self._onelake_token_expiry - 60:
            tok = self._credential.get_token(ONELAKE_SCOPE)
            self._onelake_token = tok.token
            self._onelake_token_expiry = tok.expires_on
        return self._onelake_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    # ── low-level request with retry ──────────────────────────────

    TRANSIENT_CODES = {408, 429, 500, 502, 503, 504}

    def _request(
        self, method: str, path: str, **kwargs
    ) -> requests.Response:
        url = f"{self._base}/{path.lstrip('/')}"
        delay = self._base_delay
        for attempt in range(1, self._max_retries + 1):
            resp = requests.request(method, url, headers=self._headers(), **kwargs)
            if resp.status_code < 300:
                return resp
            if resp.status_code in self.TRANSIENT_CODES:
                retry_after = int(resp.headers.get("Retry-After", delay))
                logger.warning(
                    "Transient %s on %s %s (attempt %d/%d), retrying in %ds",
                    resp.status_code, method, path, attempt, self._max_retries, retry_after,
                )
                time.sleep(retry_after)
                delay = min(delay * 2, 120)
                continue
            self._raise(resp)
        self._raise(resp)  # type: ignore[possibly-undefined]

    def _raise(self, resp: requests.Response):
        try:
            body = resp.json()
            err = body.get("error", body)
            code = err.get("code", "Unknown")
            msg = err.get("message", resp.text)
        except Exception:
            code, msg = "Unknown", resp.text
        raise FabricError(resp.status_code, code, msg)

    def _get(self, path: str, **kw) -> requests.Response:
        return self._request("GET", path, **kw)

    def _post(self, path: str, **kw) -> requests.Response:
        return self._request("POST", path, **kw)

    def _patch(self, path: str, **kw) -> requests.Response:
        return self._request("PATCH", path, **kw)

    def _delete(self, path: str, **kw) -> requests.Response:
        return self._request("DELETE", path, **kw)

    def invalidate_cache(self, prefix: str = ""):
        """Drop cached API responses (call after mutations)."""
        self._cache.invalidate(prefix)

    # ── workspaces ────────────────────────────────────────────────

    def list_workspaces(self) -> list[dict]:
        cached = self._cache.get("workspaces")
        if cached is not None:
            return cached
        items: list[dict] = []
        resp = self._get("workspaces")
        data = resp.json()
        items.extend(data.get("value", []))
        while data.get("continuationUri"):
            resp = requests.get(data["continuationUri"], headers=self._headers())
            data = resp.json()
            items.extend(data.get("value", []))
        self._cache.set("workspaces", items)
        return items

    def get_workspace(self, workspace_id: str) -> dict:
        cache_key = f"ws:{workspace_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        result = self._get(f"workspaces/{workspace_id}").json()
        self._cache.set(cache_key, result)
        return result

    def get_workspace_by_name(self, name: str) -> dict | None:
        for ws in self.list_workspaces():
            if ws["displayName"] == name:
                return ws
        return None

    def create_workspace(self, name: str, capacity_id: str | None = None) -> dict:
        body: dict[str, Any] = {"displayName": name}
        if capacity_id:
            body["capacityId"] = capacity_id
        return self._post("workspaces", json=body).json()

    def assign_to_capacity(self, workspace_id: str, capacity_id: str):
        self._post(
            f"workspaces/{workspace_id}/assignToCapacity",
            json={"capacityId": capacity_id},
        )

    # ── items (generic) ───────────────────────────────────────────

    def list_items(self, workspace_id: str, item_type: str | None = None) -> list[dict]:
        cache_key = f"items:{workspace_id}:{item_type or 'all'}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        params = {}
        if item_type:
            params["type"] = item_type
        items: list[dict] = []
        resp = self._get(f"workspaces/{workspace_id}/items", params=params)
        data = resp.json()
        items.extend(data.get("value", []))
        while data.get("continuationUri"):
            resp = requests.get(data["continuationUri"], headers=self._headers())
            data = resp.json()
            items.extend(data.get("value", []))
        self._cache.set(cache_key, items)
        return items

    def get_item(self, workspace_id: str, item_id: str) -> dict:
        return self._get(f"workspaces/{workspace_id}/items/{item_id}").json()

    def get_item_by_name(
        self, workspace_id: str, display_name: str, item_type: str | None = None
    ) -> dict | None:
        for item in self.list_items(workspace_id, item_type):
            if item["displayName"] == display_name:
                return item
        return None

    def create_item(self, workspace_id: str, display_name: str, item_type: str, **extra) -> dict:
        body: dict[str, Any] = {"displayName": display_name, "type": item_type, **extra}
        return self._post(f"workspaces/{workspace_id}/items", json=body).json()

    def delete_item(self, workspace_id: str, item_id: str):
        self._delete(f"workspaces/{workspace_id}/items/{item_id}")
        self._cache.invalidate(f"items:{workspace_id}")

    def update_item_definition(self, workspace_id: str, item_id: str, definition: dict):
        """Update an existing item's definition in-place (no delete/recreate).

        See: https://learn.microsoft.com/en-us/rest/api/fabric/core/items/update-item-definition
        Supported types: Notebook, CopyJob, Environment, SemanticModel, Report, and more.
        """
        self._post(
            f"workspaces/{workspace_id}/items/{item_id}/updateDefinition",
            params={"updateMetadata": "True"},
            json={"definition": definition},
        )
        self._cache.invalidate(f"items:{workspace_id}")

    # ── lakehouses ────────────────────────────────────────────────

    def create_lakehouse(
        self, workspace_id: str, display_name: str, enable_schemas: bool = True
    ) -> dict:
        body: dict[str, Any] = {"displayName": display_name, "type": "Lakehouse"}
        if enable_schemas:
            body["creationPayload"] = {"enableSchemas": True}
        return self._post(f"workspaces/{workspace_id}/items", json=body).json()

    def get_lakehouse(self, workspace_id: str, lakehouse_id: str) -> dict:
        cache_key = f"lh:{workspace_id}:{lakehouse_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        result = self._get(f"workspaces/{workspace_id}/lakehouses/{lakehouse_id}").json()
        self._cache.set(cache_key, result)
        return result

    def list_lakehouse_tables(self, workspace_id: str, lakehouse_id: str) -> list[dict]:
        try:
            resp = self._get(f"workspaces/{workspace_id}/lakehouses/{lakehouse_id}/tables")
            return resp.json().get("data", [])
        except FabricError as e:
            if e.status_code == 404:
                return []
            if e.status_code == 400:
                # Schema-enabled lakehouses don't support this endpoint.
                # Fall back to listing table directories via OneLake DFS.
                logger.info("Tables API not supported (schemas enabled), falling back to DFS listing")
                return self._list_tables_via_dfs(workspace_id, lakehouse_id)
            raise

    def _list_tables_via_dfs(self, workspace_id: str, lakehouse_id: str) -> list[dict]:
        """List tables by scanning for Delta tables via OneLake DFS recursive listing.

        Discovers the correct DFS hostname from the lakehouse properties
        (e.g. daily-onelake.dfs.fabric.microsoft.com for daily ring).
        Schema-enabled lakehouses virtualize directory listings, so non-recursive
        listing doesn't show user tables. We use recursive listing under Tables/
        and identify Delta tables by looking for _delta_log directories under
        the schema folder.
        """
        lh = self.get_lakehouse(workspace_id, lakehouse_id)
        tables_path = lh.get("properties", {}).get("oneLakeTablesPath", "")
        if not tables_path:
            logger.warning("No oneLakeTablesPath in lakehouse properties")
            return []
        dfs_url = tables_path.rsplit("/Tables", 1)[0]
        schema = lh.get("properties", {}).get("defaultSchema", "dbo")
        system_dirs = {"Files", "Functions", "TableMaintenance", "Tables"}
        try:
            resp = requests.get(
                dfs_url,
                headers={"Authorization": f"Bearer {self._get_onelake_token()}"},
                params={"resource": "filesystem", "directory": "Tables", "recursive": "true"},
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            # Identify Delta tables: look for paths like .../<schema>/<table>/_delta_log
            seen: set[str] = set()
            tables = []
            schema_marker = f"/{schema}/"
            for p in resp.json().get("paths", []):
                name = p.get("name", "")
                if schema_marker not in name or "/_delta_log" not in name:
                    continue
                # Extract table name from .../<schema>/<table_name>/_delta_log/...
                after_schema = name.split(schema_marker, 1)[-1]
                table_name = after_schema.split("/", 1)[0]
                if table_name and table_name not in seen and table_name not in system_dirs:
                    seen.add(table_name)
                    tables.append({"name": table_name, "type": "Managed", "format": "Delta"})
            return tables
        except Exception as e:
            logger.warning("DFS table listing failed: %s", e)
            return []

    # ── jobs ──────────────────────────────────────────────────────

    def run_job(self, workspace_id: str, item_id: str, job_type: str = "DefaultJob") -> str:
        """Start a job and return the job instance ID."""
        resp = self._post(
            f"workspaces/{workspace_id}/items/{item_id}/jobs/instances",
            params={"jobType": job_type},
        )
        # 202 Accepted — location header has the job instance URL
        location = resp.headers.get("Location", "")
        # Extract job instance ID from location URL
        return location.rsplit("/", 1)[-1] if location else ""

    def get_job_status(self, workspace_id: str, item_id: str, job_instance_id: str) -> dict:
        return self._get(
            f"workspaces/{workspace_id}/items/{item_id}/jobs/instances/{job_instance_id}"
        ).json()

    def wait_for_job(
        self,
        workspace_id: str,
        item_id: str,
        job_instance_id: str,
        timeout: int = 600,
        poll_interval: int = 15,
    ) -> dict:
        """Poll until job completes or times out. Returns final job status."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.get_job_status(workspace_id, item_id, job_instance_id)
            state = status.get("status", "Unknown")
            if state in ("Completed", "Failed", "Cancelled", "Deduped"):
                return status
            logger.info("Job %s status: %s, waiting %ds...", job_instance_id[:8], state, poll_interval)
            time.sleep(poll_interval)
        raise TimeoutError(f"Job {job_instance_id} did not complete within {timeout}s")

    # ── shortcuts ─────────────────────────────────────────────────

    def create_shortcut(
        self,
        workspace_id: str,
        item_id: str,
        shortcut_name: str,
        path: str,
        target_workspace_id: str,
        target_item_id: str,
        target_path: str,
    ):
        body = {
            "name": shortcut_name,
            "path": path,
            "target": {
                "oneLake": {
                    "workspaceId": target_workspace_id,
                    "itemId": target_item_id,
                    "path": target_path,
                }
            },
        }
        self._post(f"workspaces/{workspace_id}/items/{item_id}/shortcuts", json=body)

    def list_shortcuts(self, workspace_id: str, item_id: str) -> list[dict]:
        try:
            resp = self._get(f"workspaces/{workspace_id}/items/{item_id}/shortcuts")
            return resp.json().get("value", [])
        except FabricError as e:
            if e.status_code == 404:
                return []
            raise

    # ── item properties (via type-specific endpoint) ──────────────

    def get_lakehouse_properties(self, workspace_id: str, lakehouse_id: str) -> dict:
        """Return lakehouse properties including SQL endpoint info."""
        lh = self.get_lakehouse(workspace_id, lakehouse_id)
        return lh.get("properties", {})
