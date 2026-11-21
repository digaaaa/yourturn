#!/usr/bin/env bash
set -euo pipefail

: "${AZURE_PREFIX:?Set AZURE_PREFIX to the approved IE resource prefix}"
: "${CHORES_DATABASE_URL:?Configure the Chores connection URL as a GitHub secret}"
: "${SUPPLIES_DATABASE_URL:?Configure the Supplies connection URL as a GitHub secret}"

group="rg-$AZURE_PREFIX"
storage="${AZURE_PREFIX//-/}ui"
registry="ghcr.io/${GITHUB_REPOSITORY,,}"

app_url() {
    local fqdn
    fqdn=$(az containerapp show --name "$AZURE_PREFIX-$1" --resource-group "$group" \
        --query properties.configuration.ingress.fqdn --output tsv)
    [[ -n "$fqdn" && "$fqdn" != "None" ]]
    printf 'https://%s\n' "$fqdn"
}

chores_url=$(app_url chores)
supplies_url=$(app_url supplies)
ui_url=$(az storage account show --name "$storage" --resource-group "$group" \
    --query primaryEndpoints.web --output tsv)
[[ "$ui_url" == https://* ]]
ui_origin="${ui_url%/}"

update_app() {
    local domain=$1 database_url=$2 peer_setting=$3
    az containerapp secret set --name "$AZURE_PREFIX-$domain" --resource-group "$group" \
        --secrets "database-url=$database_url" --output none
    az containerapp ingress update --name "$AZURE_PREFIX-$domain" --resource-group "$group" \
        --target-port 8000 --allow-insecure false --output none
    az containerapp update --name "$AZURE_PREFIX-$domain" --resource-group "$group" \
        --image "$registry-$domain:$GITHUB_SHA" --min-replicas 0 --max-replicas 1 \
        --set-env-vars "DATABASE_URL=secretref:database-url" "APP_VERSION=$GITHUB_SHA" \
            "UI_ORIGIN=$ui_origin" "$peer_setting" --output none
}

update_app chores "$CHORES_DATABASE_URL" "SUPPLIES_SERVICE_URL=$supplies_url"
update_app supplies "$SUPPLIES_DATABASE_URL" "CHORES_SERVICE_URL=$chores_url"

wait_for_app() {
    local domain=$1 base_url=$2
    for attempt in {1..30}; do
        if curl --fail --silent --max-time 15 "$base_url/health" |
            python -c 'import json, sys; d = json.load(sys.stdin); sys.exit(d.get("status") != "ok" or d.get("db") != "ok" or d.get("version") != sys.argv[1])' "$GITHUB_SHA" 2>/dev/null; then
            printf '%s is healthy on %s\n' "$domain" "$GITHUB_SHA"
            return
        fi
        sleep 5
    done
    printf '%s did not become healthy on the expected commit\n' "$domain" >&2
    return 1
}

wait_for_app chores "$chores_url"
wait_for_app supplies "$supplies_url"

site=$(mktemp -d)
trap 'rm -rf -- "$site"' EXIT
cp -R ui/. "$site/"
python - "$chores_url" "$supplies_url" > "$site/config.js" <<'PY'
import json
import sys

print("window.yourTurnConfig = " + json.dumps({"chores": sys.argv[1], "supplies": sys.argv[2]}) + ";")
PY
az storage blob upload-batch --account-name "$storage" --destination '$web' \
    --source "$site" --auth-mode login --overwrite true --content-cache-control no-cache --output none
curl --fail --silent --show-error --max-time 20 "$ui_origin/" > /dev/null
remote_config=$(curl --fail --silent --show-error --max-time 20 "$ui_origin/config.js?$GITHUB_SHA")
[[ "$remote_config" == *"$chores_url"* && "$remote_config" == *"$supplies_url"* ]]

for base_url in "$chores_url" "$supplies_url"; do
    curl --fail --silent --show-error --max-time 20 -D - -o /dev/null \
        -H "Origin: $ui_origin" "$base_url/health" |
        tr -d '\r' | grep -Fi "access-control-allow-origin: $ui_origin" > /dev/null
done

printf 'UI: %s\nChores: %s\nSupplies: %s\n' "$ui_origin" "$chores_url" "$supplies_url"
