targetScope = 'resourceGroup'

@description('Azure region for the App Service plan and web app')
param location string = 'westcentralus'

@description('Globally unique App Service web app name')
param appName string

@description('Name of the Linux Free App Service plan')
param servicePlanName string = '${appName}-f1'

@description('Published CoastCast container image')
param containerImage string

@description('Name of the existing Azure Container Registry')
param registryName string

@description('Name of the existing user-assigned identity used for ACR pulls')
param pullIdentityName string

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: pullIdentityName
}

resource servicePlan 'Microsoft.Web/serverfarms@2024-11-01' = {
  name: servicePlanName
  location: location
  kind: 'linux'
  sku: {
    name: 'U13'
    tier: 'LinuxFree'
    size: 'U13'
    family: 'U'
    capacity: 1
  }
  properties: {
    reserved: true
  }
}

resource app 'Microsoft.Web/sites@2024-11-01' = {
  name: appName
  location: location
  kind: 'app,linux,container'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${pullIdentity.id}': {}
    }
  }
  properties: {
    serverFarmId: servicePlan.id
    httpsOnly: true
    clientAffinityEnabled: false
    publicNetworkAccess: 'Enabled'
    siteConfig: {
      linuxFxVersion: 'DOCKER|${containerImage}'
      acrUseManagedIdentityCreds: true
      acrUserManagedIdentityID: pullIdentity.properties.clientId
      alwaysOn: false
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      http20Enabled: true
      appSettings: [
        { name: 'DOCKER_REGISTRY_SERVER_URL', value: 'https://${registry.properties.loginServer}' }
        { name: 'WEBSITES_PORT', value: '8501' }
        { name: 'WEBSITES_CONTAINER_START_TIME_LIMIT', value: '1800' }
        { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }
        { name: 'COASTCAST_CONFIG', value: 'configs/base.yml' }
        { name: 'COASTCAST_MODEL_DIR', value: 'artifacts/runtime' }
      ]
    }
  }
}

output applicationUrl string = 'https://${app.properties.defaultHostName}'
