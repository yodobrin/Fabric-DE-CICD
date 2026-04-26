# Fabric Tooling — Improvement Plan

Where each tool should evolve to close the gaps identified in [scenarios.md](scenarios.md). Organized by the tool that should own each improvement, with rationale.

---

## The Core Gap: Definition Plane → Data Plane

Today's tools have a clean split:
- **Git Integration** handles definitions (code, TMDL, PBIR)
- **fabric-cicd** handles bulk deployment with parameterization
- **fabric-cli** handles interactive exploration
- **REST API** handles everything, but is low-level

The gap is in the **transition between definition changes and data changes**. After you update a notebook, nothing runs it. After a job runs, nothing checks if data landed. This gap is currently filled by custom scripting (our SDK, shell scripts, AzDO pipeline steps). The improvement plan aims to close this gap natively.

---

## fabric-cli Improvements

The CLI is the right home for **developer-facing operations** — things a human does from a terminal during development.

### Priority 1: Post-Deploy Actions

| Improvement | Rationale |
|---|---|
| `fab run <item>` — run any job-capable item | Today you can run some items but not all. Notebooks, Copy Jobs, Spark Jobs should all support `fab run` with consistent status polling |
| `fab run <item> --wait` — block until completion | Currently requires manual polling. `--wait` with timeout + exit code enables scripting |
| `fab run <item> --wait --verify` — run + verify | Chain: run the job, then check data expectations. Single command for the inner loop |

### Priority 2: State Visibility

| Improvement | Rationale |
|---|---|
| `fab status <workspace>` — desired-vs-current state | Show what exists, what's missing, what would change. Like our SDK's `--diff` |
| `fab verify <workspace>` — data expectations | Check that expected tables exist with data. Config-driven (YAML or inline) |
| `fab status --output json` — structured output | For CI/CD pipelines that need machine-readable state |

### Priority 3: Workspace Operations

| Improvement | Rationale |
|---|---|
| `fab bootstrap <workspace> --from <template-dir>` — full provisioning | One command: create items, replace placeholders, run jobs, create shortcuts, verify |
| `fab clone <source-ws> --to <target-ws>` — workspace cloning with remapping | Today's "branch out" doesn't remap connections. This would clone + remap in one step |
| `fab diff <workspace> <template-dir>` — show what would change | Preview before applying, like `terraform plan` |

### Priority 4: Data Operations

| Improvement | Rationale |
|---|---|
| `fab tables <lakehouse>` — list tables with row counts | Today the `/tables` API doesn't work on schema-enabled lakehouses. CLI should abstract this |
| `fab shortcuts <lakehouse>` — list/create/delete shortcuts | Currently requires REST API calls. Should be first-class CLI commands |
| `fab query <sql-endpoint> "SELECT ..."` — run ad-hoc SQL | For verification and debugging without opening the portal |

---

## fabric-cicd Improvements

fabric-cicd is the right home for **pipeline-facing operations** — things that run in CI/CD automation.

### Priority 1: Post-Publish Hooks

| Improvement | Rationale |
|---|---|
| `on_publish` hooks — run jobs after items are deployed | Today, `publish_all_items()` deploys definitions but doesn't run anything. A hook system would allow: deploy notebook → run notebook → verify |
| Job execution support — `run_item_job(workspace, item, job_type)` | fabric-cicd should be able to trigger and wait for jobs, not just deploy definitions |

### Priority 2: Verification

| Improvement | Rationale |
|---|---|
| `verify(workspace, expectations)` — data validation step | Config-driven (from parameter.yml or separate file). Check table existence, row counts, column presence |
| Exit codes for CI/CD — non-zero on verification failure | Pipeline gate: deploy → verify → fail pipeline if data is wrong |

### Priority 3: Incremental Operations

| Improvement | Rationale |
|---|---|
| `publish_items(workspace, items=[...])` — selective publish | Today `publish_all_items` publishes everything in scope. Should support deploying a specific list |
| Diff output — show what will be created/updated/skipped | Like `--diff` in our SDK. Pipeline logs should show the plan before executing |

### Priority 4: Multi-Workspace

