targetScope = 'subscription'

@minLength(1)
@maxLength(64)
param environmentName string

@minLength(1)
param location string

param sessionId string
param deployedBy string
param createdAt string
param deployerObjectId string

@secure()
param healthopsDemoToken string = newGuid()

@minLength(1)
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

var tags = {
  'app-onboard-skill': 'true'
  'app-onboard-session-id': sessionId
  'created-at': createdAt
  environment: environmentName
  'deployed-by': deployedBy
}

var resourceGroupName = 'rg-healthops-dev-4c53'
var environmentResourceName = 'cae-healthops-dev-4c53'
var containerAppName = 'ca-healthops-dev-4c53'
var registryName = 'crhealthopsdev4c53'
var logAnalyticsName = 'log-healthops-dev-4c53'
var appInsightsName = 'appi-healthops-dev-4c53'
var keyVaultName = 'kv-healthops-dev-4c53'

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module logAnalytics './modules/log-analytics.bicep' = {
  name: 'log-analytics'
  scope: rg
  params: {
    location: location
    workspaceName: logAnalyticsName
    tags: tags
  }
}

module appInsights './modules/application-insights.bicep' = {
  name: 'application-insights'
  scope: rg
  params: {
    location: location
    componentName: appInsightsName
    workspaceResourceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}

module registry './modules/container-registry.bicep' = {
  name: 'container-registry'
  scope: rg
  params: {
    location: location
    registryName: registryName
    tags: tags
  }
}

module keyVault './modules/key-vault.bicep' = {
  name: 'key-vault'
  scope: rg
  params: {
    location: location
    keyVaultName: keyVaultName
    healthopsDemoToken: healthopsDemoToken
    tags: tags
  }
}

module containerEnvironment './modules/container-app-environment.bicep' = {
  name: 'container-app-environment'
  scope: rg
  params: {
    location: location
    environmentName: environmentResourceName
    workspaceName: logAnalyticsName
    workspaceCustomerId: logAnalytics.outputs.customerId
    tags: tags
  }
}

module containerApp './modules/container-app.bicep' = {
  name: 'container-app'
  scope: rg
  params: {
    location: location
    containerAppName: containerAppName
    managedEnvironmentId: containerEnvironment.outputs.environmentId
    containerImage: containerImage
    registryLoginServer: registry.outputs.loginServer
    healthopsDemoToken: healthopsDemoToken
    appPort: 8765
    healthProbePath: '/healthz'
    modelEndpoint: 'https://cog-3wobsg75sq6ic.cognitiveservices.azure.com'
    modelDeployment: 'gpt-5.4-mini'
    tags: tags
  }
}

module roleAssignments './modules/role-assignments.bicep' = {
  name: 'role-assignments'
  scope: rg
  params: {
    appPrincipalId: containerApp.outputs.principalId
    deployerObjectId: deployerObjectId
    keyVaultName: keyVaultName
    registryName: registryName
  }
}

module modelRoleAssignment './modules/model-role-assignment.bicep' = {
  name: 'model-role-assignment'
  scope: resourceGroup('rg-agentic-spec-model')
  params: {
    appPrincipalId: containerApp.outputs.principalId
    modelAccountName: 'cog-3wobsg75sq6ic'
  }
}
