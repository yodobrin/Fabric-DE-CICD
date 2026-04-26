# Fabric CI/CD Scenarios by Persona

A practical reference for the most common CI/CD workflows in Microsoft Fabric, organized by who performs them and when. Designed to guide workshop enhancements and SDK capabilities.

---

## Personas

| Persona | Role | Primary Concern |
|---------|------|-----------------|
| **Data Engineer** | Builds pipelines, notebooks, lakehouses | "Will my data still be correct after deployment?" |
| **Analytics Engineer** | Semantic models, reports, measures | "Will my report break if someone changes the lakehouse?" |
| **Platform Engineer** | Workspace provisioning, capacity, access | "How do I stamp out environments consistently?" |
| **DevOps / Release Engineer** | Pipelines, approvals, automation | "How do I promote changes safely across environments?" |
| **Data Scientist** | Notebooks, experiments, ML models | "How do I get my notebook into production without breaking the pipeline?" |
| **Team Lead / Reviewer** | Code review, compliance, standards | "How do I know what's changing before it reaches production?" |

---

## Scenario Matrix

### 1. Fresh Workspace Provisioning

> **User Story:** *As a Platform Engineer, I want to provision a fully working Fabric workspace from a single command, so that new projects and team members can start working in minutes instead of hours of manual setup.*

> **Trigger:** New project, new team member, new environment (test/prod)  
> **Personas:** Platform Engineer, DevOps Engineer

| Step | Action | Tool |
|------|--------|------|
| Create workspace | Provision on capacity | REST API / Portal |
| Seed items | Create lakehouses, import notebooks, env, copy jobs | SDK `deploy` / `fabric-cicd` |
| Hydrate data | Run copy jobs, notebooks to populate tables | SDK `run-job` |
| Create shortcuts | Wire Silver → Bronze references | SDK (phase actions) |
| Semantic layer | Deploy semantic model + report | SDK `deploy --phase semantic_layer` |
| Validate | Confirm all data landed correctly | SDK `verify` |
| Connect to Git | Link workspace to branch | Portal / REST API |

**Key concern:** This is the only scenario that requires creating items from scratch. Every other scenario is incremental.

---

### 2. Schema Change — Additive (New Table / New Column)

> **User Story:** *As a Data Engineer, I want to add a new analytics table to the Silver lakehouse by editing a notebook and deploying the change, so that downstream consumers get new data without any disruption to existing tables.*

> **Trigger:** Business needs a new analytics table, new calculated column  
> **Personas:** Data Engineer, Analytics Engineer

| Step | Action | Tool |
|------|--------|------|
| Edit notebook | Add SQL cell (CREATE TABLE / ALTER TABLE ADD COLUMN) | VS Code / Fabric Portal |
| Edit semantic model | Add table/column definition to TMDL | VS Code |
| Commit | Push to feature branch | Git |
| Review | PR review — reviewer checks SQL is additive, no drops | GitHub / ADO |
| Deploy definition | Update notebook + model in workspace | Git Integration pull / SDK `deploy-item --on-exists update` |
| Run notebook | Execute to materialize the new table/column | SDK `run-job` / Fabric scheduler |
| Verify | Confirm new data exists, old data untouched | SDK `verify` |

**Key concern:** Existing tables and data must be preserved. The notebook must be idempotent (`CREATE TABLE IF NOT EXISTS` or `CREATE OR REPLACE TABLE`).

---

### 3. Schema Change — Destructive (Drop/Rename Column)

> **User Story:** *As a Data Engineer, I want to safely rename a deprecated column without breaking reports or notebooks that depend on it, so that I can evolve the schema while maintaining backward compatibility during a transition period.*

> **Trigger:** Column deprecated, table renamed, data type change  
> **Personas:** Data Engineer, Team Lead (approval)

| Step | Action | Tool |
|------|--------|------|
| Add new column/table | Create replacement alongside the old one | Notebook + Git |
| Update consumers | Migrate notebooks, semantic model, reports to use new name | VS Code |
| Deploy | Push all changes together | SDK `deploy --on-exists update` / Git Integration |
| Validate | Run full verification suite | SDK `verify` |
| Deprecation period | Keep old column alive, monitor usage | Manual / scheduled job |
| Drop old column | Only after all consumers migrated | Future notebook run |

