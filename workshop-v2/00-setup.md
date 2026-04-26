# Module 0: Setup & Tooling

> *As any team member, I want my local environment ready so I can follow along.*

**Duration:** 20 minutes | **Persona:** All

## Prerequisites

- Microsoft Fabric capacity (trial or premium) with a workspace you can admin
- GitHub or Azure DevOps account — see [Git Integration Reference](git-integration-reference.md)
- macOS, Linux, or Windows with WSL

## Exercise 1: Install Tools (10 min)

### Python & Packages

```bash
# Verify Python 3.11+
python3 --version

# Install SDK dependencies
pip3 install azure-identity requests fabric-cicd pyyaml
```

### Azure CLI

```bash
# Install (if needed)
brew install azure-cli    # macOS
# or: curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash   # Linux

# Login — this is how the SDK authenticates
az login --tenant <your-tenant-id>
```

### Git

```bash
git --version   # should be 2.x+
```

## Exercise 2: Fork & Clone the Repo (5 min)

Follow the setup steps for your Git provider in the [Git Integration Reference](git-integration-reference.md#setup-fork--create-the-repository).

Short version:

```bash
git clone https://github.com/<your-username>/Fabric-DE-CICD.git
cd Fabric-DE-CICD
```

## Exercise 3: Understand the Repo Layout (5 min)

```
Fabric-DE-CICD/
├── deployment/
│   ├── workshop_template/     ← Item templates with placeholder GUIDs (for bootstrapping)
│   └── sdk/                   ← Python SDK: bootstrap, deploy, verify
│       ├── bootstrap.py       ← CLI entry point
│       ├── workspace_config.yml ← All items, phases, verifications declared here
│       └── ...
├── DE_Workshop/               ← Live Fabric items (real GUIDs, managed by Git integration)
└── workshop-v2/               ← You are here
```

**Key distinction:**
- `workshop_template/` = source templates for creating new workspaces (placeholder GUIDs)
- `DE_Workshop/` = live workspace state synced by Fabric Git integration (real GUIDs)

## Further Reading

- [fabric-cicd Library — Installation & Quick Start](https://microsoft.github.io/fabric-cicd/) — the open-source library our SDK builds upon
- [fabric-cicd Tutorial](https://microsoft.github.io/fabric-cicd/0.1.30/how_to/tutorial/) — official step-by-step for the library alone
- [CI/CD Overview in Microsoft Fabric](https://learn.microsoft.com/en-us/fabric/cicd/) — MS Learn hub for all CI/CD capabilities

## Checkpoint

- [ ] `python3 --version` shows 3.11+
- [ ] `az account show` shows your account
- [ ] Repo cloned, you can `ls deployment/sdk/`
