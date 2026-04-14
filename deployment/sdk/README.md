# Fabric DE Bootstrap SDK

Config-driven, idempotent Python toolkit for bootstrapping Microsoft Fabric Data Engineering workspaces. Deploys lakehouses, environments, notebooks, copy jobs, shortcuts, semantic models, and reports — with a desired-vs-current state engine that makes every run safe to retry.

## Architecture

```
bootstrap.py          CLI entry point (subcommands: deploy, status, deploy-item, run-job)
     │
     ▼
config.py ◄────────── workspace_config.yml   (all item names, placeholders, phases)
     │
     ▼
deployer.py           Phase orchestrator — reads config, drives deployment
     │
     ├──► state.py        Desired-vs-current state engine
     ├──► templates.py    Staging + placeholder replacement
     └──► fabric_client.py   REST client (Fabric API + OneLake DFS)
```

## Files

| File | Purpose |
|---|---|
| `workspace_config.yml` | **The single source of truth.** Declares all items, placeholder GUIDs, shortcuts, data expectations, and deployment phases. To adapt this SDK for a different workspace layout, edit only this file. |
| `config.py` | Loads `workspace_config.yml` into typed dataclasses (`WorkspaceConfig`, `ItemDef`, `ShortcutDef`, `PhaseDef`, etc.). Every other module consumes these types rather than raw strings. |
| `fabric_client.py` | Thin REST client for the Fabric data-plane API. Handles auth (via `azure-identity`), token caching, retry with backoff on transient errors, and pagination. Also provides OneLake DFS table listing for schema-enabled lakehouses. |
| `state.py` | The state engine. `assess()` queries the workspace and returns a `WorkspaceState` with every declared item, data expectation, and shortcut marked as `exists` or `missing`. This is what makes deployments idempotent. |
| `templates.py` | Copies `workshop_template/` into a staging area and replaces all placeholder GUIDs with real workspace/item IDs. A single `replace_all_placeholders()` call handles every item type. |
| `deployer.py` | The orchestrator. Reads the `phases` list from config and executes them in order. Each phase can deploy items, run jobs, or create shortcuts. Exposes `deploy_item()` and `run_job()` for targeted operations. |
| `bootstrap.py` | CLI with four subcommands: `deploy`, `status`, `deploy-item`, `run-job`. Handles workspace resolution (lookup or create) and wires everything together. |

## Quick Start

```bash
# Install dependencies
pip3 install azure-identity requests fabric-cicd pyyaml

# Authenticate (any azure-identity credential works)
az login --tenant <tenant-id>

# Check workspace state
python3 bootstrap.py status \
  --workspace-name my-workspace \
  --existing-workspace

# Full deployment (idempotent — safe to re-run)
python3 bootstrap.py deploy \
  --workspace-name my-workspace \
  --existing-workspace

# Daily ring
python3 bootstrap.py deploy \
  --workspace-name my-workspace \
  --existing-workspace \
  --base-url dailyapi.powerbi.com

# Diff mode — show planned actions, no changes
python3 bootstrap.py deploy \
  --workspace-name my-workspace \
  --existing-workspace \
  --diff
```

## Usage Modes

### Full deployment
```bash
python3 bootstrap.py deploy --workspace-name ws --existing-workspace
```
Runs all phases declared in `workspace_config.yml`. Skips items that already exist.

### Diff mode (replaces dry-run)
```bash
python3 bootstrap.py deploy --workspace-name ws --existing-workspace --diff
```
Shows each resource with its planned action (`+ create`, `~ update`, `─ skip`, `▶ run`, `⊘ blocked`, `! recreate`) without making any changes.