**Key concern:** Never drop first. Always add the replacement, migrate consumers, then drop later. "Fix forward" pattern.

---

### 4. Notebook Code Change (Logic Fix / Optimization)

> **User Story:** *As a Data Engineer, I want to fix a bug in my transformation notebook and deploy the fix to production, so that the next data run produces correct results without rebuilding the entire lakehouse.*

> **Trigger:** Bug in transformation, performance tuning, adding logging  
> **Personas:** Data Engineer, Data Scientist

| Step | Action | Tool |
|------|--------|------|
| Edit notebook | Fix the code in Fabric or VS Code | Portal / VS Code |
| Test in dev | Run manually, check results | Fabric Portal |
| Commit | Fabric → Git (Source Control panel) or local push | Git |
| PR | Team reviews the change | GitHub / ADO |
| Deploy to test/prod | Update notebook definition | Git Integration / SDK `deploy-item` |
| Re-run | Execute notebook to apply the fix | SDK `run-job` / Fabric scheduler |

**Key concern:** Does the fix need a data re-run? If the notebook is idempotent (CTAS / CREATE OR REPLACE), re-running regenerates correct data. If append-only, more care needed.

---

### 5. Report / Semantic Model Update

> **User Story:** *As an Analytics Engineer, I want to add a new measure to the semantic model and update the report, so that business users see the new KPI without any downtime or data refresh issues.*

> **Trigger:** New visual, new measure, changed data source  
> **Personas:** Analytics Engineer

| Step | Action | Tool |
|------|--------|------|
| Edit in Fabric | Modify report layout, add DAX measure | Power BI / Fabric Portal |
| Commit | Fabric → Git sync | Source Control panel |
| PR | Review PBIR/TMDL diff | GitHub / ADO |
| Deploy to prod | Update definition in target workspace | Git Integration / SDK / `fabric-cicd` |
| Validate | Open report, confirm visuals load | Manual / SDK `verify` (semantic model data check) |

**Key concern:** Report binds to semantic model by ID. Cross-environment deployment must remap this ID — `fabric-cicd`'s `parameter.yml` or SDK placeholders handle this.

---

### 6. Cross-Environment Promotion (Dev → Test → Prod)

> **User Story:** *As a DevOps Engineer, I want to promote a validated set of changes from development through test to production via pull requests, so that every change is reviewed, tested, and auditable before reaching production.*

> **Trigger:** Feature complete, sprint boundary, release  
> **Personas:** DevOps Engineer, Team Lead (approval gate)

| Step | Action | Tool |
|------|--------|------|
| PR to test branch | Merge dev → test | GitHub / ADO |
| CI pipeline triggers | Deploy items to test workspace | ADO Pipeline / GitHub Actions + `fabric-cicd` |
| Run jobs in test | Populate data in test environment | Pipeline step / SDK `run-job` |
| Verify test | Automated data checks | SDK `verify` / pipeline step |
| Gate approval | Manual approval for prod promotion | ADO / GitHub Environments |
| PR to prod branch | Merge test → prod | GitHub / ADO |
| Deploy to prod | Same pipeline, different workspace | `fabric-cicd` with `parameter.yml` remapping |
| Verify prod | Final data validation | SDK `verify` |

**Key concern:** Each environment has different lakehouse IDs, connection strings, and capacity. `parameter.yml` handles the find-replace across environments.

---

### 7. Rollback / Recovery

> **User Story:** *As a DevOps Engineer, I want to quickly revert a bad deployment to a known-good state, so that production consumers are unaffected while I diagnose and fix the issue.*

> **Trigger:** Deployment broke production, data corruption  
> **Personas:** DevOps Engineer, Data Engineer

