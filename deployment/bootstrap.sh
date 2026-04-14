#!/bin/bash
set -euo pipefail

# -------------------------------------------------------------------
# Standalone Fabric DE bootstrap
#
# Provisions (or reuses) a workspace and deploys all DE artifacts:
#   lakehouses, environment, notebooks, copy jobs, shortcuts,
#   semantic model, and report.
#
# State-aware: checks what already exists and skips, updates, or
# recreates items based on the --on-exists flag.
#
# Usage:
#   ./bootstrap.sh --workspace-name MyWorkspace --existing-workspace
#   ./bootstrap.sh --workspace-name MyWorkspace --existing-workspace --on-exists force
#   ./bootstrap.sh --workspace-name MyWorkspace --capacity-name MyCap
# -------------------------------------------------------------------

# ── defaults ──────────────────────────────────────────────────────
workspace_name=""
capacity_name=""
existing_workspace=false
on_exists="skip"   # skip | force
spn_auth_enabled="false"
upn_objectid=""

staging_dir="./tmp"
EXIT_ON_ERROR=true

# ── source helpers ────────────────────────────────────────────────
source ./scripts/fab_functions.sh   # run_fab_command, get_fab_property, import_*
source ./scripts/replace_metadata.sh  # replace_string_value

# ── utility: check if item exists (uses get, not exists, for reliability) ──
item_exists() {
    local path="$1"
    fab -c "get ${path} -q id" >/dev/null 2>&1
}

# ── utility: run a fab command with retry on transient errors ─────
run_fab_with_retry() {
    local cmd="$1"
    local max_retries="${2:-6}"
    local wait_seconds="${3:-15}"
    for (( i=1; i<=max_retries; i++ )); do
        local output
        output=$(run_fab_command "$cmd" 2>&1) && { echo "$output"; return 0; }
        if echo "$output" | grep -qE "ItemDisplayNameNotAvailableYet|NotFound.*could not be found"; then
            echo "  [retry ${i}/${max_retries}] Transient error, waiting ${wait_seconds}s..."
            sleep "$wait_seconds"
        else
            echo "$output" >&2
            return 1
        fi
    done
    echo "Error: Still failing after ${max_retries} retries." >&2
    return 1
}

# ── utility: create item if not exists, or handle per on_exists ───
ensure_item() {
    local path="$1"
    local create_cmd="$2"
    local label="${3:-$path}"

    if item_exists "$path"; then
        if [[ "$on_exists" == "force" ]]; then
            echo "  [force] removing existing: ${label}"
            run_fab_command "rm -f ${path}" || true
            echo "  [force] recreating: ${label}"
            run_fab_with_retry "$create_cmd"
        else
            echo "  [skip] already exists: ${label}"
        fi
    else
        run_fab_with_retry "$create_cmd"
    fi
}

# ── utility: import item if not exists, or handle per on_exists ───
ensure_import() {
    local path="$1"
    local import_cmd="$2"
    local label="${3:-$path}"

    if item_exists "$path"; then
        if [[ "$on_exists" == "force" ]]; then
            echo "  [force] removing existing: ${label}"
            run_fab_command "rm -f ${path}" || true
            echo "  [force] reimporting: ${label}"
            run_fab_with_retry "$import_cmd"
        else
            echo "  [skip] already exists: ${label}"
        fi
    else
        run_fab_with_retry "$import_cmd"
    fi
}

# ── arg parsing ───────────────────────────────────────────────────
usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Required:
  --workspace-name  <name>   Fabric workspace name (without .Workspace suffix)

Optional:
  --capacity-name   <name>   Capacity to create/assign (required unless --existing-workspace)
  --existing-workspace       Skip workspace creation & capacity assignment
  --on-exists       <mode>   What to do when an item already exists:
                               skip  - skip it (default)
                               force - remove and recreate
  --spn-auth-enabled <bool>  Use service-principal auth (default: false)
  --upn-objectid     <id>    UPN object ID for ACL when using SPN auth

Examples:
  $0 --workspace-name DEWorkshop_yoav --existing-workspace
  $0 --workspace-name DEWorkshop_yoav --existing-workspace --on-exists force
  $0 --workspace-name DEWorkshop_yoav --capacity-name MyCapacity
