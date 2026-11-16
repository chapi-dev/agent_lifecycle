param location string
param containerAppName string
param managedEnvironmentId string
param registryLoginServer string
param appPort int
param healthProbePath string
param modelEndpoint string
param modelDeployment string
param tags object

@secure()
param healthopsDemoToken string

@minLength(1)
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

var isPlaceholder = containerImage == 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
var effectivePort = isPlaceholder ? 80 : appPort
var effectiveHealthPath = isPlaceholder ? '/' : healthProbePath

resource containerApp 'Microsoft.App/containerApps@2026-07-01' = {
  name: containerAppName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: managedEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: effectivePort
        allowInsecure: false
        transport: 'auto'
      }
      registries: isPlaceholder
        ? []
        : [
            {
              server: registryLoginServer
              identity: 'system'
            }
          ]
      secrets: isPlaceholder
        ? []
        : [
            {
              name: 'healthops-demo-token'
              value: healthopsDemoToken
            }
          ]
    }
    template: {
      containers: [
        {
          name: 'healthcare-agentops'
          image: containerImage
          env: concat(
            [
              {
                name: 'HEALTHOPS_IDENTITY'
                value: 'managed'
              }
              {
                name: 'HEALTHOPS_MODEL_ENDPOINT'
                value: modelEndpoint
              }
              {
                name: 'HEALTHOPS_MODEL_DEPLOYMENT'
                value: modelDeployment
              }
              {
                name: 'HOST'
                value: '0.0.0.0'
              }
              {
                name: 'PORT'
                value: string(effectivePort)
              }
            ],
            isPlaceholder
              ? []
              : [
                  {
                    name: 'HEALTHOPS_DEMO_TOKEN'
                    secretRef: 'healthops-demo-token'
                  }
                ]
          )
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          probes: [
            {
              type: 'Readiness'
              httpGet: {
                path: effectiveHealthPath
                port: effectivePort
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

output principalId string = containerApp.identity.principalId
output containerAppId string = containerApp.id
