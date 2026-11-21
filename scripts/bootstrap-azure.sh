#!/usr/bin/env bash
# One-time initial setup. Use a verified Azure for Students subscription.
set -euo pipefail

: "${AZURE_PROVISION_APPROVED:?Set to yes only after approving Azure provisioning}"
[[ "$AZURE_PROVISION_APPROVED" == yes ]]
: "${AZURE_SUBSCRIPTION_ID:?Select the intended Azure for Students subscription ID}"
: "${AZURE_PREFIX:?Set the IE username prefix with dots replaced by hyphens}"
: "${AZURE_REGION:?Set an approved subscription region}"
: "${GITHUB_REPOSITORY:?Set the exact GitHub owner/repository}"
: "${PROFESSOR_OBJECT_ID:?Set the confirmed Reader principal object ID}"
: "${SQL_ADMIN_USER:?Set the SQL administrator user}"
: "${SQL_ADMIN_PASSWORD:?Provide the SQL administrator password securely}"

[[ "$AZURE_PREFIX" =~ ^[a-z][a-z0-9-]*[a-z0-9]$ ]]
[[ "$PROFESSOR_OBJECT_ID" =~ ^[0-9a-fA-F-]{36}$ ]]
group="rg-$AZURE_PREFIX"
server="$AZURE_PREFIX-sql"
environment="$AZURE_PREFIX-env"
identity="$AZURE_PREFIX-github"
storage="${AZURE_PREFIX//-/}ui"
[[ ${#storage} -le 24 && ${#AZURE_PREFIX} -le 23 ]]

az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az account show --query '{subscription:name,tenant:tenantId}' --output table
az group create --name "$group" --location "$AZURE_REGION" --output none
scope=$(az group show --name "$group" --query id --output tsv)

if ! az sql server show --name "$server" --resource-group "$group" --output none 2>/dev/null; then
    az sql server create --name "$server" --resource-group "$group" --location "$AZURE_REGION" \
        --admin-user "$SQL_ADMIN_USER" --admin-password "$SQL_ADMIN_PASSWORD" \
        --minimal-tls-version 1.2 --output none
fi
az sql server firewall-rule create --resource-group "$group" --server "$server" \
    --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 --output none

for service in chores supplies; do
    database="$AZURE_PREFIX-$service-db"
    if ! az sql db show --resource-group "$group" --server "$server" --name "$database" --output none 2>/dev/null; then
        az sql db create --resource-group "$group" --server "$server" --name "$database" \
            --edition GeneralPurpose --family Gen5 --compute-model Serverless \
            --min-capacity 0.5 --capacity 1 --auto-pause-delay 60 --max-size 32GB \
            --backup-storage-redundancy Local --use-free-limit true \
            --free-limit-exhaustion-behavior AutoPause --output none
    fi
    actual=$(az sql db show --resource-group "$group" --server "$server" --name "$database" \
        --query '{free:useFreeLimit,whenFull:freeLimitExhaustionBehavior,tier:sku.tier,family:sku.family,max:sku.capacity,min:minCapacity,pause:autoPauseDelay,backup:requestedBackupStorageRedundancy,size:maxSizeBytes}' --output json)
    python3 - "$database" "$actual" <<'PY'
import json
import sys

name, actual = sys.argv[1], json.loads(sys.argv[2])
expected = dict(free=True, whenFull="AutoPause", tier="GeneralPurpose", family="Gen5",
                max=1, min=0.5, pause=60, backup="Local", size=32 * 1024**3)
if actual != expected:
    raise SystemExit(f"{name} differs from the requested free database settings: {actual}")
print(f"{name} matches the requested free-offer configuration.")
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
az role assignment create --assignee-object-id "$principal" --assignee-principal-type ServicePrincipal \
    --role Contributor --scope "$scope" --output none
az role assignment create --assignee-object-id "$principal" --assignee-principal-type ServicePrincipal \
    --role 'Storage Blob Data Contributor' --scope "$storage_scope" --output none
az role assignment create --assignee-object-id "$PROFESSOR_OBJECT_ID" --assignee-principal-type User \
    --role Reader --scope "$scope" --output none

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
