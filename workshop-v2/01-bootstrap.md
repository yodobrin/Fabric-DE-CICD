# Module 1: Bootstrap a Workspace from Scratch

> **User Story:** *As a Platform Engineer, I want to provision a fully working Fabric workspace from a single command, so that new projects and team members can start working in minutes instead of hours of manual setup.*

**Duration:** 25 minutes | **Persona:** Platform Engineer | **Depends on:** Module 0

## Context

Your team needs a new Fabric workspace for development. Instead of clicking through the portal to create 10+ items, configure connections, run jobs, and create shortcuts — you run one command.

## Exercise 1: Create the Workspace (2 min)

1. Open the Fabric portal
2. Create a new empty workspace (e.g., `DEWorkshop_<yourname>`)
3. Assign it to a capacity

> **Note:** The SDK can also create workspaces via `--capacity-id`, but most orgs prefer portal/IaC for workspace creation due to governance.

## Exercise 2: Preview What Will Happen (3 min)

```bash
cd deployment/sdk

python3 bootstrap.py deploy \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace \
    --diff
```

**Expected output:** 10 items to create, 5 blocked (data + shortcuts that depend on items being created first).

Study the diff:
- `+ create` — items that will be created from templates
- `⊘ blocked` — data and shortcuts that can't be created until their dependencies exist
- The phases will unblock these automatically during deployment

## Exercise 3: Run the Full Bootstrap (15 min)

```bash
python3 bootstrap.py deploy \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace
```

Watch the phases execute:
1. **Items** — lakehouses, environment, notebooks, copy jobs created
2. **Copy Jobs** — run in parallel, wait for completion
3. **Shortcuts & Notebooks** — shortcuts created, Bronze + Transformations notebooks run
4. **Semantic Layer** — semantic model + report deployed

## Exercise 4: Verify (2 min)

```bash
python3 bootstrap.py verify \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace
```

**Expected:** 6/6 checks passed — all tables exist with data.

## Exercise 5: Explore the Config (3 min)

Open `deployment/sdk/workspace_config.yml` and find:
- Where the item names are declared (`items:`)
- Where the phase ordering is defined (`phases:`)
- Where the verification queries are (`verifications:`)
- Where placeholder GUIDs are listed (`placeholders:`)

> **Discussion:** What would you change to add a third lakehouse (Gold)? What config entries would you add?

## Checkpoint

- [ ] Workspace has 10 items visible in Fabric portal
- [ ] `verify` shows 6/6 passed
- [ ] You can explain what each phase does
- [ ] You understand the relationship between `workspace_config.yml` and the deployment

## Key Takeaway

> The workspace was bootstrapped from **templates** with **placeholder GUIDs** that got replaced with real IDs at deploy time. Every subsequent module works with **incremental changes** — you never need to run the full bootstrap again.
