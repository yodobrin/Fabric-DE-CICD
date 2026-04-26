# Module 4: Add a Table — Additive Schema Change

> **User Story:** *As a Data Engineer, I want to add a new analytics table to the Silver lakehouse by editing a notebook and deploying the change, so that downstream consumers get new data without any disruption to existing tables.*

**Duration:** 30 minutes | **Persona:** Data Engineer | **Depends on:** Module 3

## Context

Business wants a new analytics table `t5` that joins diabetes data with holiday data by country. This is an **additive change** — you're adding something new without touching existing tables.

## Exercise 1: Preview Current State (3 min)

```bash
cd deployment/sdk
python3 bootstrap.py status \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace
```

Note: all items exist, all data checks pass. This is the baseline.

## Exercise 2: Edit the Notebook (5 min)

Open `DE_Workshop/Transformations.Notebook/notebook-content.py` and add a new cell at the end:

```sql
%%sql

-- Additive schema change: create analytics table t5
CREATE TABLE IF NOT EXISTS dbo.t5 USING DELTA AS (
    SELECT 
        t1.AGE,
        t1.SEX,
        t1.BMI,
        t1.countryOrRegion,
        t3.holidayName,
        CURRENT_TIMESTAMP() as created_timestamp
    FROM dbo.t1 t1
    INNER JOIN dbo.t3 t3 ON t1.countryOrRegion = t3.countryOrRegion
)
```

And a validation cell:

```sql
%%sql

SELECT COUNT(*) as t5_row_count FROM dbo.t5
```

## Exercise 3: Add Config for t5 (5 min)

Open `deployment/sdk/workspace_config.yml` and add:

Under `data_expectations:`:
```yaml
  data_silver_t5:
    lakehouse: lakehouse_silver
    table: t5
    produced_by: [nb_transformations]
```

Under `verifications:`:
```yaml
  silver_t5_has_data:
    description: "Transformations notebook produced Silver t5 (analytics)"
    lakehouse: lakehouse_silver
    query: "SELECT COUNT(*) AS cnt FROM dbo.t5"
    expect:
      min_rows: 1
      column_check: { column: cnt, min_value: 1 }
```

## Exercise 4: Diff Before Applying (5 min)

```bash
python3 bootstrap.py deploy \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace \
    --on-exists update \
    --diff
```

**Expected output:**
```
  Item          Transformations.Notebook    ✓ exists   ~ update
  Data          lakehouse_silver:t5         · missing  ▶ run
```

Everything else: `─ skip`. Only the notebook definition changes, and t5 needs to be created by running the notebook.

## Exercise 5: Deploy, Run, Verify (12 min)

The full inner loop combining Git Integration and SDK:

### Step 1: Push definition via Git
```bash
# Commit notebook change + config change
git add DE_Workshop/Transformations.Notebook/ deployment/sdk/workspace_config.yml
git commit -m "feat: add analytics table t5 to Silver lakehouse"
git push
```

In Fabric: **Source Control** → **Update all** — notebook definition now has the t5 cell.

### Step 2: Run notebook via SDK (Git Integration can't do this)
```bash
python3 bootstrap.py run-job \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace \
    --item nb_transformations
```

### Step 3: Verify data via SDK (Git Integration can't do this)
```bash
python3 bootstrap.py verify \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace
```

**Expected:** All checks pass, including the new `silver_t5_has_data` check.

> **The pattern:** Git Integration handles *what the code says*. SDK handles *what the data looks like*. Together they cover the full lifecycle.

## Exercise 6: Confirm Nothing Else Changed (2 min)

```bash
python3 bootstrap.py verify \
    --workspace-name DEWorkshop_<yourname> \
    --existing-workspace \
    --check bronze_t2_has_data,silver_t1_has_data
```

Existing data is untouched. **This is the power of additive changes.**

## Checkpoint

- [ ] `t5` exists in Silver lakehouse with data
- [ ] All previous verification checks still pass
- [ ] You can explain why this is safe (additive, no drops)
- [ ] Diff showed exactly what would change before you applied it

## Key Takeaway

> Additive schema changes are safe: add new tables/columns alongside existing ones. Use `--diff` to preview, `deploy-item` to push the definition, `run-job` to materialize data, `verify` to confirm. Existing data is never touched.