| Strategy | When to Use | How |
|----------|-------------|-----|
| **Git revert** | Definition change broke something | `git revert <commit>` → deploy | 
| **Re-run from source** | Data pipeline produced bad results | Fix code → SDK `run-job` (idempotent CTAS regenerates) |
| **Restore from backup** | Data deleted/corrupted beyond re-run | OneLake BCDR / time-travel (Delta) |
| **Re-deploy previous version** | Multiple changes, need to go back | `fabric-cicd` from a known-good Git tag |

**Key concern:** Idempotent notebooks (CREATE OR REPLACE) make data rollback trivial — just re-run with the corrected code. Non-idempotent (INSERT/APPEND) requires more careful handling.

---

### 8. New Team Member Onboarding

> **User Story:** *As a new Data Engineer joining the team, I want to get a personal development workspace with all data pre-populated in one step, so that I can start contributing code on my first day.*

> **Trigger:** New developer joins the project  
> **Personas:** Platform Engineer, new Data Engineer

| Step | Action | Tool |
|------|--------|------|
| Provision personal workspace | Create `DEWorkshop_<username>` | SDK `deploy` / Portal |
| Connect to feature branch | Git integration to personal branch | Portal |
| Seed data | Run bootstrap to populate lakehouses | SDK `deploy` (full run) |
| Verify | Confirm everything works | SDK `verify` |

**Key concern:** The developer should get a fully working environment in minutes, not hours. This is where the SDK's full bootstrap shines — one command to go from empty workspace to all-green.

---

### 9. Scheduled Data Refresh

> **User Story:** *As a Data Engineer, I want to configure daily ingestion jobs that run automatically and alert me on failure, so that the lakehouse always has fresh data without manual intervention.*

> **Trigger:** Daily/hourly data ingestion  
> **Personas:** Data Engineer (setup), Fabric Scheduler (execution)

| Step | Action | Tool |
|------|--------|------|
| Configure schedule | Set Copy Job and Notebook schedules | Fabric Portal / REST API |
| Monitor runs | Check job status | Fabric Monitor / SDK `status` |
| Alert on failure | Notify on job failure | Fabric alerts / pipeline webhook |
| Re-run on failure | Retry failed jobs | SDK `run-job` / Fabric auto-retry |

**Key concern:** Schedules are workspace-level and NOT versioned in Git. They must be configured per environment separately.

---

### 10. Capacity Migration / Workspace Move

> **User Story:** *As a Platform Engineer, I want to migrate a workspace to a different capacity or region by redeploying from Git, so that the move is repeatable and verified rather than a risky manual copy.*

> **Trigger:** Cost optimization, region move, capacity resize  
> **Personas:** Platform Engineer

| Step | Action | Tool |
|------|--------|------|
| Create target workspace | On new capacity | SDK `deploy` / Portal |
| Deploy all items | From Git (source of truth) | SDK `deploy` / `fabric-cicd` |
| Hydrate data | Run copy jobs + notebooks | SDK `run-job` |
| Verify | Full validation suite | SDK `verify` |
| Switch DNS / update consumers | Point downstream to new workspace | Manual |
| Decommission old workspace | After validation period | Portal / REST API |

**Key concern:** Data doesn't move with items. You need to re-run the full data pipeline in the new workspace.

---

## What's Versioned vs What's Not

Critical for understanding which scenarios need data-plane actions beyond Git:

| Versioned in Git | NOT Versioned (needs SDK/CLI) |
|---|---|
| Notebook code, cell structure | Notebook execution results, Spark session state |
| Lakehouse structure, shortcut definitions | Actual data in tables, files in OneLake |
| Copy Job configuration | Copy Job run history, last run status |
| Semantic Model definition (TMDL) | Imported/cached data, refresh history |
| Report layout, visuals, DAX | User personalizations, cached renders |
| Environment Spark config | Running cluster state |
| — | Job schedules (per-workspace) |
| — | Data gateway bindings |
| — | Capacity assignment |
| — | Workspace role assignments |

---

## When to Use What: Git Integration vs CLI vs SDK vs REST

There are four layers of tooling. Each has a clear purpose — using the wrong one for a task creates friction; using the right one makes it invisible.

### The Four Layers

