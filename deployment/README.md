# Azure initial setup

Use Azure CLI in Bash with your personal Azure for Students subscription. Before approving any resources, select the subscription and read its region policy:

```bash
az login
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az account show --query '{name:name,id:id,state:state}' --output table
az policy assignment list --scope "/subscriptions/$AZURE_SUBSCRIPTION_ID" \
  --query "[?displayName=='Allowed resource deployment regions'].parameters" --output json
```

Confirm the output identifies your enabled personal subscription. Choose an allowed region and confirm SQL free-offer availability there. If SQL needs a different allowed region, set `AZURE_SQL_REGION` and include that region in the approval. The script does not switch regions or try a paid database automatically.

1. Set `AZURE_SUBSCRIPTION_ID`, `AZURE_REGION`, `AZURE_PREFIX` (IE username with dots replaced by hyphens), `GITHUB_REPOSITORY` (owner/repository), `GITHUB_NUMERIC_REPOSITORY` (owner@ID/repository@ID), and `SQL_ADMIN_USER`. Get the GitHub IDs with `gh api "repos/$GITHUB_REPOSITORY" --jq '{owner_id: .owner.id, repository_id: .id}'`. Verify both Reader identities in the selected tenant and set `ALBERTO_OBJECT_ID` for `amartini@faculty.ie.edu` and `SERRA_OBJECT_ID` for `bserra@faculty.ie.edu`. Read `SQL_ADMIN_PASSWORD` into the local environment with a hidden prompt.
2. Run `AZURE_PROVISION_APPROVED=yes bash scripts/bootstrap-azure.sh` only after approval. It checks the selected subscription before registering providers or creating resources. Once the SQL server is available, Azure Resource Manager validates both database requests with the SQL provider before the script creates either database. The script stops if validation fails and verifies the SKU, free offer, and exhaustion behavior after creation. Azure sets the auto-pause delay and maximum size.
3. For the initial SQL setup, temporarily allow only your approved public IP on the SQL server firewall. Supply distinct `CHORES_DB_PASSWORD` and `SUPPLIES_DB_PASSWORD` values through hidden prompts. In a Python 3.12 environment with `pymssql==2.3.2`, run `python scripts/bootstrap-azure-sql.py`. Remove the temporary IP rule after SQL setup and verification. The service users have only data and migration permissions in their respective databases.
4. In GitHub Actions secrets, configure `AZURE_CLIENT_ID` from the deployment identity, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `CHORES_DATABASE_URL` and `SUPPLIES_DATABASE_URL`. Use a connection URL of the form `mssql://USER:PASSWORD@SERVER.database.windows.net:1433/DATABASE` and percent-encode credentials if needed. The two app logins are `yourturn_chores_app` and `yourturn_supplies_app`. Keep the administrator password local.
5. In repository Actions variables, set `AZURE_PREFIX`. The first successful main workflow publishes two GHCR packages. Set those packages to public visibility to allow anonymous image pulls from Container Apps. If a package already exists, grant this repository Actions access to it.
6. After setup and explicit deployment approval, set `AZURE_DEPLOY_ENABLED=true`. A successful push to `main` then deploys that commit's images and frontend. The run must print both healthy SHAs and the public URLs. For the migration exercise, deploy and populate the baseline before enabling the new schema migration on main.

The deployment identity trusts `refs/heads/main` through both OIDC subject formats. It has Contributor on the assignment resource group and Storage Blob Data Contributor on the one UI account. Both professors receive Reader on the assignment group. The app database connections are injected as Container Apps secrets.

See [Microsoft's Azure SQL free offer](https://learn.microsoft.com/en-us/azure/azure-sql/database/free-offer), [managed identity federation](https://learn.microsoft.com/en-us/azure/active-directory/develop/workload-identity-federation-create-trust-user-assigned-managed-identity), and [static website hosting](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-static-website-how-to) for the service configuration.