| Improvement | Rationale |
|---|---|
| Batch deploy across workspaces — `publish_to_workspaces(workspaces, template)` | ISV scenario: deploy the same template to N customer workspaces |
| Workspace provisioning — create workspace + assign capacity | Today requires separate REST calls. Should be a first-class operation |

---

## REST API Improvements

These are platform-level gaps that affect all tools built on top.

### Priority 1: Schema-Enabled Lakehouse Support

| Improvement | Rationale |
|---|---|
| `/tables` endpoint for schema-enabled lakehouses | Currently returns 400. Forces fallback to DFS recursive listing with `_delta_log` pattern matching. This is the most impactful single API fix |
| `/tables` with row counts | Today's API returns table names but not sizes. Row counts would enable verification without DFS |

### Priority 2: Job Execution

| Improvement | Rationale |
|---|---|
| Consistent job types across items | `CopyJob` vs `RunNotebook` vs `DefaultJob` — should be consistent or auto-detected |
| Job output/result in status response | After a notebook job completes, the status response should include cell outputs or at least success/failure per cell |

### Priority 3: Workspace Management

| Improvement | Rationale |
|---|---|
| `executeQueries` on SQL Endpoints (not just Warehouses) | Today only Warehouses support the `executeQueries` API. Lakehouse SQL endpoints return 404. This blocks SQL-based verification |
| Workspace template API — create workspace from definition | Like ARM templates but for Fabric workspaces. Create workspace + all items from a JSON/YAML spec |
| Workspace diff API — compare two workspaces | Return the delta between source and target workspace items |

### Priority 4: Git Integration API

| Improvement | Rationale |
|---|---|
| Programmatic Git connect — `POST /workspaces/{id}/gitConnection` | Today requires portal clicks. Should be API-driven for automation |
| Git sync trigger — `POST /workspaces/{id}/gitSync` | Trigger a Git→Fabric pull programmatically (for CI/CD after PR merge) |
| Git status — `GET /workspaces/{id}/gitStatus` | Check if workspace has pending changes without opening the portal |

---

## What We Built (SDK) vs What Should Be Native

Our SDK exists because of gaps. As those gaps close, parts of the SDK should become unnecessary:

| SDK Capability | Should Move To | When |
|---|---|---|
| `deploy` (full bootstrap) | `fab bootstrap` or `fabric-cicd` with job hooks | When CLI/cicd support post-deploy job execution |
| `status` (state assessment) | `fab status` | When CLI gets desired-vs-current diff |
| `verify` (data checks) | `fab verify` or `fabric-cicd verify()` | When `/tables` works on schema-enabled LH + `executeQueries` on SQL endpoints |
| `run-job` (with polling) | `fab run --wait` | When CLI supports all job types with `--wait` |
| `--diff` (planned actions) | `fab diff` or `fabric-cicd` diff output | When either tool shows create/update/skip per item |
| `--output json` | `fab status --json` | When CLI supports structured output |
| DFS table listing fallback | Not needed | When `/tables` API supports schema-enabled lakehouses |
| `_TTLCache` | Not needed | When tools don't call the same API 5x per run |
| Parallel job polling | `fabric-cicd` | When cicd supports concurrent job execution |
| `parameter.yml` stub creation | Not needed | When `fabric-cicd` tolerates missing parameter file |
| `fabric-cicd` endpoint override | Not needed | When `fabric-cicd` respects `FABRIC_API_ROOT_URL` env var properly |

---

## Recommended Direction

**Short term (now):** Use Git Integration for definitions + SDK for data plane. This is what the workshop teaches.

**Medium term:** fabric-cli gains `run --wait`, `status`, `verify`. fabric-cicd gains post-publish hooks and diff. SDK shrinks to config + orchestration.

**Long term:** A single `fab deploy` command that reads a workspace config, diffs against current state, deploys definitions (via fabric-cicd), runs jobs, verifies data, and outputs a structured result. The SDK concepts (state engine, phased deployment, verification) become native CLI capabilities.

The design principle: **Git Integration owns what the code says. The CLI/SDK owns what the data looks like. The REST API enables both.**