| Layer | Tool | What It Does | Best For |
|---|---|---|---|
| **Definition** | Git Integration | Sync code, TMDL, PBIR between Fabric ↔ Git. PR review, branching. Built into Fabric portal — zero install. | Developers editing code, code review, version history |
| **Deployment** | fabric-cicd | Bulk import with parameterization, environment-aware (dev/test/prod), dependency ordering, orphan cleanup. | CI/CD pipelines, cross-environment promotion |
| **Execution** | fabric-cli (fab) | Interactive REPL, filesystem-like workspace navigation, quick create/run/status operations. | Developer inner loop, debugging, scripting |
| **Execution** | REST API + OneLake DFS | Run jobs, poll status, create shortcuts, verify data via DFS. Maximum control, all operations. | Custom automation, data-plane operations not covered by CLI/cicd |

### Decision Matrix Per Scenario

| Scenario | Git Integration | fabric-cli | fabric-cicd | REST API |
|----------|:-:|:-:|:-:|:-:|
| **1. Fresh provisioning** | — | create items | bulk import | lakehouses, shortcuts, jobs |
| **2. Additive schema change** | push notebook code | — | update definition | run notebook, verify data |
| **3. Destructive schema change** | push code + review PR | — | update definition | run notebook, verify data |
| **4. Notebook code fix** | push/pull definition | test run | update in CI/CD | run + verify |
| **5. Report/model update** | push TMDL/PBIR | — | update definition | — |
| **6. Cross-env promotion** | PR merge across branches | — | deploy + remap | verify data |
| **7. Rollback** | `git revert` + pull | — | redeploy from tag | re-run jobs, verify |
| **8. Onboarding** | connect workspace to branch | — | bulk import | bootstrap (all phases) |
| **9. Scheduled refresh** | — | — | — | configure schedules |
| **10. Capacity migration** | connect new workspace | — | bulk import | full bootstrap |

### The Pattern

Most scenarios follow the same flow, using each tool for what it does best:

| Step | Action | Layer |
|------|--------|-------|
| 1. Edit | IDE / Fabric portal (human) | — |
| 2. Version | Git Integration (commit, push, PR) | Definition |
| 3. Deploy definitions | Git Integration (pull) or fabric-cicd (CI/CD) | Definition / Deployment |
| 4. Execute | REST API (run jobs, create shortcuts) | Execution |
| 5. Verify | REST API + OneLake DFS (check data) | Execution |

Steps 1-3 are **definition plane** — what the code says.
Steps 4-5 are **data plane** — what the data looks like.

Git Integration owns the definition plane. REST API (wrapped by the SDK) owns the data plane. fabric-cicd bridges them for bulk operations. fabric-cli is for humans exploring interactively.

### What's Missing Today

The gap is between steps 3 and 4. After Git Integration pulls a notebook update, **nothing runs it**. After fabric-cicd deploys a copy job, **nothing starts it**. After a job runs, **nothing checks if data landed**. This is why we built the SDK — to close the definition-to-data gap with `run-job`, `verify`, and phased orchestration.

---

## Workshop Coverage Gap Analysis

| Scenario | Current Workshop | Gap |
|----------|-----------------|-----|
| 1. Fresh provisioning | Module 2 (shell script) | SDK bootstrap now covers this fully |
| 2. Additive schema change | Module 8 (manual) | SDK `deploy-item` + `run-job` + `verify` |
| 3. Destructive schema change | Module 8 (conceptual) | Needs hands-on exercise with fix-forward pattern |
| 4. Notebook code change | Module 3 (Git push/pull) | Missing: automated re-run + verification |
| 5. Report/model update | Not covered | Needs exercise: edit model → deploy → validate |
| 6. Cross-env promotion | Modules 5-7 | Well covered, could add SDK `verify` as gate |
| 7. Rollback | Not covered | Needs exercise: break prod → recover |
| 8. Onboarding | Not covered | SDK bootstrap is the answer |
| 9. Scheduled refresh | Not covered | Config-only, reference doc sufficient |
| 10. Capacity migration | Not covered | Advanced, reference doc sufficient |