EOF
    exit 1
}

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --workspace-name)       workspace_name="$2"; shift ;;
        --capacity-name)        capacity_name="$2"; shift ;;
        --existing-workspace)   existing_workspace=true ;;
        --on-exists)            on_exists="$2"; shift ;;
        --spn-auth-enabled)     spn_auth_enabled="$2"; shift ;;
        --upn-objectid)         upn_objectid="$2"; shift ;;
        -h|--help)              usage ;;
        *) echo "Error: Unknown parameter: $1"; usage ;;
    esac
    shift
done

# ── validate inputs ───────────────────────────────────────────────
if [[ -z "$workspace_name" ]]; then
    echo "Error: --workspace-name is required."
    usage
fi

if [[ "$on_exists" != "skip" && "$on_exists" != "force" ]]; then
    echo "Error: --on-exists must be 'skip' or 'force'."
    usage
fi

if [[ "$existing_workspace" == false && -z "$capacity_name" ]]; then
    echo "Error: --capacity-name is required when creating a new workspace."
    echo "       Use --existing-workspace to skip workspace creation."
    usage
fi

# ── derived names ─────────────────────────────────────────────────
_ws="${workspace_name}.Workspace"
_lakehouse_bronze_name_no_ext="Lakehouse_Bronze"
_lakehouse_bronze_name="${_lakehouse_bronze_name_no_ext}.Lakehouse"
_lakehouse_silver_name_no_ext="Lakehouse_Silver"
_lakehouse_silver_name="${_lakehouse_silver_name_no_ext}.Lakehouse"
_environment_name="MyEnv.Environment"
_notebook_names=("Bronze_Data_Preparation.Notebook" "Transformations.Notebook" "Validations.Notebook")
_copyjob_names=("MyLHCopyJob.CopyJob" "MyLHCopyJob2.CopyJob")
_sem_model_name="MySemanticModel.SemanticModel"
_report_name="MyReport.Report"

# ── SPN auth (if enabled) ────────────────────────────────────────
if [[ "$spn_auth_enabled" == "true" ]]; then
    echo -e "\n_ authenticating with service principal..."
    run_fab_command "auth login -u $FAB_CLIENT_ID -p $FAB_CLIENT_SECRET --tenant $FAB_TENANT_ID"
    echo "* Done"
fi

# ── workspace ─────────────────────────────────────────────────────
if [[ "$existing_workspace" == true ]]; then
    echo -e "\n_ using existing workspace: ${_ws}"
    # Quick sanity check – make sure the workspace is reachable
    _workspace_id=$(run_fab_command "get /${_ws} -q id" | tr -d '\r')
    if [[ -z "$_workspace_id" ]]; then
        echo "Error: Workspace '${_ws}' not found or not accessible."
        exit 1
    fi
    echo "  Workspace ID: ${_workspace_id}"
else
    echo -e "\n_ validating capacity: ${capacity_name}..."
    if ! fab -c "get .capacities/${capacity_name}.Capacity" >/dev/null 2>&1; then
        echo "Error: Capacity '${capacity_name}' not found or not a valid Fabric capacity."
        echo "       List available capacities with: fab ls .capacities"
        exit 1
    fi

    echo -e "\n_ creating workspace: ${_ws}..."
    run_fab_command "create /${_ws} -P capacityName=${capacity_name}"

    if [[ "$spn_auth_enabled" == "true" && -n "$upn_objectid" ]]; then
        echo -e "\n_ assigning workspace permissions..."
        run_fab_command "acl set -f /${_ws} -I $upn_objectid -R admin"
    fi

    _workspace_id=$(run_fab_command "get /${_ws} -q id" | tr -d '\r')
    if [[ -z "$_workspace_id" ]]; then
        echo "Error: Workspace creation succeeded but could not retrieve workspace ID."
        exit 1
    fi
    echo "  Workspace ID: ${_workspace_id}"
fi