### Update existing items in-place
```bash
python3 bootstrap.py deploy --workspace-name ws --existing-workspace --on-exists update
```
Pushes template changes to items that support [`updateDefinition`](https://learn.microsoft.com/en-us/rest/api/fabric/core/items/update-item-definition) without delete/recreate. Supported types: Notebook, CopyJob, Environment, SemanticModel, Report ([full list](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/item-definition-overview)).

### JSON structured output
```bash
python3 bootstrap.py status --workspace-name ws --existing-workspace --output json
```
Machine-readable output for CI/CD pipelines. Works with all subcommands.

### Single phase
```bash
python3 bootstrap.py deploy --workspace-name ws --existing-workspace --phase copy_jobs
```

### Deploy a single item
```bash
python3 bootstrap.py deploy-item --workspace-name ws --existing-workspace --item semantic_model
```

### Run a single job
```bash
python3 bootstrap.py run-job --workspace-name ws --existing-workspace --item nb_transformations
```

### State check
```bash
python3 bootstrap.py status --workspace-name ws --existing-workspace
```
Outputs a table showing every resource, its state, and the action that would be taken.

### Force recreate
```bash
python3 bootstrap.py deploy --workspace-name ws --existing-workspace --on-exists force
```
Deletes and recreates items that already exist.

## Configuration

Everything is driven by `workspace_config.yml`. Key sections:

### `items`
Declares every Fabric item to deploy. Each entry has:
- `type`: Fabric item type (Lakehouse, Notebook, CopyJob, etc.)
- `display_name`: Name in the workspace
- `template_folder`: Subfolder in `workshop_template/`
- `enable_schemas`: (Lakehouse only) create with schema support
- `default_lakehouse`: (Notebook only) key of the default lakehouse binding

### `placeholders`
GUIDs found in the template source files that get replaced with real IDs at deploy time. When you update template content, grab the new placeholder values from the template files and update this section.

### `shortcuts`
Shortcut definitions with `depends_on` gating — the shortcut is only created after its prerequisite data table exists.

### `data_expectations`
Tables that should exist after jobs/notebooks run. The state engine checks these to determine completeness, and phases use them as skip/gate conditions.

### `phases`
Ordered list of deployment phases. Each phase can:
- `deploy`: Create items (lakehouses first, then imports)
- `run_jobs`: Execute copy jobs or notebooks and wait for completion
- `actions`: Mixed list of shortcut keys and notebook keys to process

## Extending

### Adding a new item
1. Add a template folder under `workshop_template/`
2. Add an entry in `workspace_config.yml` under `items`
3. If the template has placeholder GUIDs, add them to `placeholders`
4. Add the item key to the appropriate phase in `phases`

### Adding a new shortcut
Add under `shortcuts` with `depends_on` pointing to the data expectation that must be satisfied first.

### Adding a new data expectation
Add under `data_expectations` with the `lakehouse` key, `table` name, and `produced_by` list of item keys.

### Custom auth
Pass any `azure-identity` `TokenCredential` to `FabricClient`:
```python
from azure.identity import ClientSecretCredential
from fabric_client import FabricClient

cred = ClientSecretCredential(tenant_id="...", client_id="...", client_secret="...")
client = FabricClient(base_host="api.fabric.microsoft.com", credential=cred)
```

### Programmatic use
```python
from config import load_config
from fabric_client import FabricClient
from deployer import Deployer
from state import assess, display

cfg = load_config("workspace_config.yml")
client = FabricClient(base_host=cfg.fabric.api_host)

# State check
state = assess(client, workspace_id="...", cfg=cfg)
display(state)

# Targeted deployment
deployer = Deployer(client, workspace_id="...", cfg=cfg, base_dir=Path("../"))
deployer.deploy_item("semantic_model")
deployer.run_job("nb_transformations")
```

## Known Workarounds

| Issue | Workaround |
|---|---|
| Schema-enabled lakehouses don't support the `/tables` REST endpoint | Falls back to OneLake DFS recursive listing, detecting Delta tables by `_delta_log` presence |
| DFS hostname differs per ring (daily vs prod) | Discovered dynamically from the lakehouse `oneLakeTablesPath` property |
| `fabric-cicd` hardcodes `api.powerbi.com` | Overridden at runtime via `constants.DEFAULT_API_ROOT_URL` |
| Non-recursive DFS listing doesn't show user tables in schema-enabled lakehouses | Uses recursive listing under `Tables/` and pattern-matches `/<schema>/<table>/_delta_log` |

## Fabric REST API References

| Feature | Documentation |
|---|---|
| Update Item Definition | [REST API](https://learn.microsoft.com/en-us/rest/api/fabric/core/items/update-item-definition) — in-place update without delete/recreate |
| Item Definition Overview | [Supported types & formats](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/item-definition-overview) |
| Notebook Definition | [Notebook definition structure](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/notebook-definition) |
| Semantic Model Definition | [TMDL definition structure](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/semantic-model-definition) |
| Report Definition | [PBIR definition structure](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/report-definition) |
| Copy Job Definition | [Copy job definition structure](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/copyjob-definition) |
| Environment Definition | [Environment definition structure](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/environment-definition) |
| OneLake Shortcuts | [Create Shortcut API](https://learn.microsoft.com/en-us/rest/api/fabric/core/onelake-shortcuts/create-shortcut) |
| Job Scheduler | [Run on-demand item job](https://learn.microsoft.com/en-us/rest/api/fabric/core/job-scheduler/run-on-demand-item-job) |
| Lakehouse Tables | [List Tables API](https://learn.microsoft.com/en-us/rest/api/fabric/lakehouse/tables/list-tables) |

## Suggested Improvements

1. **Environment-scoped configs** — Support `workspace_config.dev.yml`, `workspace_config.prod.yml` with shared base + overrides
2. **Rollback support** — Track created items per run so a failed deployment can be unwound
3. **Webhook/callback** — Emit events per phase for integration with external orchestrators (AzDO, GitHub Actions)
4. **Token credential passthrough** — Accept SPN/managed identity credentials via env vars for non-interactive CI scenarios
5. **Tests** — Unit tests with mocked Fabric API responses; integration tests against a dedicated test workspace
