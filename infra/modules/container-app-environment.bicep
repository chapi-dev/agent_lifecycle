param location string
param environmentName string
param workspaceName string
param workspaceCustomerId string
param tags object

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2026-03-01' existing = {
  name: workspaceName
}

var workspaceSharedKey = logAnalyticsWorkspace.listKeys().primarySharedKey

resource managedEnvironment 'Microsoft.App/managedEnvironments@2026-07-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspaceCustomerId
        sharedKey: workspaceSharedKey
      }
    }
  }
}

output environmentId string = managedEnvironment.id
