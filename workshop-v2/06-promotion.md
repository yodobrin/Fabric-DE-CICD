# Module 6: Promote to Production

> **User Story:** *As a DevOps Engineer, I want to promote a validated set of changes from development through test to production via pull requests, so that every change is reviewed, tested, and auditable before reaching production.*

**Duration:** 30 minutes | **Persona:** DevOps Engineer | **Depends on:** Module 5

## Context

Your development workspace has the full solution including the new `t5` table. Now you need to create a production workspace with its own isolated data — pointing at the same code but with environment-specific GUIDs remapped.

## Exercise 1: Create a Production Branch (5 min)

### Option A: Via Fabric "Branch out to new workspace"
1. In your dev workspace, click **Source Control** → **Branch out to new workspace**
2. Name: `production`, workspace: `DEWorkshop_<yourname>_Prod`

### Option B: Via Git + SDK
```bash
git checkout -b production
git push origin production

# Create workspace in portal, then bootstrap it
python3 bootstrap.py deploy \
    --workspace-name DEWorkshop_<yourname>_Prod \
    --existing-workspace \
    --base-url <api-host>
```

## Exercise 2: Understand Parameter Remapping (10 min)

When you deploy the same code to a different workspace, the lakehouse IDs, connection strings, and semantic model IDs are different. This is what `parameter.yml` solves.

Examine `DE_Workshop/parameter.yml`:

```yaml
find_replace:
    - find_value: "<dev-bronze-lakehouse-id>"
      replace_value:
        _ALL_: "$items.Lakehouse.Lakehouse_Bronze.id"
      item_type: "Notebook"
```

**How it works:**
- `find_value` — the GUID from the source (dev) workspace
- `replace_value` — a variable that resolves to the target (prod) workspace's actual GUID
- `fabric-cicd` does this replacement at deploy time

> **Reference:** [fabric-cicd Parameter File](https://microsoft.github.io/fabric-cicd/latest/parameter_file/)

## Exercise 3: Deploy & Verify Production (10 min)

```bash
# Bootstrap prod workspace
python3 bootstrap.py deploy \
    --workspace-name DEWorkshop_<yourname>_Prod \
    --existing-workspace

# Verify prod has its own data
python3 bootstrap.py verify \
    --workspace-name DEWorkshop_<yourname>_Prod \
    --existing-workspace
```

**Key observation:** Production has its own lakehouses with their own data. The notebooks ran in the prod workspace context, creating prod-specific tables. Nothing is shared with dev.

## Exercise 4: Simulate a PR-Driven Promotion (5 min)

In a real CI/CD pipeline, promotion looks like:

```
1. Developer works on feature branch → dev workspace
2. PR from feature → main (code review, approval)
3. CI pipeline deploys to test workspace, runs verify
4. PR from main → production (approval gate)
5. CD pipeline deploys to prod workspace, runs verify
```

Open your GitHub repo and create a PR from `main` to `production`. Review the diff — this is exactly what a Team Lead would review before approving a production deployment.

## Checkpoint

- [ ] Production workspace exists with all items
- [ ] `verify` passes on production (its own data, not dev's)
- [ ] You understand: same code, different GUIDs, `parameter.yml` bridges them
- [ ] You can explain the PR-driven promotion flow

## Further Reading

- [fabric-cicd Parameterization Guide](https://microsoft.github.io/fabric-cicd/0.1.30/how_to/parameterization/) — deep dive into `parameter.yml` syntax and item-level overrides
- [fabric-cicd Parameter File Reference](https://microsoft.github.io/fabric-cicd/latest/parameter_file/) — complete schema reference
- [CI/CD Tutorial — MS Learn](https://learn.microsoft.com/en-us/fabric/cicd/cicd-tutorial) — portal-based alternative using Fabric Deployment Pipelines
- [Deployment Pipelines Overview](https://learn.microsoft.com/en-us/fabric/cicd/deployment-pipelines/intro-to-deployment-pipelines) — if your org prefers the no-code pipeline approach
- [fabric-cicd Whitepaper](https://github.com/FabricDevCamp/fabric-cicd-whitepaper) — architecture context by Yaron Pri Gal

## Key Takeaway

> Each environment (dev/test/prod) has its own workspace, its own data, its own lakehouse IDs. The **code** (notebooks, semantic model definitions) is the same across environments — versioned in Git. The **GUIDs** differ — `parameter.yml` and the SDK handle the remapping. This is why you never hardcode IDs in your notebooks.
