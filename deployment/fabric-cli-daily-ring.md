# Using Fabric CLI against the Daily Ring

## Problem

The Fabric CLI (`fab`) targets **production** (`api.fabric.microsoft.com`) by default. If your workspace lives on the **daily ring** (portal: `daily.powerbi.com`), the CLI cannot see it.

## How to point the CLI to daily

The CLI reads the API hostname from the environment variable `FAB_API_ENDPOINT_FABRIC`. The daily ring's backend API is **`dailyapi.powerbi.com`** (discovered from `https://daily.powerbi.com/metadata/cluster`).

```bash
export FAB_API_ENDPOINT_FABRIC=dailyapi.powerbi.com
fab auth login
# complete browser auth
fab -c "ls /"   # should now list daily-ring workspaces
```

## CLI bug: hostname validator rejects multi-level subdomains

### Versions affected

- `fab` version 1.5.0 (and likely earlier versions with the same validator)

### Root cause

The hostname validator in the Fabric CLI uses a regex that only allows **one** subdomain level:

```python
# File: fabric_cli/utils/fab_hostname_validator.py
VALID_HOSTNAME_REGEX = re.compile(
    r"^([\w-]+\.)?(fabric\.microsoft\.com|dfs\.fabric\.microsoft\.com|powerbi\.com|management\.[\w-]+\.[\w-]+)$"
)
```

The `?` quantifier means the `([\w-]+\.)` group matches zero or one times. Hostnames like `api.daily.fabric.microsoft.com` have **two** subdomain segments and fail validation.

### Secondary bug: circular import crash

When the hostname validation fails, the error handler references `fab_constant.ERROR_INVALID_HOSTNAME`, but this constant is defined at line 255 of `fab_constant.py` — **after** the validator is called at line 8 during module initialization. This causes an `AttributeError` instead of a clean error message:

```
AttributeError: partially initialized module 'fabric_cli.core.fab_constant' 
has no attribute 'ERROR_INVALID_HOSTNAME' (most likely due to a circular import)
```

### Fix

In the installed package, change `?` to `*` in the regex:

**File:** `/opt/homebrew/lib/python3.11/site-packages/fabric_cli/utils/fab_hostname_validator.py`

```diff
- r"^([\w-]+\.)?(fabric\.microsoft\.com|dfs\.fabric\.microsoft\.com|powerbi\.com|management\.[\w-]+\.[\w-]+)$"
+ r"^([\w-]+\.)*(fabric\.microsoft\.com|dfs\.fabric\.microsoft\.com|powerbi\.com|management\.[\w-]+\.[\w-]+)$"
```

This allows multiple subdomain levels while still restricting to Microsoft Fabric domains.

### Note

This patch only matters if you try a hostname like `api.daily.fabric.microsoft.com`. The actual daily API hostname (`dailyapi.powerbi.com`) already passes the original regex since it's a single subdomain of `powerbi.com`. The patch is still recommended to fix the general bug.

## auth status display is misleading

After switching to the daily ring, `fab auth status` still shows:

```
✓ Logged in to app.fabric.microsoft.com
```

This is **hardcoded** (line 270 of `fab_auth.py`) and does not reflect the actual endpoint. Verify by running `fab -c "ls /"` and checking that you see your daily-ring workspaces.

## Spark environment capacity limits

The workshop template's `MyEnv.Environment/Setting/Sparkcompute.yml` defaults to:

```yaml
executor_cores: 4
executor_memory: 28g
max_executors: 9
```

This totals 40 cores / 280g memory (4 × 10 instances). Trial or smaller capacities may have a lower limit (e.g., 24 cores / 168g). If you get a `SparkSettingsComputeExceedsPoolLimit` error, reduce `max_executors`:

```yaml
max_executors: 4   # 4 cores × 5 instances = 20 cores / 140g
```

## Quick reference

```bash
# Set daily environment
export FAB_API_ENDPOINT_FABRIC=dailyapi.powerbi.com

# Login
fab auth login

# Verify
fab -c "ls /"

# Run bootstrap against an existing workspace
cd deployment
./bootstrap.sh --workspace-name <your-ws-name> --existing-workspace
```
