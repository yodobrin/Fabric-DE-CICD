# Module 2: Connect to Git & Understand What's Versioned

> **User Story:** *As a team member, I want my workspace connected to Git so that every change is tracked, reviewable, and recoverable.*

**Duration:** 20 minutes | **Persona:** All | **Depends on:** Module 1

## Context

Your workspace is running and verified. Now connect it to Git so the item definitions are version-controlled. This is the foundation for every subsequent module — code review, promotion, rollback all depend on Git.

## Exercise 1: Connect Workspace to Git (5 min)

Follow the connection steps for your Git provider in the [Git Integration Reference](git-integration-reference.md#setup-connect-a-fabric-workspace-to-git).

Summary:
1. In Fabric portal, open your workspace
2. **Workspace settings** → **Git integration**
3. Select GitHub or Azure DevOps, configure repo/branch/folder
4. Click **Connect and sync** → choose **Export workspace to Git**

## Exercise 2: Explore What Fabric Exported (5 min)

Pull the changes locally:

```bash
git pull origin main   # or your branch
ls DE_Workshop/
```

Examine the structure:

| File | What It Is |
|---|---|
| `*.Notebook/notebook-content.py` | Notebook code in Fabric's `.py` format |
| `*.Lakehouse/.platform` | Item metadata (ID, type) |
| `*.Lakehouse/shortcuts.metadata.json` | Shortcut definitions |
| `*.SemanticModel/definition/*.tmdl` | Tabular Model Definition Language |
| `*.Report/definition.pbir` | Report binding to semantic model |
| `*.Report/report.json` | Report layout, visuals, DAX |

## Exercise 3: What's NOT in Git (5 min)

Open `Lakehouse_Bronze` in the portal. Expand **Tables** → you see `t2`, `t3_dev`, `t3_prod`.

Now look in `DE_Workshop/Lakehouse_Bronze.Lakehouse/` in Git — no table data, no parquet files.

**What's versioned vs what's not:**

| In Git ✓ | Not in Git ✗ |
|---|---|
| Notebook code & cell structure | Table data (rows, parquet files) |
| Lakehouse structure, shortcuts | Files in OneLake |
| Copy Job configuration | Job run history |
| Semantic Model definition (TMDL) | Cached/imported data |
| Report layout, visuals | User personalizations |
| Environment Spark config | Running cluster state |
| — | Job schedules |
| — | Workspace role assignments |
| — | Capacity assignment |

> **This is why the SDK exists.** Git handles definitions. The SDK handles everything else: running jobs, creating data, verifying results.

## Exercise 4: Round-Trip Sync (5 min)

### Fabric → Git
1. Open the `Validations` notebook in Fabric
2. Add a comment to the first cell: `-- Exercise 2 round-trip test`
3. Save → **Source Control** → commit with message: `test: round-trip exercise`
4. Pull locally: `git pull` → see the change in `DE_Workshop/Validations.Notebook/`

### Git → Fabric
1. Edit the same file locally — remove the comment you just added
2. Commit and push
3. In Fabric, **Source Control** → see "Updates available" → **Update all**
4. Open the notebook — comment is gone

## Checkpoint

- [ ] Workspace connected to Git, showing "Synced"
- [ ] `DE_Workshop/` folder exists in your repo with all items
- [ ] You made a Fabric → Git change and saw it in the repo
- [ ] You made a Git → Fabric change and saw it in the portal
- [ ] You can explain what data is NOT in Git

## Key Takeaway

> Git integration tracks **definitions** (code, structure, metadata). It does NOT track **data** (table contents, job results). For the full picture, you need both Git (for definitions) and the SDK (for data-plane operations like `run-job` and `verify`).
