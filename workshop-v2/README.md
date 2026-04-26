# Fabric CI/CD Workshop (v2) — Scenario-Driven

## The Problem

You're a team building a data product on Microsoft Fabric. You have lakehouses, notebooks, copy jobs, semantic models, and reports. Things work in the portal. Then reality hits:

- **"Our new hire spent two days setting up their workspace."** They followed a 30-step wiki page, missed step 14, and their shortcuts point to the wrong lakehouse.
- **"I changed a notebook and now the report is broken."** There's no undo button, no history, no way to know what changed.
- **"Someone needs to add a column to the core table."** Last time this happened, we rebuilt everything from scratch because we didn't know what else depended on it.
- **"We need a production environment."** You copied the workspace, but all the connections still point to dev. The semantic model shows dev data to production users.
- **"A deployment broke prod on Friday."** We reverted the notebook manually, but the data was already wrong. We spent the weekend fixing it.

These aren't edge cases. They are the daily reality of every data engineering team that grows beyond one person or one environment. Fabric gives you powerful tools for building — but the operational lifecycle (version, deploy, test, promote, recover) needs a deliberate approach.

## What This Tutorial Teaches

This is a self-paced tutorial that solves each of those problems through a real, working data pipeline. You'll build a medallion architecture (Bronze → Silver), connect it to Git, make changes, break things, and recover — all using the same tools you'll use in production.

**By the end, you'll have practiced:**

| Problem | Solution You'll Learn | Module |
|---------|----------------------|--------|
| Slow workspace setup | One-command bootstrap — empty workspace to all-green in 15 min | [Module 1](01-bootstrap.md) |
| No version history | Git integration — every change tracked, diffable, revertable | [Module 2](02-git-integration.md) |
| Fear of schema changes | Additive changes with diff preview and automated verification | [Module 4](04-additive-schema.md) |
| Broken connections after copy | Parameter remapping — same code, different GUIDs per environment | [Module 6](06-promotion.md) |
| No rollback plan | Git revert + idempotent re-run — recovery in minutes | [Module 7](07-rollback.md) |
| Manual verification | `verify` command — automated data checks after every deploy | [Modules 1-7](01-bootstrap.md) |

## Who This Is For

You don't need to be all of these people — but your team has them:

| Persona | Their Question | Modules For Them |
|---------|---------------|-----------------|
| **Data Engineer** | "Will my data survive this deployment?" | 3, 4, 7 |
| **Analytics Engineer** | "Will the report break if I change the model?" | 5 |
| **Platform Engineer** | "How do I stamp out workspaces consistently?" | 1, 8 |
| **DevOps Engineer** | "How do I promote to prod safely?" | 6, 7 |
| **Team Lead** | "How do I review what's changing?" | 4 (diff), 6 (PR) |
| **New Team Member** | "How do I get started?" | 0, 8 |

Each module names its primary persona so you can skip to what matters for your role — or go end-to-end to understand the full lifecycle.

## The Two Tools — And Why You Need Both

Fabric's **Git Integration** tracks item *definitions* — notebook code, semantic model TMDL, report layout. It's your version control, your code review surface, your audit trail.

But Git doesn't track *data*. It can't run a notebook, create a table, check if rows landed, or wire a shortcut. That's where the **SDK/CLI** comes in — it handles the data plane: executing jobs, verifying results, creating items, managing state.

```
Git Integration                    SDK / CLI
──────────────                    ─────────
✓ Track code changes              ✓ Run notebooks and copy jobs
✓ PR-based review                 ✓ Create lakehouses and shortcuts
✓ Revert definitions              ✓ Verify data correctness
✓ Sync across branches            ✓ Bootstrap new workspaces
✗ Run jobs                        ✓ Diff: see what will change
✗ Create data                     ✓ Promote across environments
✗ Verify correctness              ✓ JSON output for CI pipelines
```

**The pattern you'll repeat in every module:**
1. Edit code (locally or in Fabric)
2. Commit to Git → push
3. Git Integration pulls the definition into the workspace
4. SDK runs the job → data materializes
5. SDK verifies → confirms correctness

## What You'll Build

A practical data engineering solution using public datasets:

```
Azure Open Datasets (Parquet)
  ├─ CopyJob1 (diabetes)       ──→ Bronze dbo.t2
  └─ CopyJob2 (holidays)       ──→ Bronze dbo.t3_prod
                                       │
                          Bronze Notebook (sampling)
                          ├──→ dbo.t3_dev  (1%)
                          └──→ dbo.t3_test (10%)
                                       │
                          shortcut: dbo.t3 → t3_{stage}
                                       │
                      Transformations Notebook
                      (t2 FULL JOIN t3 → dbo.t1, then dbo.t5)
                                │
                      Semantic Model → Report
```

