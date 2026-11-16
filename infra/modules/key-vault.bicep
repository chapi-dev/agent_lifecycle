param location string
param keyVaultName string
param tags object

@secure()
param healthopsDemoToken string

resource keyVault 'Microsoft.KeyVault/vaults@2026-05-15' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource demoTokenSecret 'Microsoft.KeyVault/vaults/secrets@2026-05-15' = {
  parent: keyVault
  name: 'demo-token'
  tags: tags
  properties: {
    value: healthopsDemoToken
  }
}

output keyVaultName string = keyVault.name
output keyVaultId string = keyVault.id
