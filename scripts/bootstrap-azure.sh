#!/usr/bin/env bash
# One-time initial setup. Use a verified Azure for Students subscription.
set -euo pipefail

: "${AZURE_PROVISION_APPROVED:?Set to yes only after approving Azure provisioning}"
[[ "$AZURE_PROVISION_APPROVED" == yes ]]
: "${AZURE_SUBSCRIPTION_ID:?Select the intended Azure for Students subscription ID}"
: "${AZURE_PREFIX:?Set the IE username prefix with dots replaced by hyphens}"
: "${AZURE_REGION:?Set an approved subscription region}"
: "${AZURE_SQL_REGION:=$AZURE_REGION}"
: "${GITHUB_REPOSITORY:?Set the exact GitHub owner/repository}"
: "${GITHUB_NUMERIC_REPOSITORY:?Set owner@ID/repo@ID for the numeric OIDC subject}"
: "${ALBERTO_OBJECT_ID:?Set the verified object ID for amartini@faculty.ie.edu}"
: "${SERRA_OBJECT_ID:?Set the verified object ID for bserra@faculty.ie.edu}"
: "${SQL_ADMIN_USER:?Set the SQL administrator user}"
: "${SQL_ADMIN_PASSWORD:?Provide the SQL administrator password securely}"

[[ "$AZURE_PREFIX" =~ ^[a-z][a-z0-9-]*[a-z0-9]$ ]]
[[ "$ALBERTO_OBJECT_ID" =~ ^[0-9a-fA-F-]{36}$ && "$SERRA_OBJECT_ID" =~ ^[0-9a-fA-F-]{36}$ ]]
[[ "$GITHUB_NUMERIC_REPOSITORY" =~ ^[^/@]+@[0-9]+/[^/@]+@[0-9]+$ ]]
group="rg-$AZURE_PREFIX"
server="$AZURE_PREFIX-sql"
environment="$AZURE_PREFIX-env"
identity="$AZURE_PREFIX-github"
storage="${AZURE_PREFIX//-/}ui"
[[ ${#storage} -le 24 && ${#AZURE_PREFIX} -le 23 ]]

az account set --subscription "$AZURE_SUBSCRIPTION_ID"
selected=$(az account show --query '[id,name,state]' --output json)
SELECTED_SUBSCRIPTION_JSON="$selected" python3 - "$AZURE_SUBSCRIPTION_ID" <<'PY'
import json
import os
import sys

subscription, name, state = json.loads(os.environ["SELECTED_SUBSCRIPTION_JSON"])
if subscription != sys.argv[1] or name != "Azure for Students" or state != "Enabled":
    raise SystemExit("Expected the approved, enabled personal Azure for Students subscription.")
print(f"Verified subscription: {name} ({subscription})")
PY

for provider in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
    az provider register --namespace "$provider" --wait --output none
done
az group create --name "$group" --location "$AZURE_REGION" --output none
scope=$(az group show --name "$group" --query id --output tsv)

if ! az sql server show --name "$server" --resource-group "$group" --output none 2>/dev/null; then
    az sql server create --name "$server" --resource-group "$group" --location "$AZURE_SQL_REGION" \
        --admin-user "$SQL_ADMIN_USER" --admin-password "$SQL_ADMIN_PASSWORD" \
        --minimal-tls-version 1.2 --output none
fi
[[ $(az sql server show --name "$server" --resource-group "$group" --query location --output tsv) == "$AZURE_SQL_REGION" ]]

database_names=()
for service in chores supplies; do
    database="$AZURE_PREFIX-$service-db"
    if ! az sql db show --resource-group "$group" --server "$server" --name "$database" --output none 2>/dev/null; then
        database_names+=("$database")
    fi
done
if (( ${#database_names[@]} )); then
    root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
    parameters=$(mktemp)
    trap 'rm -f -- "$parameters"' EXIT
    python3 - "$server" "$AZURE_SQL_REGION" "${database_names[@]}" > "$parameters" <<'PY'
import json
import sys

server, location, *names = sys.argv[1:]
print(json.dumps({"parameters": {key: {"value": value} for key, value in
                                dict(server=server, location=location, databaseNames=names).items()}}))
PY
    if command -v cygpath >/dev/null; then
        template_path=$(cygpath -m "$root/deployment/sql-free-preflight.json")
        params_path=$(cygpath -m "$parameters")
    else
        template_path="$root/deployment/sql-free-preflight.json"
        params_path="$parameters"
    fi
    az deployment group validate --resource-group "$group" --validation-level Provider \
        --template-file "$template_path" --parameters "@$params_path" \
        --output none
    printf '%s\n' 'Azure provider validation accepted the requested free-offer database configuration.'
fi
az sql server firewall-rule create --resource-group "$group" --server "$server" \
    --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 --output none

for service in chores supplies; do
    database="$AZURE_PREFIX-$service-db"
    if ! az sql db show --resource-group "$group" --server "$server" --name "$database" --output none 2>/dev/null; then
        az sql db create --resource-group "$group" --server "$server" --name "$database" \
            --edition GeneralPurpose --family Gen5 --compute-model Serverless \
            --min-capacity 0.5 --capacity 1 \
            --backup-storage-redundancy Local --use-free-limit true \
            --free-limit-exhaustion-behavior AutoPause --output none
    fi
    actual=$(az sql db show --resource-group "$group" --server "$server" --name "$database" \
        --query '{free:useFreeLimit,whenFull:freeLimitExhaustionBehavior,tier:sku.tier,sku:sku.name,family:sku.family,max:sku.capacity,min:minCapacity,pause:autoPauseDelay,backup:requestedBackupStorageRedundancy,size:maxSizeBytes}' --output json)
    ACTUAL_SQL_JSON="$actual" python3 - "$database" <<'PY'
import json
import os
import sys

name, actual = sys.argv[1], json.loads(os.environ["ACTUAL_SQL_JSON"])
expected = dict(free=True, whenFull="AutoPause", tier="GeneralPurpose", family="Gen5",
                sku="GP_S_Gen5", max=1, min=0.5, backup="Local", size=32 * 1024**3)
if any(actual[key] != value for key, value in expected.items()):
    raise SystemExit(f"{name} differs from the requested free database settings: {actual}")
print(f"{name} matches the free-offer configuration; provider auto-pause is {actual['pause']} minutes.")
PY
done

if ! az storage account show --name "$storage" --resource-group "$group" --output none 2>/dev/null; then
    az storage account create --name "$storage" --resource-group "$group" --location "$AZURE_REGION" \
        --kind StorageV2 --sku Standard_LRS --https-only true --min-tls-version TLS1_2 --output none
fi
az storage account blob-service-properties update --account-name "$storage" --resource-group "$group" \
    --enable-static-website true --index-document index.html \
    --404-document index.html --output none
storage_scope=$(az storage account show --name "$storage" --resource-group "$group" --query id --output tsv)

if ! az identity show --name "$identity" --resource-group "$group" --output none 2>/dev/null; then
    az identity create --name "$identity" --resource-group "$group" --location "$AZURE_REGION" --output none
fi
principal=$(az identity show --name "$identity" --resource-group "$group" --query principalId --output tsv)
az identity federated-credential create --name github-main --identity-name "$identity" \
    --resource-group "$group" --issuer https://token.actions.githubusercontent.com \
    --subject "repo:$GITHUB_REPOSITORY:ref:refs/heads/main" --audiences api://AzureADTokenExchange --output none
az identity federated-credential create --name github-main-numeric --identity-name "$identity" \
    --resource-group "$group" --issuer https://token.actions.githubusercontent.com \
    --subject "repo:$GITHUB_NUMERIC_REPOSITORY:ref:refs/heads/main" --audiences api://AzureADTokenExchange --output none
az role assignment create --assignee-object-id "$principal" --assignee-principal-type ServicePrincipal \
    --role Contributor --scope "$scope" --output none
az role assignment create --assignee-object-id "$principal" --assignee-principal-type ServicePrincipal \
    --role 'Storage Blob Data Contributor' --scope "$storage_scope" --output none
for professor in "$ALBERTO_OBJECT_ID" "$SERRA_OBJECT_ID"; do
    az role assignment create --assignee-object-id "$professor" --assignee-principal-type User \
        --role Reader --scope "$scope" --output none
done

if ! az containerapp env show --name "$environment" --resource-group "$group" --output none 2>/dev/null; then
    az containerapp env create --name "$environment" --resource-group "$group" --location "$AZURE_REGION" \
        --logs-destination log-analytics --enable-workload-profiles false --output none
fi
for service in chores supplies; do
    if ! az containerapp show --name "$AZURE_PREFIX-$service" --resource-group "$group" --output none 2>/dev/null; then
        az containerapp create --name "$AZURE_PREFIX-$service" --resource-group "$group" \
            --environment "$environment" --image mcr.microsoft.com/k8se/quickstart:latest \
            --ingress external --target-port 80 --transport auto --allow-insecure false \
            --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
            --revisions-mode single --output none
    fi
done

az storage account show --name "$storage" --resource-group "$group" --query primaryEndpoints.web --output tsv
