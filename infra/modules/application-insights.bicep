param location string
param componentName string
param workspaceResourceId string
param tags object

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: componentName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    IngestionMode: 'LogAnalytics'
    WorkspaceResourceId: workspaceResourceId
  }
}

output componentId string = applicationInsights.id
