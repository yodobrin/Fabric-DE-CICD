# Module 8: Onboard a New Team Member

> **User Story:** *As a new Data Engineer joining the team, I want to get a personal development workspace with all data pre-populated in one step, so that I can start contributing code on my first day.*

**Duration:** 15 minutes | **Persona:** Platform Engineer + new engineer | **Depends on:** Module 1

## Context

A new team member joins. They need their own isolated development workspace — fully populated with data, shortcuts, semantic model, report — ready to code against. This should take minutes, not a day of manual setup.

## Exercise 1: Create & Bootstrap (10 min)

The new engineer creates an empty workspace in the portal, then runs:

```bash
cd deployment/sdk

python3 bootstrap.py deploy \
    --workspace-name DEWorkshop_NewEngineer \
    --existing-workspace
```

**That's it.** The SDK:
1. Creates lakehouses (Bronze + Silver, schema-enabled)
2. Imports environment, notebooks, copy jobs from templates
3. Replaces placeholder GUIDs with the new workspace's real IDs
4. Runs copy jobs (data ingestion from Azure Open Datasets)
5. Creates shortcuts (Silver → Bronze)
6. Runs Bronze + Transformations notebooks (data processing)
7. Deploys semantic model + report

## Exercise 2: Verify & Connect to Git (5 min)

```bash
python3 bootstrap.py verify \
    --workspace-name DEWorkshop_NewEngineer \
    --existing-workspace
```

Then connect the workspace to a personal feature branch:

1. In Fabric: **Workspace settings** → **Git integration**
2. Connect to your fork, create branch `dev/<engineer-name>`
3. The workspace is now tracked, isolated, and ready for development

## Discussion: Isolation Patterns

| Pattern | Use Case | Tradeoff |
|---------|----------|----------|
| **Branch-per-developer** | Each dev has own workspace + branch | Full isolation, more capacity cost |
| **Shared dev workspace** | Team shares one workspace on `main` | Cheaper, but changes affect everyone |
| **Feature workspace** | Temporary workspace for a feature | Created on demand, destroyed after merge |

> **Recommendation:** For data engineering, branch-per-developer is safest because notebook runs affect shared data. A broken notebook in a shared workspace breaks everyone.

## Checkpoint

- [ ] New workspace bootstrapped with one command
- [ ] `verify` passes — all data present
- [ ] Workspace connected to a personal Git branch
- [ ] Time from empty workspace to all-green: < 15 minutes

## Key Takeaway

> Onboarding should be **one command**. If it takes a wiki page of manual steps, you'll lose the engineer's first day to setup. The SDK bootstrap is the answer — provision, hydrate, verify, done.
