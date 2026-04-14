"""Template preparation: copy workshop templates to staging, replace metadata.

All placeholder values come from ``WorkspaceConfig.placeholders`` — nothing is
hardcoded here.  The ``replace_all_placeholders()`` function is the single
entry point that handles every item type.
"""

import logging
import shutil
from pathlib import Path

from config import WorkspaceConfig

logger = logging.getLogger(__name__)

WORKSHOP_TEMPLATE_DIR = "workshop_template"
STAGING_DIR = "tmp"


def prepare_staging(base_dir: Path) -> Path:
    """Copy workshop_template/ into a staging directory and return its path."""
    src = base_dir / WORKSHOP_TEMPLATE_DIR
    dst = base_dir / STAGING_DIR
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    # fabric-cicd expects a valid parameter.yml — create a no-op one
    param_file = dst / "parameter.yml"
    if not param_file.exists():
        param_file.write_text("find_replace: []\n")
    logger.info("Staging directory prepared: %s", dst)
    return dst


def cleanup_staging(base_dir: Path):
    dst = base_dir / STAGING_DIR
    if dst.exists():
        shutil.rmtree(dst)
        logger.info("Staging directory cleaned up")


def replace_in_file(file_path: Path, old: str, new: str):
    """Replace all occurrences of *old* with *new* in a file."""
    if not old:
        return
    try:
        text = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        return  # skip binary files
    if old not in text:
        return
    file_path.write_text(text.replace(old, new), encoding="utf-8")
    logger.debug("Replaced in %s: %s → %s", file_path.name, old[:30], new[:30])


def replace_all_placeholders(
    staging_dir: Path,
    cfg: WorkspaceConfig,
    *,
    workspace_id: str,
    resolved_ids: dict[str, str],
    silver_sql_conn_string: str = "",
    silver_sql_endpoint_id: str = "",
    semantic_model_id: str = "",
):
    """Walk the staging directory and replace all placeholder GUIDs.

    Args:
        staging_dir: Path to the staged copy of ``workshop_template/``.
        cfg: The loaded workspace configuration.
        workspace_id: Real workspace ID.
        resolved_ids: Mapping of config item key → real Fabric item ID.
        silver_sql_conn_string: Real SQL connection string for the silver lakehouse.
        silver_sql_endpoint_id: Real SQL endpoint ID for the silver lakehouse.
        semantic_model_id: Real semantic model ID (for report binding).
    """
    ph = cfg.placeholders
    replacements: list[tuple[str, str]] = [
        (ph.workspace_id, workspace_id),
        (ph.bronze_lakehouse_id, resolved_ids.get("lakehouse_bronze", "")),
        (ph.silver_lakehouse_id, resolved_ids.get("lakehouse_silver", "")),
        (ph.silver_sql_conn_str, silver_sql_conn_string),
        (ph.silver_sql_conn_id, silver_sql_endpoint_id),
        (ph.semantic_model_id, semantic_model_id),
    ]

    # Apply replacements to every text file in staging
    for file_path in staging_dir.rglob("*"):
        if not file_path.is_file():
            continue
        # Skip binary files
        if file_path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2"}:
            continue
        for old, new in replacements:
            if old and new:
                replace_in_file(file_path, old, new)