**10 Fabric items:** 2 lakehouses, 1 environment, 3 notebooks, 2 copy jobs, 1 semantic model, 1 report.

## How To Use This Tutorial

**Self-paced:** Work through the modules at your own speed. Each module has exercises, expected outputs, and a checkpoint.

**Workshop mode:** An instructor can run this as a 3.5-hour guided session with the agenda below.

**Pick your path:** If you're a Data Engineer, start at Module 0, do 1-4, skip 5 if you don't touch semantic models, do 7. If you're a Platform Engineer, do 0, 1, 6, 8.

## Modules

### Prerequisites

- Microsoft Fabric capacity (trial or premium)
- GitHub or Azure DevOps account — see [Git Integration Reference](git-integration-reference.md)
- Python 3.11+, `az login` working
- `pip install azure-identity requests fabric-cicd pyyaml`

### Agenda

| Module | Scenario | Persona Focus | Duration | Depends On |
|--------|----------|---------------|----------|------------|
| **—** | [Git Integration Reference](git-integration-reference.md) | All | ref | — |
| **0** | [Setup & Tooling](00-setup.md) | All | 20 min | — |
| **1** | [Bootstrap a Workspace from Scratch](01-bootstrap.md) | Platform Engineer | 25 min | Module 0 |
| **2** | [Connect to Git & Understand What's Versioned](02-git-integration.md) | All | 20 min | Module 1 |
| **3** | [Make a Code Change & Deploy It](03-code-change.md) | Data Engineer | 30 min | Module 2 |
| **4** | [Add a Table — Additive Schema Change](04-additive-schema.md) | Data Engineer | 30 min | Module 3 |
| **5** | [Update the Semantic Model & Report](05-semantic-layer.md) | Analytics Engineer | 25 min | Module 4 |
| **6** | [Promote to Production](06-promotion.md) | DevOps Engineer | 30 min | Module 5 |
| **7** | [Break Something & Recover](07-rollback.md) | DevOps + Data Engineer | 25 min | Module 6 |
| **8** | [Onboard a New Team Member](08-onboarding.md) | Platform Engineer | 15 min | Module 1 |

**Total:** ~3.5 hours hands-on + breaks

---

## Module Summaries

### Module 0: Setup & Tooling
> *As any team member, I want my local environment ready so I can follow along.*

- Install Python packages, verify `az login`
- Fork the repo, clone locally
- Understand the repo layout: `DE_Workshop/` (Git-synced items), `deployment/sdk/` (tooling)

### Module 1: Bootstrap a Workspace from Scratch
> *As a Platform Engineer, I want to provision a fully working workspace from a single command.*

- Run `bootstrap.py deploy` — watch it create 10 items, run copy jobs, create shortcuts, deploy the semantic layer
- Run `bootstrap.py verify` — confirm 6/6 data checks pass
- Understand: what the SDK does vs what Git integration does
- **Checkpoint:** All-green status + verify output

### Module 2: Connect to Git & Understand What's Versioned
> *As a team member, I want my workspace connected to Git so changes are tracked.*

- Connect workspace to GitHub branch via Fabric portal
- Examine `DE_Workshop/` — see `.platform` files, notebook `.py` format, TMDL, PBIR
- Understand what's versioned (definitions) vs what's not (data, schedules, capacity)
- Make a trivial change in Fabric → commit → see it in Git
- Edit a file in GitHub → pull into Fabric
- **Checkpoint:** Bi-directional sync working

### Module 3: Make a Code Change & Deploy It
> *As a Data Engineer, I want to fix a notebook and deploy the fix without rebuilding the lakehouse.*

- Edit the Transformations notebook locally (make `CREATE TABLE` idempotent → `CREATE OR REPLACE TABLE`)
- Commit to feature branch, push
- Run `bootstrap.py deploy-item --on-exists update --item nb_transformations`
- Run `bootstrap.py run-job --item nb_transformations` — verify data is correct
- Discuss: Git Integration pull vs SDK deploy — when to use which
- **Checkpoint:** Notebook updated, data intact, verify passes

### Module 4: Add a Table — Additive Schema Change
> *As a Data Engineer, I want to add table t5 without disrupting existing tables.*

- Add a SQL cell to Transformations notebook: `CREATE TABLE IF NOT EXISTS dbo.t5`
- Add data expectation + verification check to `workspace_config.yml`
- Run `bootstrap.py deploy --diff` — see `~ update` for notebook, `▶ run` for t5
- Deploy the notebook update, run it, verify t5 exists
- Confirm t1, t2, t3 are untouched
- **Checkpoint:** t5 verified, all other tables preserved

### Module 5: Update the Semantic Model & Report
> *As an Analytics Engineer, I want to expose t5 in the semantic model and add a visual to the report.*

- Add `t5.tmdl` to the semantic model definition
- Add `ref table t5` to `model.tmdl`
- Deploy with `--on-exists update --item semantic_model`
- Open the report in Fabric — verify t5 data is available
- Discuss: TMDL format, how measures and relationships are versioned
- **Checkpoint:** Semantic model shows t5, report loads

### Module 6: Promote to Production
> *As a DevOps Engineer, I want to promote changes from dev to production via PR.*

- Create a `production` branch from current state
- Create a new workspace `*_Prod` via Fabric "Branch out" or SDK
- Bootstrap the prod workspace: `bootstrap.py deploy --workspace-name *_Prod`
- Understand `parameter.yml` — how GUIDs get remapped across environments
- Run `verify` on prod
- Discuss: approval gates, environment-specific config, what `fabric-cicd` handles
- **Checkpoint:** Prod workspace all-green, items point to prod lakehouses

### Module 7: Break Something & Recover
> *As a DevOps Engineer, I want to recover from a bad deployment quickly.*

- Simulate a break: edit the Transformations notebook to produce wrong results (e.g., `WHERE 1=0`)
- Deploy + run — verify shows failure (t1 has 0 rows)
- Recovery option A: `git revert` → deploy → run → verify
- Recovery option B: re-run from a known-good notebook state
- Discuss: idempotent DDL, Delta time-travel, fix-forward vs rollback
- **Checkpoint:** Data restored, verify passes again

### Module 8: Onboard a New Team Member
> *As a new engineer, I want a personal workspace ready in minutes.*

- Create a new empty workspace
- Run the full bootstrap: `bootstrap.py deploy --workspace-name <name>`
- Verify all data
- Connect to a personal feature branch
- Discuss: isolation patterns, branch-per-developer vs shared dev workspace
- **Checkpoint:** New workspace all-green in < 15 minutes

---

## Key Concepts Thread

These ideas build across modules:

| Concept | Introduced | Reinforced | Mastered |
|---------|------------|------------|----------|
| **Git = definitions, SDK = data** | Module 2 (the table) | Module 3 (Git pulls code, SDK runs it) | Module 7 (Git reverts code, SDK re-runs) |
| **Idempotency** | Module 1 (bootstrap is re-runnable) | Module 3 (CREATE OR REPLACE) | Module 7 (recovery by re-run) |
| **Diff before apply** | Module 1 (`--diff`) | Module 4 (see what will change) | Module 6 (PR review) |
| **Incremental change** | Module 3 (update one item) | Module 4 (add table, keep others) | Module 5 (model + report update) |
| **Verification** | Module 1 (`verify`) | Module 4 (new check for t5) | Module 7 (verify detects the break) |
| **Git Integration + SDK** | Module 2 (connect + bi-directional) | Module 3 (Git pulls, SDK runs) | Module 4 (Git for code, SDK for data) |

## When to Use Git Integration vs SDK

This workshop deliberately uses **both** to show where each fits:

| Capability | Git Integration | SDK / CLI |
|---|---|---|
| Update item definitions (code) | ✓ commit → push → pull in Fabric | ✓ `deploy-item --on-exists update` |
| Create new items from scratch | ✗ | ✓ `deploy` |
| Run notebooks / copy jobs | ✗ | ✓ `run-job` |
| Create shortcuts | ✗ | ✓ (phase actions) |
| Verify data correctness | ✗ | ✓ `verify` |
| PR-based code review | ✓ (GitHub / ADO) | ✗ |
| Track change history | ✓ (Git log) | ✗ |
| Rollback definitions | ✓ (`git revert`) | ✓ (`deploy` from tag) |
| Rollback data | ✗ | ✓ (`run-job` with corrected code) |

**The pattern across all modules:**
1. **Edit** definitions locally or in Fabric
2. **Push** to Git (or commit from Fabric)
3. **Pull** into workspace via Git Integration (definitions updated)
4. **Run** jobs via SDK (data materialized)
5. **Verify** via SDK (correctness confirmed)

## CLI Quick Reference

```bash
# Full bootstrap (new workspace)
python3 bootstrap.py deploy --workspace-name my-ws --existing-workspace

# Diff — see what would change
python3 bootstrap.py deploy --workspace-name my-ws --existing-workspace --diff

# Update a single item in-place
python3 bootstrap.py deploy-item --workspace-name my-ws --existing-workspace \
    --on-exists update --item nb_transformations

# Run a job
python3 bootstrap.py run-job --workspace-name my-ws --existing-workspace \
    --item nb_transformations

# Check state
python3 bootstrap.py status --workspace-name my-ws --existing-workspace

# Verify data
python3 bootstrap.py verify --workspace-name my-ws --existing-workspace

# JSON output (for CI pipelines)
python3 bootstrap.py status --workspace-name my-ws --existing-workspace --output json
```

## Comparison with Workshop v1

| Aspect | Workshop v1 | Workshop v2 |
|--------|-------------|-------------|
| Structure | 8 sequential modules | 9 scenario-driven modules |
| Motivation | "Learn this feature" | "Solve this problem" |
| Personas | Implicit (one size fits all) | Explicit per module |
| Tooling | fabric-cli + portal-heavy | SDK + Git + portal |
| Verification | Manual (open in browser) | Automated (`verify` command) |
| State visibility | None | `--diff` and `--output json` |
| Idempotency | Not addressed | Core thread from Module 1 |
| Rollback | Not covered | Dedicated module |
| Onboarding | Not covered | Dedicated module |

---

## The SDK — A Reference Implementation

The Python SDK under `deployment/sdk/` is a **reference implementation** — it demonstrates patterns for Fabric CI/CD that go beyond what any single existing tool covers. It is NOT a production dependency or replacement for `fabric-cicd`.

**Use it as:**
- A working example of desired-state deployment, job orchestration, and data verification
- A pattern library: steal the retry logic, the DFS verification approach, the phased deployment strategy
- A teaching tool for the workshop exercises

**It builds on top of:**
- [`fabric-cicd`](https://microsoft.github.io/fabric-cicd/) — the official open-source library for definition imports and parameterization (our SDK uses it internally via `_import_via_fabric_cicd()`)
- Fabric REST APIs — for workspace and item management, job execution
- OneLake DFS — for data verification

**What's novel in this SDK (not available elsewhere):**
| Capability | In `fabric-cicd`? | In this SDK? |
|---|---|---|
| Item definition deployment | ✓ | ✓ (delegates to fabric-cicd) |
| Parameterization (`parameter.yml`) | ✓ | ✓ (via fabric-cicd) |
| Desired-state assessment (`--diff`) | ✗ | ✓ |
| Job execution & wait | ✗ | ✓ |
| Shortcut creation | ✗ | ✓ |
| Post-deploy data verification | ✗ | ✓ |
| Workspace bootstrap from scratch | ✗ | ✓ |
| Phased deployment with dependencies | ✗ | ✓ |

---

## Relationship to Existing Materials

This workshop builds on — and deliberately does not duplicate — these existing resources:

| Resource | What It Covers | How This Workshop Uses It |
|----------|---------------|--------------------------|
| [fabric-cicd library docs](https://microsoft.github.io/fabric-cicd/) | Library API, `parameter.yml` syntax, tutorials | Module 6 links here for parameterization deep dive |
| [MS Learn Git Integration](https://learn.microsoft.com/en-us/fabric/cicd/git-integration/intro-to-git-integration) | Connect workspace to Git, sync mechanics | Module 2 references this for setup steps |
| [MS Learn CI/CD Tutorial](https://learn.microsoft.com/en-us/fabric/cicd/cicd-tutorial) | Portal-based deployment pipelines | Module 6 links as portal-based alternative |
| [fabric-cicd Whitepaper](https://github.com/FabricDevCamp/fabric-cicd-whitepaper) | Architecture, design decisions | Linked for conceptual depth |
| [Fabric Terraform Demo](https://github.com/FabricDevCamp/fabric-terraform-demo) | Infrastructure-as-code with Terraform | Different approach (infra provisioning vs CI/CD) |

**What this workshop adds that doesn't exist elsewhere:**
1. **Persona-activity paradigm** — each module opens with "As a [role], I want to..." making it navigable by job function
2. **Data-plane CI/CD** — verifying data correctness after deployment, not just definition deployment
3. **Desired-state engine** — `--diff` preview showing exactly what will change before deploying
4. **End-to-end scenario** — from empty workspace to production promotion to disaster recovery, all connected
