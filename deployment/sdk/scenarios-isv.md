# Fabric CI/CD Scenarios — ISV Personas

Scenarios specific to Independent Software Vendors (ISVs) building products and managed services on Microsoft Fabric. These differ from enterprise scenarios in that the ISV **owns the deployment pipeline** across many customer tenants, and the Fabric workspace is a **product artifact** — not an internal tool.

---

## ISV Personas

| Persona | Role | Primary Concern |
|---------|------|-----------------|
| **Product Engineer** | Builds the data product (notebooks, lakehouses, models) | "How do I ship a new version of my product to 200 customer workspaces without breaking any of them?" |
| **Tenant Provisioning Engineer** | Automates new customer onboarding | "How do I stamp out an identical workspace per customer in minutes, with their specific config?" |
| **Release Manager** | Manages versioned releases across tenants | "How do I roll out v2.3 to 10% of customers first, then the rest after validation?" |
| **Customer Success Engineer** | Troubleshoots customer-specific issues | "How do I see what version a customer is on, what data is missing, and fix it without accessing their data?" |
| **ISV Platform Architect** | Designs the multi-tenant deployment model | "How do I support per-customer config (schemas, columns, data sources) without forking the codebase?" |
| **Partner Solutions Engineer** | Pre-sales, POC delivery | "How do I spin up a demo environment for a prospect that looks like the real product in 15 minutes?" |

---

## ISV-Specific Scenarios

### 1. Multi-Tenant Workspace Stamping

> **User Story:** *As a Tenant Provisioning Engineer, I want to deploy an identical workspace for each new customer from a versioned template, with customer-specific connection strings and branding, so that onboarding is automated and consistent across hundreds of tenants.*

> **Trigger:** New customer signs contract, needs their Fabric workspace  
> **Persona:** Tenant Provisioning Engineer

| Step | Action | Tool |
|------|--------|------|
| Accept customer config | Tenant ID, capacity, data source URLs | CRM / API webhook |
| Create workspace | Per-customer workspace with naming convention | REST API / SDK |
| Apply tenant config | Replace placeholders with customer-specific values | SDK placeholders + per-tenant `parameter.yml` |
| Deploy items | Lakehouses, notebooks, copy jobs, semantic model, report | SDK `deploy` / `fabric-cicd` |
| Hydrate initial data | Run ingestion jobs from customer's data source | SDK `run-job` |
| Verify | Confirm all tables populated, report loads | SDK `verify` |
| Tag version | Record which product version was deployed | Git tag + metadata API |

**Key concern:** Every tenant gets the same codebase version but different GUIDs, connection strings, and possibly different capacity SKUs. The template must be parameterizable — not hardcoded to any single tenant.

---

### 2. Versioned Rollout (Canary / Ring Deployment)

> **User Story:** *As a Release Manager, I want to roll out a new product version to a small ring of customers first, validate it works, then promote to all tenants, so that a bad release never affects the entire customer base.*

> **Trigger:** New product release ready  
> **Persona:** Release Manager

| Step | Action | Tool |
|------|--------|------|
| Tag release | Git tag `v2.3.0` on the release branch | Git |
| Select canary ring | Pick 5-10% of tenants for early rollout | Tenant registry |
| Deploy to canary | For each canary tenant: `deploy --on-exists update` | SDK / CI pipeline |
| Run jobs | Re-run notebooks to apply schema changes | SDK `run-job` |
| Verify canary | `verify` on each canary tenant | SDK / CI pipeline |
| Monitor | Wait 24-48h, check for errors | Fabric monitoring / alerts |
| Promote to all | Deploy to remaining tenants | SDK / CI pipeline (parallelized) |
| Update tenant registry | Record current version per tenant | Metadata store |

**Key concern:** You need a tenant registry that tracks which version each customer is on. Rollout must be resumable — if it fails on tenant 47/200, you restart from 47, not from 1.

---

### 3. Per-Tenant Customization Without Forking

> **User Story:** *As an ISV Platform Architect, I want to support customer-specific schemas (extra columns, custom tables) without maintaining separate codebases, so that the product scales without O(n) code branches.*

> **Trigger:** Customer requests a custom field or table  
> **Persona:** ISV Platform Architect

| Step | Action | Tool |
|------|--------|------|
| Define extension point | Standard notebook with optional extension cells | Code convention |
| Customer config | `tenant_config.yml` declares extra columns / tables | Per-tenant config file |
| Template renders | Notebook template includes conditional SQL blocks | SDK template engine / Jinja |
| Deploy | Standard deploy with tenant-specific config overlay | SDK `deploy` + config merge |
| Verify | Standard checks + tenant-specific checks | SDK `verify` with merged config |

**Key concern:** The base product is ONE codebase. Customer customizations are config-driven overlays — never code forks. If you fork, you can't ship updates to the base product without N merge conflicts.

---

### 4. Customer Environment Diagnosis & Repair

> **User Story:** *As a Customer Success Engineer, I want to remotely check a customer's workspace state and identify missing or stale data without accessing their raw data, so that I can resolve issues quickly during a support call.*

> **Trigger:** Customer reports "my report shows no data"  
> **Persona:** Customer Success Engineer