# ── staging ───────────────────────────────────────────────────────
echo -e "\n_ preparing staging directory..."
mkdir -p "$staging_dir"
cp -r ./workshop_template/* "$staging_dir/"
echo "* Done"

# ══════════════════════════════════════════════════════════════════
#  DESIRED STATE vs CURRENT STATE
# ══════════════════════════════════════════════════════════════════
# Define everything that should exist at the end of this script.
# Check what actually exists now. Show a plan. Execute only deltas.

echo -e "\n═══════════════════════════════════════"
echo "  State Assessment: ${_ws}"
echo "═══════════════════════════════════════"

# ── helper: check and record state (file-based, bash 3 compatible) ─
_state_dir=$(mktemp -d)
trap 'rm -rf "$_state_dir"' EXIT

set_state() { echo "$2" > "$_state_dir/$1"; }
get_state() { cat "$_state_dir/$1" 2>/dev/null || echo "missing"; }

check_item() {
    local key="$1" path="$2"
    if item_exists "$path"; then set_state "$key" "exists"; else set_state "$key" "missing"; fi
}

check_path() {
    local key="$1" path="$2"
    if fab -c "ls ${path}" >/dev/null 2>&1; then set_state "$key" "exists"; else set_state "$key" "missing"; fi
}

# Items
check_item "lakehouse_bronze"  "/${_ws}/${_lakehouse_bronze_name}"
check_item "lakehouse_silver"  "/${_ws}/${_lakehouse_silver_name}"
check_item "environment"       "/${_ws}/${_environment_name}"
for _nb in "${_notebook_names[@]}"; do check_item "nb:${_nb}" "/${_ws}/${_nb}"; done
for _cj in "${_copyjob_names[@]}"; do check_item "cj:${_cj}" "/${_ws}/${_cj}"; done
check_item "semantic_model"    "/${_ws}/${_sem_model_name}"
check_item "report"            "/${_ws}/${_report_name}"

# Data / paths (produced by jobs) — check via Tables listing, not Tables/dbo
_bronze_tables=$(fab -c "ls /${_ws}/${_lakehouse_bronze_name}/Tables" 2>&1 || true)
_silver_tables=$(fab -c "ls /${_ws}/${_lakehouse_silver_name}/Tables" 2>&1 || true)

if echo "$_bronze_tables" | grep -q "dbo"; then set_state "schema_bronze_dbo" "exists"; else set_state "schema_bronze_dbo" "missing"; fi
if echo "$_silver_tables" | grep -q "dbo"; then set_state "schema_silver_dbo" "exists"; else set_state "schema_silver_dbo" "missing"; fi
if echo "$_bronze_tables" | grep -q "t2"; then set_state "data_bronze_t2" "exists"; else set_state "data_bronze_t2" "missing"; fi
if echo "$_bronze_tables" | grep -q "t3_dev"; then set_state "data_bronze_t3" "exists"; else set_state "data_bronze_t3" "missing"; fi
if echo "$_silver_tables" | grep -q "t1"; then set_state "data_silver_t1" "exists"; else set_state "data_silver_t1" "missing"; fi
if echo "$_silver_tables" | grep -q "t2"; then set_state "shortcut_t2" "exists"; else set_state "shortcut_t2" "missing"; fi
if echo "$_silver_tables" | grep -q "t3"; then set_state "shortcut_t3" "exists"; else set_state "shortcut_t3" "missing"; fi

# Display state table
printf "\n  %-12s  %-45s  %s\n" "CATEGORY" "RESOURCE" "STATE"
printf "  %-12s  %-45s  %s\n" "────────────" "─────────────────────────────────────────────" "───────"
_plan_items=(
    "Item        |${_lakehouse_bronze_name}|lakehouse_bronze"
    "Item        |${_lakehouse_silver_name}|lakehouse_silver"
    "Item        |${_environment_name}|environment"
)
for _nb in "${_notebook_names[@]}"; do _plan_items+=("Item        |${_nb}|nb:${_nb}"); done
for _cj in "${_copyjob_names[@]}"; do _plan_items+=("Item        |${_cj}|cj:${_cj}"); done
_plan_items+=(
    "Item        |${_sem_model_name}|semantic_model"
    "Item        |${_report_name}|report"
    "Schema      |Bronze Tables/dbo|schema_bronze_dbo"
    "Schema      |Silver Tables/dbo|schema_silver_dbo"
    "Data        |Bronze t2 (from copy jobs)|data_bronze_t2"
    "Data        |Bronze t3_dev (from notebook)|data_bronze_t3"
    "Data        |Silver t1 (from notebook)|data_silver_t1"
    "Shortcut    |Silver t2 → Bronze t2|shortcut_t2"
    "Shortcut    |Silver t3 → Bronze t3_dev|shortcut_t3"
)

_missing_count=0
for _entry in "${_plan_items[@]}"; do
    IFS='|' read -r _cat _label _key <<< "$_entry"
    _st="$(get_state "$_key")"
    if [[ "$_st" == "exists" ]]; then
        _marker="✓"
    else
        _marker="·"
        ((_missing_count++)) || true
    fi
    printf "  %-12s  %-45s  %s %s\n" "$_cat" "$_label" "$_marker" "$_st"
done

echo ""
if [[ $_missing_count -eq 0 ]]; then
    echo "  All resources are in desired state. Nothing to do."
    open_workspace "$_ws"
    rm -rf "$staging_dir"
    echo -e "\n========================================="
    echo "  Bootstrap complete: ${_ws}"
    echo "  Workspace ID: ${_workspace_id}"
    echo "========================================="
    exit 0
fi
echo "  ${_missing_count} resource(s) need action (mode: --on-exists ${on_exists})"
echo ""

# ══════════════════════════════════════════════════════════════════
#  PHASE 1: Items (lakehouses, environment, notebooks, copy jobs)
# ══════════════════════════════════════════════════════════════════

# ── lakehouses ────────────────────────────────────────────────────
echo -e "\n_ [phase 1] lakehouses..."
ensure_item "/${_ws}/${_lakehouse_bronze_name}" "create /${_ws}/${_lakehouse_bronze_name} -P enableschemas=true" "${_lakehouse_bronze_name}"
ensure_item "/${_ws}/${_lakehouse_silver_name}" "create /${_ws}/${_lakehouse_silver_name} -P enableschemas=true" "${_lakehouse_silver_name}"

# ── environment ───────────────────────────────────────────────────
echo -e "\n_ [phase 1] environment..."
ensure_import "/${_ws}/${_environment_name}" "import -f /${_ws}/${_environment_name} -i ${staging_dir}/${_environment_name}" "${_environment_name}"

# ── metadata ──────────────────────────────────────────────────────
echo -e "\n_ [phase 1] retrieving item metadata..."
_lakehouse_bronze_id=$(get_fab_property "/${_ws}/${_lakehouse_bronze_name}" "id")
_lakehouse_silver_id=$(get_fab_property "/${_ws}/${_lakehouse_silver_name}" "id")
_lakehouse_silver_conn_id=$(get_fab_property "/${_ws}/${_lakehouse_silver_name}" "properties.sqlEndpointProperties.id")
_lakehouse_silver_conn_string=$(get_fab_property "/${_ws}/${_lakehouse_silver_name}" "properties.sqlEndpointProperties.connectionString")
echo "  Bronze LH ID:            ${_lakehouse_bronze_id}"
echo "  Silver LH ID:            ${_lakehouse_silver_id}"
echo "  Silver SQL Endpoint ID:  ${_lakehouse_silver_conn_id}"
echo "  Silver SQL Conn String:  ${_lakehouse_silver_conn_string}"

# ── notebooks ─────────────────────────────────────────────────────
for _nb in "${_notebook_names[@]}"; do
    echo -e "\n_ [phase 1] notebook: ${_nb}..."
    ensure_import "/${_ws}/${_nb}" "import -f /${_ws}/${_nb} -i ${staging_dir}/${_nb}" "${_nb}"
    run_fab_command "set -f /${_ws}/${_nb} -q lakehouse -i '{\"known_lakehouses\": [{\"id\": \"${_lakehouse_silver_id}\"}],\"default_lakehouse\": \"${_lakehouse_silver_id}\",\"default_lakehouse_name\": \"${_lakehouse_silver_name_no_ext}\",\"default_lakehouse_workspace_id\": \"${_workspace_id}\"}'"
done
run_fab_command "set -f /${_ws}/Bronze_Data_Preparation.Notebook -q lakehouse -i '{\"known_lakehouses\": [{\"id\": \"${_lakehouse_bronze_id}\"}],\"default_lakehouse\": \"${_lakehouse_bronze_id}\",\"default_lakehouse_name\": \"${_lakehouse_bronze_name_no_ext}\",\"default_lakehouse_workspace_id\": \"${_workspace_id}\"}'"

# ── copy jobs ─────────────────────────────────────────────────────
for _cj in "${_copyjob_names[@]}"; do
    echo -e "\n_ [phase 1] copy job: ${_cj}..."
    replace_string_value "$_cj" "copyjob-content.json" "8e0cc78d-1667-4e88-9523-a04c1d5dd187" "$_workspace_id"
    replace_string_value "$_cj" "copyjob-content.json" "3ad63567-2849-4e5b-9cf2-eacd059e50a5" "$_lakehouse_bronze_id"
    ensure_import "/${_ws}/${_cj}" "import -f /${_ws}/${_cj} -i ${staging_dir}/${_cj}" "${_cj}"
done

# ══════════════════════════════════════════════════════════════════
#  PHASE 2: Run copy jobs, wait for data
# ══════════════════════════════════════════════════════════════════
# Note: Tables/dbo schema path only materializes AFTER data lands,
# so we run copy jobs first then poll for the result tables.

# Run copy jobs → produces t2 in bronze
if [[ "$(get_state data_bronze_t2)" == "exists" ]]; then
    echo -e "\n_ [phase 2] [skip] copy jobs already ran (t2 exists in bronze)"
else
    for _cj in "${_copyjob_names[@]}"; do
        echo -e "\n_ [phase 2] running copy job: ${_cj}..."
        _cj_id=$(get_fab_property "/${_ws}/${_cj}" "id")
        run_fab_command "api -X post workspaces/${_workspace_id}/items/${_cj_id}/jobs/instances?jobType=Execute" >/dev/null
        echo "  Started."
    done

    # Wait for t2 table to appear — this also implies Tables/dbo is ready
    echo -e "\n_ [phase 2] waiting for copy job results..."
    echo "  (Tables/dbo schema & t2 table appear once data lands)"
    for (( _r=1; _r<=40; _r++ )); do
        # Try listing via the item level (works even if dbo isn't browsable yet)
        if fab -c "ls /${_ws}/${_lakehouse_bronze_name}/Tables" 2>&1 | grep -q "t2"; then
            echo "  t2 table ready."
            break
        fi
        if (( _r % 4 == 0 )); then
            echo "  [${_r}/40] still waiting... ($(( _r * 15 ))s elapsed)"
        fi
        sleep 15
    done

    if ! fab -c "ls /${_ws}/${_lakehouse_bronze_name}/Tables" 2>&1 | grep -q "t2"; then
        echo "  [warning] t2 table not found after 10 min. Copy jobs may have failed."
        echo "  Check copy job status in the Fabric portal and re-run the script."
        exit 1
    fi
fi

# ══════════════════════════════════════════════════════════════════
#  PHASE 3: Shortcuts and notebook runs (depend on data)
# ══════════════════════════════════════════════════════════════════

# Shortcut: t2 in silver → t2 in bronze (requires t2 to exist in bronze)
echo -e "\n_ [phase 3] shortcut: t2 → silver..."
if [[ "$(get_state shortcut_t2)" == "exists" ]]; then
    echo "  [skip] already exists"
else
    # Verify precondition
    if ! fab -c "ls /${_ws}/${_lakehouse_bronze_name}/Tables" 2>&1 | grep -q "t2"; then
        echo "  [blocked] Cannot create shortcut: source t2 table does not exist in bronze."
        echo "           Copy jobs may not have completed. Re-run the script."
        exit 1
    fi
    run_fab_with_retry "ln -f /${_ws}/${_lakehouse_silver_name}/Tables/dbo/t2.Shortcut --type oneLake --target /${_ws}/${_lakehouse_bronze_name}/Tables/dbo/t2" 12 15
fi

# Bronze notebook → creates t3_dev
echo -e "\n_ [phase 3] Bronze notebook → t3_dev..."
if [[ "$(get_state data_bronze_t3)" == "exists" ]]; then
    echo "  [skip] t3_dev already exists"
else
    echo "  Running Bronze_Data_Preparation notebook..."
    run_fab_command "job run /${_ws}/Bronze_Data_Preparation.Notebook"
    # Wait for t3_dev
    echo "  Waiting for t3_dev..."
    for (( _r=1; _r<=20; _r++ )); do
        if fab -c "ls /${_ws}/${_lakehouse_bronze_name}/Tables" 2>&1 | grep -q "t3_dev"; then
            echo "  t3_dev ready."
            break
        fi
        if (( _r % 4 == 0 )); then
            echo "  [${_r}/20] still waiting... ($(( _r * 15 ))s elapsed)"
        fi
        sleep 15
    done
fi

# Shortcut: t3 in silver → t3_dev in bronze
echo -e "\n_ [phase 3] shortcut: t3 → silver..."
if [[ "$(get_state shortcut_t3)" == "exists" ]]; then
    echo "  [skip] already exists"
else
    if ! fab -c "ls /${_ws}/${_lakehouse_bronze_name}/Tables" 2>&1 | grep -q "t3_dev"; then
        echo "  [blocked] Cannot create shortcut: source t3_dev table does not exist in bronze."
        exit 1
    fi
    run_fab_with_retry "ln -f /${_ws}/${_lakehouse_silver_name}/Tables/dbo/t3.Shortcut --type oneLake --target /${_ws}/${_lakehouse_bronze_name}/Tables/dbo/t3_dev" 12 15
fi

# Transformations notebook → creates t1 in silver
echo -e "\n_ [phase 3] Transformations notebook → t1..."
if [[ "$(get_state data_silver_t1)" == "exists" ]]; then
    echo "  [skip] t1 already exists"
else
    echo "  Running Transformations notebook..."
    run_fab_command "job run /${_ws}/Transformations.Notebook"
fi

# ══════════════════════════════════════════════════════════════════
#  PHASE 4: Semantic model and report
# ══════════════════════════════════════════════════════════════════

echo -e "\n_ [phase 4] semantic model..."
replace_string_value "$_sem_model_name" "definition/expressions.tmdl" \
    "X6EPS4XRQ2XUDENLFV6NAEO3I4-RXDQZDTHC2EE5FJDUBGB2XORQ4.msit-datawarehouse.fabric.microsoft.com" \
    "$_lakehouse_silver_conn_string"
replace_string_value "$_sem_model_name" "definition/expressions.tmdl" \
    "48d64684-b584-4ef5-ad7b-a094b42f52f8" \
    "$_lakehouse_silver_conn_id"

if [[ "$(get_state semantic_model)" == "exists" && "$on_exists" != "force" ]]; then
    echo "  [skip] already exists"
else
    if [[ "$(get_state semantic_model)" == "exists" ]]; then
        echo "  [force] removing existing: ${_sem_model_name}"
        run_fab_command "rm -f /${_ws}/${_sem_model_name}" || true
    fi
    import_semantic_model "$_ws" "$_sem_model_name"
fi
_semantic_model_id=$(get_fab_property "/${_ws}/${_sem_model_name}" "id")

echo -e "\n_ [phase 4] report..."
replace_string_value "$_report_name" "definition.pbir" \
    "e4e9593c-b1a9-428e-9581-64939a83c4d9" \
    "$_semantic_model_id"

if [[ "$(get_state report)" == "exists" && "$on_exists" != "force" ]]; then
    echo "  [skip] already exists"
else
    if [[ "$(get_state report)" == "exists" ]]; then
        echo "  [force] removing existing: ${_report_name}"
        run_fab_command "rm -f /${_ws}/${_report_name}" || true
    fi
    import_powerbi_report "$_ws" "$_report_name" "$_semantic_model_id"
fi

# ── open & clean up ──────────────────────────────────────────────
open_workspace "$_ws"

echo -e "\n_ cleaning up staging directory..."
rm -r "$staging_dir"
echo "* Done"

echo -e "\n========================================="
echo "  Bootstrap complete: ${_ws}"
echo "  Workspace ID: ${_workspace_id}"
echo "========================================="
