# Git Integration Reference — GitHub & Azure DevOps

Fabric supports Git integration with both **GitHub** and **Azure DevOps (ADO)**. The concepts are identical — only the setup steps differ. This page covers both so you can follow the tutorial with whichever provider you use.

---

## Choosing Your Provider

| | GitHub | Azure DevOps |
|---|---|---|
| **Repository hosting** | github.com or GitHub Enterprise | dev.azure.com |
| **Auth** | GitHub account (personal or org) | Microsoft Entra ID |
| **PR workflow** | Pull Requests | Pull Requests |
| **CI/CD** | GitHub Actions | Azure Pipelines |
| **Free tier** | Unlimited public repos, limited private | Free for ≤5 users |
| **Enterprise Managed Users** | Cannot fork external repos | Native Entra integration |

> **For this tutorial:** Either works. Pick the one your organization uses. All subsequent modules are provider-agnostic — they reference "commit", "push", "PR", and "pull" which work the same way on both.

---

## Prerequisites

### For GitHub
- A GitHub account (personal, not Enterprise Managed User if you need to fork external repos)
- A repository (fork of this workshop repo, or your own)

### For Azure DevOps
- An Azure DevOps organization and project
- A Git repository in that project
- Contributor access

---

## Setup: Fork / Create the Repository

### GitHub

1. Go to **https://github.com/DaniBunny/Fabric-DE-CICD**
2. Click **Fork** → keep defaults → **Create fork**
3. Clone locally:
```bash
git clone https://github.com/<your-username>/Fabric-DE-CICD.git
cd Fabric-DE-CICD
```

### Azure DevOps

1. Navigate to your ADO project → **Repos** → **Files**
2. If starting fresh, click **Initialize** with a README
3. If forking the workshop repo, use **Import repository**:
   - Source: `https://github.com/DaniBunny/Fabric-DE-CICD.git`
   - Click **Import**
4. Clone locally:
```bash
git clone https://dev.azure.com/<org>/<project>/_git/<repo>
cd <repo>
```

---

## Setup: Connect a Fabric Workspace to Git

1. Open your workspace in the Fabric portal
2. **Workspace settings** (gear icon) → **Git integration**
3. Select your provider:

### GitHub Configuration

| Setting | Value |
|---|---|
| **Git provider** | GitHub |
| **Repository owner** | `<your-github-username>` |
| **Repository** | `Fabric-DE-CICD` (or your repo name) |
| **Branch** | `main` (or your working branch) |
| **Git folder** | `/DE_Workshop` |

### Azure DevOps Configuration

| Setting | Value |
|---|---|
| **Git provider** | Azure DevOps |
| **Organization** | `<your-ado-org>` |
| **Project** | `<your-project>` |
| **Repository** | `<your-repo>` |
| **Branch** | `main` (or your working branch) |
| **Git folder** | `/DE_Workshop` |

4. Click **Connect and sync**
5. Choose:
   - **Export workspace to Git** — if the workspace already has items (e.g., after bootstrap)
   - **Import from Git** — if the Git repo already has items and the workspace is empty

---

## Daily Operations (Same on Both Providers)

### Fabric → Git (Save Your Work)

1. Make a change in the Fabric portal (edit a notebook, rename a shortcut, etc.)
2. Click **Source Control** in the workspace header
3. Review pending changes
4. Enter a commit message → **Commit**

The commit appears in your repo's history (GitHub or ADO).

### Git → Fabric (Pull Changes)

1. Edit files locally or in the web UI (GitHub.com or dev.azure.com)
2. Commit and push to the branch
3. In Fabric, **Source Control** → you'll see "Updates available"
4. Click **Update all**

Fabric applies the definition changes to the workspace items.

### Pull Requests (Code Review)

Both providers support PRs with the same flow:

1. Create a feature branch: `git checkout -b feat/add-t5`
2. Make changes, commit, push
3. Open a PR:
   - **GitHub:** github.com → Pull requests → New pull request
   - **ADO:** dev.azure.com → Repos → Pull requests → New pull request
4. Reviewer sees the diff (notebook code, TMDL, PBIR — all text-based)
5. Approve and merge

---

## Branch Strategy

Fabric workspaces connect to a single branch. Common patterns:

| Pattern | Branches | Workspaces |
|---------|----------|------------|
| **Dev + Prod** | `main`, `production` | `DEWorkshop_dev`, `DEWorkshop_prod` |
| **Dev + Test + Prod** | `main`, `test`, `production` | 3 workspaces, one per branch |
| **Branch-per-developer** | `main`, `dev/<name>` | Shared + personal workspaces |
| **Feature branches** | `main`, `feat/*` | Temporary workspaces per feature |

The "Branch out to new workspace" feature in Fabric creates both the branch and workspace in one step (works with both providers).

---

## What Fabric Syncs to Git

| Synced ✓ | Not Synced ✗ |
|---|---|
| Notebook code and cell structure | Table data (rows, parquet files) |
| Lakehouse structure, shortcut definitions | Files in OneLake |
| Copy Job configuration | Job run history, schedules |
| Semantic Model definition (TMDL) | Cached/imported data, refresh history |
| Report layout, visuals, DAX | User personalizations |
| Environment Spark config | Running cluster state |
| `.platform` metadata files | Workspace role assignments |
| | Capacity assignment |
| | Data gateway bindings |

> **Key implication:** After pulling changes from Git, you may need to run notebooks or copy jobs to materialize data. Git only updates *definitions*, not *data*. This is where the SDK's `run-job` and `verify` commands fill the gap.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Updates available" won't go away | Commit or discard local changes first |
| Can't connect to GitHub (EMU account) | Use a personal GitHub account, or use ADO |
| Push rejected (permission denied) | Check PAT scope includes `repo`, or use SSH keys |
| Sync stuck / items missing | Verify Git folder path matches in settings |
| Conflict on pull | Resolve in Git (locally or web), then re-sync |
| Can't see Source Control button | You need workspace admin role |

---

## Further Reading

- [Git integration in Microsoft Fabric](https://learn.microsoft.com/en-us/fabric/cicd/git-integration/intro-to-git-integration)
- [Best practices for CI/CD in Fabric](https://learn.microsoft.com/en-us/fabric/cicd/best-practices-cicd)
- [Connect a workspace to GitHub](https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-get-started?tabs=github)
- [Connect a workspace to Azure DevOps](https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-get-started?tabs=azure-devops)
- [Manage branches in Fabric](https://learn.microsoft.com/en-us/fabric/cicd/git-integration/manage-branches)
