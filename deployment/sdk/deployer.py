"""Phased deployment orchestrator for Fabric DE workspace bootstrap.

The ``Deployer`` reads a ``WorkspaceConfig`` and executes the declared phases
in order.  Each phase can:
  - **deploy** items (create lakehouses, import from templates via fabric-cicd)
  - **run_jobs** (copy jobs, notebook runs) and wait for completion
  - **create shortcuts** with retry logic

Individual phases or single items can be run independently, making the class
useful for targeted deployments, not only full bootstraps.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config import WorkspaceConfig, ItemDef
from fabric_client import FabricClient, FabricError
from state import WorkspaceState, assess, compute_actions, display
from templates import prepare_staging, cleanup_staging, replace_all_placeholders

logger = logging.getLogger(__name__)


def _print(msg: str):
    print(msg, flush=True)


class Deployer:
    """Orchestrates deployment of Fabric workspace items driven by config.

    Args:
        client: Authenticated Fabric REST client.
        workspace_id: Target workspace ID.
        cfg: Parsed workspace configuration.
        base_dir: Path to the ``deployment/`` directory containing
            ``workshop_template/``.
        on_exists: ``"skip"`` to leave existing items, ``"force"``
            to delete and recreate.
    """

    def __init__(
        self,
        client: FabricClient,
        workspace_id: str,
        cfg: WorkspaceConfig,
        base_dir: Path,
        on_exists: str = "skip",
        output_format: str = "table",
    ):
        self.client = client
        self.workspace_id = workspace_id
        self.cfg = cfg
        self.base_dir = base_dir
        self.on_exists = on_exists
        self.output_format = output_format
        self.staging_dir: Path | None = None
        self.state: WorkspaceState | None = None

    # ── public entry points ───────────────────────────────────

    def run(self, diff_only: bool = False, phases: list[str] | None = None):
        """Execute the full bootstrap (or selected phases).

        Args:
            diff_only: Assess state and show planned actions without deploying.
            phases: Optional list of phase names to run.  *None* runs all.
        """
        _print("\n_ Assessing workspace state...")
        self.state = assess(self.client, self.workspace_id, self.cfg)
        compute_actions(self.state, self.cfg, self.on_exists)
        display(self.state, self.output_format)

        if diff_only:
            if self.output_format == "table":
                _print("Diff only — no changes applied.")
            return

        if self.state.all_done:
            if self.output_format == "table":
                _print("Nothing to do.")
            return

        self.staging_dir = prepare_staging(self.base_dir)
        try:
            for phase_def in self.cfg.phases:
                if phases and phase_def.name not in phases:
                    continue
                self._run_phase(phase_def)
                self._refresh_state()
        finally:
            cleanup_staging(self.base_dir)

        if self.output_format == "table":
            _print(f"\n{'=' * 55}")
            _print(f"  Bootstrap complete: {self.state.workspace_name}")
            _print(f"  Workspace ID: {self.workspace_id}")
            _print(f"{'=' * 55}")

    def deploy_item(self, key: str):
        """Deploy a single item by its config key (create or import)."""
        item_def = self.cfg.get_item(key)
        self._refresh_state()
        if self.staging_dir is None:
            self.staging_dir = prepare_staging(self.base_dir)
            self._apply_placeholders()
        if item_def.type == "Lakehouse":
            self._ensure_lakehouse(item_def)
        else:
            self._ensure_import(item_def)

    def run_job(self, key: str):
        """Run a single job (CopyJob or Notebook) by its config key."""
        self._refresh_state()
        item_def = self.cfg.get_item(key)
        item_id = self.state.item_id(key)
        if not item_id:
            raise RuntimeError(f"Item {key} ({item_def.display_name}) not found in workspace")
        job_type = "CopyJob" if item_def.type == "CopyJob" else "RunNotebook"
        self._run_job_and_wait(item_id, item_def.display_name, job_type)

    def check_state(self) -> WorkspaceState:
        """Assess and display workspace state without deploying."""
        self.state = assess(self.client, self.workspace_id, self.cfg)
        compute_actions(self.state, self.cfg, self.on_exists)
        display(self.state, self.output_format)
        return self.state

    # ── phase dispatch ────────────────────────────────────────

    def _run_phase(self, phase_def):
        from config import PhaseDef
        p: PhaseDef = phase_def

        _print(f"\n═ Phase: {p.name} — {p.description}")

        # Skip-if-done gate
        if p.skip_if_done and self.state.is_done(p.skip_if_done):
            _print(f"  [skip] {p.skip_if_done} already satisfied")
            return

        # Deploy items
        if p.deploy:
            self._do_deploy(p.deploy)

        # Run jobs
        if p.run_jobs:
            self._do_run_jobs(p.run_jobs)

        # Actions (shortcuts + notebook runs mixed)
        if p.actions:
            self._do_actions(p.actions)

    # ── deploy ────────────────────────────────────────────────

    def _do_deploy(self, keys: list[str]):
        # First deploy lakehouses, then refresh to get IDs for placeholder replacement
        lh_keys = [k for k in keys if self.cfg.get_item(k).type == "Lakehouse"]
        other_keys = [k for k in keys if k not in lh_keys]

        for k in lh_keys:
            self._ensure_lakehouse(self.cfg.get_item(k))

        if lh_keys:
            self._refresh_state()
            self._apply_placeholders()

        for k in other_keys:
            # Re-apply placeholders before each import — earlier imports may have
            # produced new IDs that subsequent items reference (e.g. Report → SemanticModel).
            self._refresh_state()
            self._apply_placeholders()
            self._ensure_import(self.cfg.get_item(k))

    def _ensure_lakehouse(self, item_def: ItemDef):
        if self.state.is_done(item_def.key) and self.on_exists != "force":
            _print(f"  [skip] {item_def.display_name}.Lakehouse exists")
            return
        if self.state.is_done(item_def.key):
            _print(f"  [force] removing {item_def.display_name}.Lakehouse")
            item = self.client.get_item_by_name(
                self.workspace_id, item_def.display_name, "Lakehouse")
            if item:
                self.client.delete_item(self.workspace_id, item["id"])
                self._wait_for_name_available(item_def.display_name)
        _print(f"  Creating {item_def.display_name}.Lakehouse...")
        self.client.create_lakehouse(
            self.workspace_id, item_def.display_name, enable_schemas=item_def.enable_schemas)
        _print(f"  ✓ {item_def.display_name}.Lakehouse created")

    def _ensure_import(self, item_def: ItemDef):
        if self.state.is_done(item_def.key) and self.on_exists == "skip":
            _print(f"  [skip] {item_def.display_name}.{item_def.type} exists")
            return
        if self.state.is_done(item_def.key) and self.on_exists == "update":
            if item_def.supports_update_definition:
                _print(f"  [update] {item_def.display_name}.{item_def.type}...")
                self._import_via_fabric_cicd(item_def.type)
                _print(f"  ✓ {item_def.display_name}.{item_def.type} updated")
                return
            else:
                _print(f"  [skip] {item_def.display_name}.{item_def.type} (update not supported)")
                return
        if self.state.is_done(item_def.key) and self.on_exists == "force":
            _print(f"  [force] removing {item_def.display_name}.{item_def.type}")
            item = self.client.get_item_by_name(
                self.workspace_id, item_def.display_name, item_def.type)
            if item:
                self.client.delete_item(self.workspace_id, item["id"])
                self._wait_for_name_available(item_def.display_name)
        _print(f"  Importing {item_def.display_name}.{item_def.type}...")
        self._import_via_fabric_cicd(item_def.type)
        _print(f"  ✓ {item_def.display_name}.{item_def.type} imported")

    def _import_via_fabric_cicd(self, item_type: str):
        """Import items of *item_type* from staging via fabric-cicd."""
        from fabric_cicd import FabricWorkspace, publish_all_items, constants as fc_constants

        api_root = self.client._base.rsplit("/v1", 1)[0]
        fc_constants.DEFAULT_API_ROOT_URL = api_root
        fc_constants.FABRIC_API_ROOT_URL = api_root

        target = FabricWorkspace(
            workspace_id=self.workspace_id,
            repository_directory=str(self.staging_dir),
            item_type_in_scope=[item_type],
            token_credential=self.client._credential,
        )
        publish_all_items(target)

    # ── run jobs ──────────────────────────────────────────────

    def _do_run_jobs(self, keys: list[str]):
        job_runs: list[tuple[str, str, str]] = []
        for k in keys:
            item_def = self.cfg.get_item(k)
            item_id = self.state.item_id(k)
            if not item_id:
                _print(f"  [skip] {item_def.display_name} not found — cannot run")
                continue
            job_type = "CopyJob" if item_def.type == "CopyJob" else "RunNotebook"
            _print(f"  Running {item_def.display_name}...")
            try:
                jid = self.client.run_job(self.workspace_id, item_id, job_type=job_type)
                job_runs.append((item_def.display_name, item_id, jid))
                _print(f"    Started: {jid[:8]}...")
            except FabricError as e:
                logger.warning("Failed to start %s: %s", item_def.display_name, e)

        if not job_runs:
            return

        # Wait for all jobs in parallel
        _print(f"  Waiting for {len(job_runs)} job(s)...")

        def _wait_one(args):
            name, item_id, jid = args
            try:
                result = self.client.wait_for_job(
                    self.workspace_id, item_id, jid, timeout=600, poll_interval=15)
                return name, result.get("status", "Unknown")
            except TimeoutError:
                return name, "TimedOut"

        with ThreadPoolExecutor(max_workers=len(job_runs)) as pool:
            futures = {pool.submit(_wait_one, jr): jr[0] for jr in job_runs}
            for future in as_completed(futures):
                name, status = future.result()
                sym = "✓" if status == "Completed" else "✗"
                _print(f"    {sym} {name}: {status}")

    # ── actions (shortcuts + notebook runs) ───────────────────

    def _do_actions(self, keys: list[str]):
        for k in keys:
            if k in self.cfg.shortcuts:
                self._do_shortcut(k)
            elif k in self.cfg.items:
                self._do_notebook_run(k)
            else:
                logger.warning("Unknown action key: %s", k)

    def _do_shortcut(self, key: str):
        sc = self.cfg.shortcuts[key]
        self._refresh_state()

        if self.state.is_done(key):
            _print(f"  [skip] shortcut {sc.name} already exists")
            return
        if sc.depends_on and not self.state.is_done(sc.depends_on):
            _print(f"  [blocked] shortcut {sc.name}: {sc.depends_on} not ready")
            return

        location_id = self.state.item_id(sc.location_lakehouse)
        target_id = self.state.item_id(sc.target_lakehouse)
        if not location_id or not target_id:
            _print(f"  [blocked] shortcut {sc.name}: lakehouse IDs missing")
            return

        _print(f"  Creating shortcut: {sc.name}...")
        for attempt in range(1, 13):
            try:
                self.client.create_shortcut(
                    workspace_id=self.workspace_id,
                    item_id=location_id,
                    shortcut_name=sc.name,
                    path=sc.path,
                    target_workspace_id=self.workspace_id,
                    target_item_id=target_id,
                    target_path=sc.target_path,
                )
                _print(f"    ✓ shortcut {sc.name} created")
                return
            except FabricError as e:
                if e.status_code == 404 and attempt < 12:
                    _print(f"    [retry {attempt}/12] waiting 15s...")
                    time.sleep(15)
                else:
                    raise

    def _do_notebook_run(self, key: str):
        item_def = self.cfg.get_item(key)
        # Find the data expectation this notebook produces
        de_key = ""
        for de in self.cfg.data_expectations.values():
            if key in de.produced_by:
                de_key = de.key
                break
        if de_key and self.state.is_done(de_key):
            _print(f"  [skip] {item_def.display_name}: output {de_key} already exists")
            return

        item_id = self.state.item_id(key)
        if not item_id:
            item = self.client.get_item_by_name(
                self.workspace_id, item_def.display_name, "Notebook")
            if item:
                item_id = item["id"]
        if not item_id:
            _print(f"  [blocked] {item_def.display_name} not found")
            return

        _print(f"  Running {item_def.display_name}...")
        self._run_job_and_wait(item_id, item_def.display_name, "RunNotebook")

    # ── helpers ───────────────────────────────────────────────

    def _run_job_and_wait(self, item_id: str, name: str, job_type: str):
        try:
            jid = self.client.run_job(self.workspace_id, item_id, job_type=job_type)
            _print(f"    Started: {jid[:8]}...")
            result = self.client.wait_for_job(
                self.workspace_id, item_id, jid, timeout=600, poll_interval=15)
            status = result.get("status", "Unknown")
            _print(f"    {'✓' if status == 'Completed' else '✗'} {name}: {status}")
        except (FabricError, TimeoutError) as e:
            _print(f"    ✗ {name} failed: {e}")

    def _apply_placeholders(self):
        """Apply all placeholder replacements to staged templates."""
        if not self.staging_dir:
            return
        replace_all_placeholders(
            self.staging_dir,
            self.cfg,
            workspace_id=self.workspace_id,
            resolved_ids=self.state.item_ids,
            silver_sql_conn_string=self.state.lakehouse_sql_conn_string("lakehouse_silver"),
            silver_sql_endpoint_id=self.state.lakehouse_sql_endpoint_id("lakehouse_silver"),
            semantic_model_id=self.state.item_id("semantic_model"),
        )

    def _refresh_state(self):
        self.client.invalidate_cache()
        self.state = assess(self.client, self.workspace_id, self.cfg)
        compute_actions(self.state, self.cfg, self.on_exists)

    def _wait_for_name_available(self, name: str, timeout: int = 120, interval: int = 10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            existing = self.client.get_item_by_name(self.workspace_id, name)
            if existing is None:
                return
            time.sleep(interval)
        logger.warning("Name '%s' still not available after %ds", name, timeout)
