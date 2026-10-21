# Deploie l'infrastructure Azure de Veille LDA et configure le deploiement GitHub.
# Prerequis : az login (compte administrateur), gh auth login, sqlcmd (winget install Microsoft.Sqlcmd, ou -Sqlcmd <chemin>).
# Relancable sans risque : toutes les etapes sont idempotentes.
param(
    [string]$ResourceGroup = 'RG-LDA-Veille',
    [string]$GitHubRepo = 'LesDomainesAgricoles/LDA-Veille',
    [string]$Sqlcmd = 'sqlcmd'
)
$ErrorActionPreference = 'Stop'
function Invoke-Az { $out = az @args; if ($LASTEXITCODE) { throw "az $args a echoue" }; $out }

Write-Host '1/5  Identite de l''administrateur'
$me = Invoke-Az ad signed-in-user show --query '{id:id, upn:userPrincipalName}' -o json | ConvertFrom-Json

Write-Host '2/5  Deploiement Bicep (App Service, Key Vault, Azure SQL)'
$out = Invoke-Az deployment group create -g $ResourceGroup -n lda-veille `
    --template-file "$PSScriptRoot/main.bicep" `
    --parameters sqlAdminLogin=$($me.upn) adminObjectId=$($me.id) `
    --query properties.outputs -o json | ConvertFrom-Json
$webApp = $out.webAppName.value
$sqlServer = $out.sqlServerName.value

Write-Host '3/5  Utilisateur SQL Entra ID pour l''identite managee de l''app'
$ip = (Invoke-RestMethod -Uri 'https://api.ipify.org')
Invoke-Az sql server firewall-rule create -g $ResourceGroup -s $sqlServer -n deploy-client `
    --start-ip-address $ip --end-ip-address $ip -o none
try {
    $tsql = @"
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'$webApp')
    CREATE USER [$webApp] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [$webApp];
ALTER ROLE db_datawriter ADD MEMBER [$webApp];
IF OBJECT_ID('dbo.ScoutSnapshots', 'U') IS NULL
CREATE TABLE dbo.ScoutSnapshots (
    Slot NVARCHAR(64) NOT NULL PRIMARY KEY,
    CollectedAt DATETIME2 NULL,
    Payload VARBINARY(MAX) NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
"@
    & $Sqlcmd -S "tcp:$($out.sqlServerFqdn.value),1433" -d $out.sqlDatabaseName.value `
        --authentication-method ActiveDirectoryAzCli -b -Q $tsql
    if ($LASTEXITCODE) { throw 'sqlcmd a echoue' }
}
finally {
    Invoke-Az sql server firewall-rule delete -g $ResourceGroup -s $sqlServer -n deploy-client -o none
}

Write-Host '4/5  Profil de publication -> GitHub'
$publishProfile = Invoke-Az webapp deployment list-publishing-profiles -g $ResourceGroup -n $webApp --xml
$publishProfile | gh secret set AZURE_WEBAPP_PUBLISH_PROFILE --repo $GitHubRepo
if ($LASTEXITCODE) { throw 'gh secret set a echoue' }
gh variable set AZURE_WEBAPP_NAME --repo $GitHubRepo --body $webApp
if ($LASTEXITCODE) { throw 'gh variable set a echoue' }

Write-Host '5/5  Termine'
Write-Host "  Application : $($out.webAppUrl.value)"
Write-Host "  Key Vault   : $($out.keyVaultName.value)"
Write-Host "  Cles API    : .\infra\set-api-keys.ps1 -KeyVault $($out.keyVaultName.value)"
