// Veille LDA : App Service Linux + Key Vault (access policies) + Azure SQL (Entra ID uniquement).
// Aucune affectation de role Azure (RBAC) : acces Key Vault par strategies d'acces,
// acces SQL par utilisateur de base de donnees contenu (voir deploy.ps1).

@description('Region des ressources (par defaut celle du groupe de ressources).')
param location string = resourceGroup().location

@description('Prefixe des noms de ressources.')
param prefix string = 'lda-veille'

@description('UPN de l\'administrateur Entra ID du serveur SQL (le compte qui deploie).')
param sqlAdminLogin string

@description('Object ID Entra ID de cet administrateur (acces SQL + gestion des secrets).')
param adminObjectId string

@description('Nom de l\'App Service -> https://<nom>.azurewebsites.net (unique au niveau mondial).')
param webAppName string = 'lda-veille'

var suffix = uniqueString(resourceGroup().id)
var tenantId = subscription().tenantId
var keyVaultName = take('kv-ldaveille-${suffix}', 24)
var sqlServerName = 'sql-${prefix}-${suffix}'
var sqlDatabaseName = 'veille'

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'asp-${prefix}'
  location: location
  kind: 'linux'
  sku: { name: 'B1' } // Always On requis pour la collecte programmee de 7 h et 19 h
  properties: { reserved: true }
}

resource webApp 'Microsoft.Web/sites@2024-04-01' = {
  name: webAppName
  location: location
  kind: 'app,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: true
      webSocketsEnabled: true // Streamlit communique par WebSocket
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appCommandLine: 'python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0 --server.headless true'
      appSettings: [
        // Seule configuration de l'app : l'URL (non secrete) du coffre.
        { name: 'KEY_VAULT_URL', value: 'https://${keyVaultName}${environment().suffixes.keyvaultDns}/' }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'WEBSITES_PORT', value: '8000' }
        { name: 'TZ', value: 'Africa/Casablanca' }
      ]
    }
  }
}

// Le profil de publication (GitHub Actions) repose sur l'authentification de base SCM.
resource scmPolicy 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2024-04-01' = {
  parent: webApp
  name: 'scm'
  properties: { allow: true }
}

resource ftpPolicy 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2024-04-01' = {
  parent: webApp
  name: 'ftp'
  properties: { allow: false }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    tenantId: tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: false
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    accessPolicies: [
      {
        tenantId: tenantId
        objectId: webApp.identity.principalId
        permissions: { secrets: [ 'get', 'list' ] }
      }
      {
        tenantId: tenantId
        objectId: adminObjectId
        permissions: { secrets: [ 'get', 'list', 'set', 'delete', 'recover' ] }
      }
    ]
  }
}

resource sqlServer 'Microsoft.Sql/servers@2023-08-01' = {
  name: sqlServerName
  location: location
  properties: {
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    administrators: {
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true // aucun login SQL / mot de passe
      principalType: 'User'
      login: sqlAdminLogin
      sid: adminObjectId
      tenantId: tenantId
    }
  }
}

resource sqlAllowAzure 'Microsoft.Sql/servers/firewallRules@2023-08-01' = {
  parent: sqlServer
  name: 'AllowAllWindowsAzureIps'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-08-01' = {
  parent: sqlServer
  name: sqlDatabaseName
  location: location
  sku: { name: 'Basic', tier: 'Basic' }
}

resource secretSqlServer 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'SQL-SERVER'
  properties: { value: sqlServer.properties.fullyQualifiedDomainName }
}

resource secretSqlDatabase 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'SQL-DATABASE'
  properties: { value: sqlDatabaseName }
}

output webAppName string = webApp.name
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output keyVaultName string = keyVault.name
output sqlServerName string = sqlServer.name
output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output sqlDatabaseName string = sqlDatabaseName
