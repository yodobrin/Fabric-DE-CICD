# Module 7: Break Something & Recover

> **User Story:** *As a DevOps Engineer, I want to quickly revert a bad deployment to a known-good state, so that production consumers are unaffected while I diagnose and fix the issue.*

**Duration:** 25 minutes | **Persona:** DevOps + Data Engineer | **Depends on:** Module 6

## Context

Deployments fail. Notebooks have bugs. Someone merges a bad PR. You need to know how to recover — fast. This module deliberately breaks the workspace and teaches three recovery strategies.

## Exercise 1: Break It (5 min)

Edit `DE_Workshop/Transformations.Notebook/notebook-content.py`. Change the t1 creation to produce zero rows:

```sql
CREATE OR REPLACE TABLE dbo.t1 USING DELTA AS (
    SELECT * FROM t2 FULL OUTER JOIN t3 WHERE 1=0
)
```

Deploy and run:

```bash
python3 bootstrap.py deploy-item \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace \
    --on-exists update \
    --item nb_transformations

python3 bootstrap.py run-job \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace \
    --item nb_transformations
```

## Exercise 2: Detect the Break (3 min)

```bash
python3 bootstrap.py verify \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace
```

**Expected:** `silver_t1_has_data` **FAILS** — t1 has 0 rows. Other checks may also fail if they depend on t1.

> **This is why automated verification matters.** In a CI/CD pipeline, this verify step would block the deployment from reaching production.

## Exercise 3: Recovery Strategy A — Git Revert (7 min)

The cleanest approach: revert the bad commit in Git, pull into Fabric via Git Integration, then re-run via SDK.

```bash
# Find the bad commit
git log --oneline -5

# Revert it
git revert HEAD --no-edit
git push
```

In Fabric: **Source Control** → **Update all** — the notebook reverts to the good version.

Now re-run and verify (SDK — because Git Integration can't execute code):

```bash
# Re-run to regenerate correct data
python3 bootstrap.py run-job \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace \
    --item nb_transformations

# Verify
python3 bootstrap.py verify \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace
```

**Why this works:** Git Integration reverted the *definition*. SDK re-ran the notebook to regenerate *data*. Because the notebook uses `CREATE OR REPLACE TABLE`, re-running with correct code produces correct data.

## Exercise 4: Recovery Strategy B — Fix Forward (5 min)

Instead of reverting, fix the code and push a new commit:

1. Edit the notebook — fix the `WHERE 1=0` back to the correct query
2. Commit: `fix: restore t1 join condition`
3. Deploy + run + verify

> **Discussion:** When to revert vs fix forward?
> - **Revert** when the bad commit is isolated and you need instant recovery
> - **Fix forward** when the fix requires additional changes beyond undoing the last commit

## Exercise 5: Recovery Strategy C — Delta Time-Travel (5 min)

If the table existed before with good data, Delta Lake keeps history:

```sql
-- In Fabric notebook, check table history
DESCRIBE HISTORY dbo.t1

-- Restore to a previous version
RESTORE TABLE dbo.t1 TO VERSION AS OF <version_number>
```

> **Note:** This requires running a notebook cell manually in Fabric. The SDK doesn't yet automate Delta time-travel, but `run-job` on a restore notebook would work.

## Checkpoint

- [ ] You intentionally broke the workspace (t1 has 0 rows)
- [ ] `verify` detected the break
- [ ] You recovered using at least one strategy
- [ ] `verify` passes again after recovery
- [ ] You can explain when to use revert vs fix-forward vs time-travel

## Key Takeaway

> Recovery is trivial when two things are true: **(1)** your DDL is idempotent (CREATE OR REPLACE) so re-running regenerates correct data, and **(2)** you have automated verification so you detect breaks before users do. The `--diff` + `verify` workflow is your safety net.