| Step | Action | Tool |
|------|--------|------|
| Identify tenant | Look up customer's workspace ID + version | Tenant registry |
| Remote state check | `status --output json` on their workspace | SDK / support API |
| Identify gap | See which resources are missing or stale | State assessment |
| Remote verify | `verify --output json` — check data expectations | SDK / support API |
| Targeted fix | Re-run specific job or re-deploy specific item | SDK `run-job` / `deploy-item` |
| Confirm | `verify` passes | SDK |

**Key concern:** The support engineer should NEVER need to open the customer's lakehouse and browse their data. The `status` and `verify` commands give a structural view (does the table exist? does it have rows?) without exposing PII.

---

### 5. Demo / POC Environment Provisioning

> **User Story:** *As a Partner Solutions Engineer, I want to spin up a fully working demo of our product for a prospect in 15 minutes, pre-loaded with sample data, so that the sales meeting is productive and the prospect sees the real product — not slides.*

> **Trigger:** Sales meeting, conference demo, POC kickoff  
> **Persona:** Partner Solutions Engineer

| Step | Action | Tool |
|------|--------|------|
| Create demo workspace | Temporary workspace on demo capacity | Portal / SDK |
| Deploy product | Full bootstrap from latest stable release tag | SDK `deploy` |
| Load sample data | Run ingestion with demo dataset (not real customer data) | SDK `run-job` |
| Verify | Confirm everything works | SDK `verify` |
| Demo | Walk prospect through the report, lakehouses, notebooks | Fabric Portal |
| Teardown | Delete workspace after demo (or set TTL) | REST API / scheduled cleanup |

**Key concern:** Demo environments must use the same code as production (so the demo is honest) but with sample data (so there's no PII risk). The bootstrap makes this a one-command operation.

---

### 6. Product Version Audit & Compliance

> **User Story:** *As a Release Manager, I want to know exactly which product version each customer tenant is running, including whether any tenants have drifted from the expected state, so that I can ensure compliance and plan forced upgrades.*

> **Trigger:** Quarterly audit, security patch, compliance requirement  
> **Persona:** Release Manager

| Step | Action | Tool |
|------|--------|------|
| Enumerate tenants | List all customer workspaces + expected versions | Tenant registry |
| Batch state check | `status --output json` on each tenant | SDK (parallelized) |
| Detect drift | Compare actual state to expected state for the version | Custom diff logic |
| Report | Generate compliance report: on-version, drifted, missing items | JSON processing |
| Remediate | For drifted tenants: `deploy --on-exists update` | SDK |
| Re-audit | Confirm remediation | SDK `verify` |

**Key concern:** Customers may have made manual changes in the portal (edited a notebook, deleted a shortcut). The state assessment detects this drift. The question is policy: do you overwrite their changes (managed service) or flag for review (co-managed)?

---

### 7. Schema Migration Across All Tenants

> **User Story:** *As a Product Engineer, I want to add a new column to the product's core table across all customer tenants, without downtime and without losing any customer data, so that the new feature works for everyone on the next refresh.*

> **Trigger:** Product feature requires schema change  
> **Persona:** Product Engineer

| Step | Action | Tool |
|------|--------|------|
| Develop migration notebook | `ALTER TABLE ADD COLUMN` or new `CREATE TABLE` | VS Code / Fabric |
| Test in dev tenant | Deploy + run + verify on internal workspace | SDK |
| Tag release | Include migration notebook in release | Git tag |
| Canary rollout | Deploy to ring-0 tenants | SDK / CI pipeline |
| Run migration | Execute notebook on each tenant | SDK `run-job` (parallelized across tenants) |
| Verify per tenant | `verify` with new column check | SDK |
| Full rollout | Deploy + run + verify on remaining tenants | SDK / CI pipeline |

**Key concern:** The migration must be idempotent — if it fails on tenant 47, re-running on tenant 47 must work without double-adding the column. `ALTER TABLE ADD COLUMN IF NOT EXISTS` or conditional DDL is essential.

---

## ISV vs Enterprise — Key Differences

| Dimension | Enterprise | ISV |
|-----------|-----------|-----|
| **Tenant count** | 1-5 environments | 10s to 1000s of customer workspaces |
| **Config variety** | Dev/test/prod (same schema) | Per-customer schemas, data sources, SKUs |
| **Deployment cadence** | Sprint-based | Versioned releases with canary rings |
| **Rollback scope** | One workspace | Subset of tenants |
| **State visibility** | Team knows their workspace | Need remote audit across all tenants |
| **Customization** | Branch per environment | Config overlays, never code forks |
| **Data isolation** | By workspace | By workspace + potentially by capacity/region |
| **Compliance** | Internal policy | Customer SLAs, SOC2, data residency |

## SDK Gaps for ISV Scenarios

| Gap | What's Needed |
|-----|---------------|
| **Tenant registry** | Track workspace ID → customer → version → last deploy time |
| **Batch operations** | `deploy` / `verify` across N workspaces in parallel |
| **Config overlays** | Merge base `workspace_config.yml` + per-tenant `tenant_config.yml` |
| **Version tagging** | Stamp workspace metadata with deployed Git tag |
| **Drift detection** | Compare expected state (from Git tag) to actual state |
| **Migration runner** | Run a specific notebook cell (not the whole notebook) for schema migrations |
