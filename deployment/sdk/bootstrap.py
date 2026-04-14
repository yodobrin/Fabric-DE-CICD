#!/usr/bin/env python3
"""CLI entry point for Fabric DE workspace bootstrap.

Subcommands:

    # Diff mode — show what would happen, no changes:
    python3 bootstrap.py deploy --workspace-name my-ws --existing-workspace --diff

    # Full bootstrap (production):
    python3 bootstrap.py deploy --workspace-name my-ws --existing-workspace

    # Full bootstrap (daily ring):
    python3 bootstrap.py deploy --workspace-name my-ws --existing-workspace \
        --base-url dailyapi.powerbi.com

    # State check with JSON output:
    python3 bootstrap.py status --workspace-name my-ws --existing-workspace --output json

    # Update existing items in-place (where supported):
    python3 bootstrap.py deploy --workspace-name my-ws --existing-workspace --on-exists update

    # Run a single phase:
    python3 bootstrap.py deploy --workspace-name my-ws --existing-workspace --phase copy_jobs

    # Deploy a single item:
    python3 bootstrap.py deploy-item --workspace-name my-ws --existing-workspace --item semantic_model

    # Run a single job:
    python3 bootstrap.py run-job --workspace-name my-ws --existing-workspace --item nb_transformations
"""

import argparse
import logging
import sys
from pathlib import Path

from config import load_config
from fabric_client import FabricClient
from deployer import Deployer


# ── Shared CLI setup ──────────────────────────────────────────────────────────

def _add_common_args(parser: argparse.ArgumentParser):
    parser.add_argument("--workspace-name", required=True, help="Fabric workspace display name")
    parser.add_argument("--existing-workspace", action="store_true", help="Use existing workspace")
    parser.add_argument("--capacity-id", help="Fabric capacity ID (for new workspaces)")
    parser.add_argument("--base-url", default=None, help="Fabric API host override")
    parser.add_argument("--config", default=None, help="Path to workspace_config.yml")
    parser.add_argument("--base-dir", default=None, help="Path to deployment/ directory")
    parser.add_argument("--on-exists", choices=["skip", "update", "force"], default="skip",
                        help="skip: leave existing | update: in-place update (where supported) | force: delete+recreate")
    parser.add_argument("--output", choices=["table", "json"], default="table", help="Output format")
    parser.add_argument("--verbose", "-v", action="store_true")


def _setup(args) -> tuple[FabricClient, str, 'config.WorkspaceConfig', Path]:
    """Common setup: logging, config, client, workspace resolution."""
    import config as config_mod  # noqa: used for type hint

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%H:%M:%S")
    if not args.verbose:
        for name in ("azure", "urllib3", "msal"):
            logging.getLogger(name).setLevel(logging.WARNING)

    cfg = load_config(args.config)
    api_host = args.base_url or cfg.fabric.api_host

    if not args.existing_workspace and not (args.capacity_id or cfg.fabric.capacity_id):
        print("Error: --capacity-id required when creating a new workspace.", file=sys.stderr)
        sys.exit(1)

    base_dir = Path(args.base_dir) if args.base_dir else Path(__file__).resolve().parent.parent
    if not (base_dir / "workshop_template").exists():
        print(f"Error: workshop_template/ not found in {base_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"\n_ Connecting to Fabric API ({api_host})...")
    client = FabricClient(base_host=api_host)

    if args.existing_workspace:
        print(f"_ Looking up workspace: {args.workspace_name}")
        ws = client.get_workspace_by_name(args.workspace_name)
        if ws is None:
            print(f"Error: Workspace '{args.workspace_name}' not found.", file=sys.stderr)
            sys.exit(1)
        workspace_id = ws["id"]
        print(f"  Workspace ID: {workspace_id}")
    else:
        cap = args.capacity_id or cfg.fabric.capacity_id
        print(f"_ Creating workspace: {args.workspace_name}")
        ws = client.create_workspace(args.workspace_name, capacity_id=cap)
        workspace_id = ws["id"]
        print(f"  Created. Workspace ID: {workspace_id}")

    return client, workspace_id, cfg, base_dir


# ── Subcommands ───────────────────────────────────────────────────────────────

def cmd_deploy(args):
    client, workspace_id, cfg, base_dir = _setup(args)
    deployer = Deployer(client=client, workspace_id=workspace_id, cfg=cfg,
                        base_dir=base_dir, on_exists=args.on_exists,
                        output_format=args.output)
    phases = [args.phase] if args.phase else None
    deployer.run(diff_only=args.diff, phases=phases)


def cmd_status(args):
    client, workspace_id, cfg, _ = _setup(args)
    deployer = Deployer(client=client, workspace_id=workspace_id, cfg=cfg,
                        base_dir=Path("."), on_exists=args.on_exists,
                        output_format=args.output)
    deployer.check_state()


def cmd_deploy_item(args):
    client, workspace_id, cfg, base_dir = _setup(args)
    deployer = Deployer(client=client, workspace_id=workspace_id, cfg=cfg,
                        base_dir=base_dir, on_exists=args.on_exists,
                        output_format=args.output)
    deployer.deploy_item(args.item)


def cmd_run_job(args):
    client, workspace_id, cfg, _ = _setup(args)
    deployer = Deployer(client=client, workspace_id=workspace_id, cfg=cfg,
                        base_dir=Path("."), on_exists=args.on_exists,
                        output_format=args.output)
    deployer.run_job(args.item)


def cmd_verify(args):
    from state import assess, compute_actions
    from verify import run_verifications, display_verifications

    client, workspace_id, cfg, _ = _setup(args)
    state = assess(client, workspace_id, cfg)
    compute_actions(state, cfg)
    check_keys = [k.strip() for k in args.check.split(",")] if args.check else None
    results = run_verifications(client, workspace_id, cfg, state, keys=check_keys)
    display_verifications(results, args.output)
    # Exit non-zero if any check failed (useful for CI)
    if any(not r.passed for r in results):
        sys.exit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="bootstrap",
        description="Fabric DE workspace bootstrap — config-driven, idempotent deployment",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # deploy
    p_deploy = sub.add_parser("deploy", help="Full or phased deployment")
    _add_common_args(p_deploy)
    p_deploy.add_argument("--diff", action="store_true", help="Show planned actions without deploying")
    p_deploy.add_argument("--phase", default=None, help="Run a single phase by name")
    p_deploy.set_defaults(func=cmd_deploy)

    # status
    p_status = sub.add_parser("status", help="Show workspace state assessment")
    _add_common_args(p_status)
    p_status.set_defaults(func=cmd_status)

    # deploy-item
    p_item = sub.add_parser("deploy-item", help="Deploy a single item by config key")
    _add_common_args(p_item)
    p_item.add_argument("--item", required=True, help="Config key of the item to deploy")
    p_item.set_defaults(func=cmd_deploy_item)

    # run-job
    p_job = sub.add_parser("run-job", help="Run a single job (CopyJob or Notebook)")
    _add_common_args(p_job)
    p_job.add_argument("--item", required=True, help="Config key of the item to run")
    p_job.set_defaults(func=cmd_run_job)

    # verify
    p_verify = sub.add_parser("verify", help="Run verification queries against lakehouse SQL endpoints")
    _add_common_args(p_verify)
    p_verify.add_argument("--check", default=None, help="Comma-separated verification keys (default: all)")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
