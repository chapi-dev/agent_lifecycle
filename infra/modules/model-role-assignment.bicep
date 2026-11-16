param appPrincipalId string
param modelAccountName string

var cognitiveServicesOpenAIUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource modelAccount 'Microsoft.CognitiveServices/accounts@2026-11-01' existing = {
  name: modelAccountName
}

resource modelInferenceRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(modelAccount.id, appPrincipalId, cognitiveServicesOpenAIUserRoleId)
  scope: modelAccount
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      cognitiveServicesOpenAIUserRoleId
    )
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
  }
}
