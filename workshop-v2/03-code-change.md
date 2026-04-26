# Module 3: Make a Code Change & Deploy It

> **User Story:** *As a Data Engineer, I want to fix a bug in my transformation notebook and deploy the fix to production, so that the next data run produces correct results without rebuilding the entire lakehouse.*

**Duration:** 30 minutes | **Persona:** Data Engineer | **Depends on:** Module 2

## Context

The Transformations notebook currently uses `CREATE TABLE` which fails if the table already exists. You need to make it idempotent so it can be re-run safely. This is a common real-world fix.

## Exercise 1: Identify the Problem (5 min)

Try re-running the notebook:

```bash
cd deployment/sdk
python3 bootstrap.py run-job \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace \
    --item nb_transformations
```

**Expected:** Job fails because `dbo.t1` already exists and `CREATE TABLE` doesn't handle that.

## Exercise 2: Fix the Notebook Locally (5 min)

Open `DE_Workshop/Transformations.Notebook/notebook-content.py` and find:

```sql
create table dbo.t1 using DELTA as (
    select * from t2 full outer join t3 limit 10000
)
```

Change it to:

```sql
CREATE OR REPLACE TABLE dbo.t1 USING DELTA AS (
    SELECT * FROM t2 FULL OUTER JOIN t3 LIMIT 10000
)
```

> **Why:** `CREATE OR REPLACE` is idempotent — safe to run multiple times. This is critical for any notebook that runs in CI/CD.

## Exercise 3: Deploy the Fix (10 min)

This exercise shows **both paths** — Git Integration for the definition change, SDK for execution. In practice, you'd pick one based on your workflow.

### Path A: Git Integration (recommended for definition changes)

This is the natural developer flow — edit, commit, pull into Fabric.

```bash
# Commit the fix
git add DE_Workshop/Transformations.Notebook/
git commit -m "fix: make t1 creation idempotent (CREATE OR REPLACE)"
git push
```

Then in Fabric:
1. Open your workspace
2. **Source Control** → you'll see "1 incoming change"
3. Click **Update all** — the notebook definition updates in Fabric

> **What happened:** Git Integration updated the notebook's *definition* (code). But the notebook didn't *run* — the data hasn't changed yet.

### Path B: SDK (for definition + execution in one go)

```bash
python3 bootstrap.py deploy-item \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace \
    --on-exists update \
    --item nb_transformations
```

> **When to use which:**
> | Situation | Use |
> |---|---|
> | Developer editing code interactively | Git Integration (edit → commit → pull) |
> | CI/CD pipeline deploying after PR merge | SDK or `fabric-cicd` |
> | Need to run the notebook after updating | SDK `run-job` (Git Integration can't do this) |
> | Need to verify data after running | SDK `verify` (Git Integration can't do this) |

## Exercise 4: Run & Verify (10 min)

```bash
# Re-run — should succeed now
python3 bootstrap.py run-job \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace \
    --item nb_transformations

# Verify data is still correct
python3 bootstrap.py verify \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace
```

**Expected:** Notebook completes, 6/6 verification checks pass. Table `t1` has the same data — just recreated cleanly.

## Checkpoint

- [ ] Notebook updated to use `CREATE OR REPLACE TABLE`
- [ ] Re-running the notebook succeeds (previously it failed)
- [ ] Verification passes — data is correct
- [ ] You understand: Git Integration = definitions, SDK = execution

## Key Takeaway

> Always write DDL that is **safe to re-run**. `CREATE OR REPLACE TABLE`, `CREATE TABLE IF NOT EXISTS`, and `MERGE` are your friends. A notebook that fails on re-run blocks every CI/CD pipeline.
