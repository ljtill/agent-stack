@description('Name of the container app')
param name string

@description('Location for the resource')
param location string

@description('User-assigned managed identity resource ID')
param identityId string

@description('ACR login server')
param acrLoginServer string

@description('Container image tag')
param imageTag string

@description('App Configuration endpoint')
param appConfigEndpoint string

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${name}-env'
  location: location
  properties: {
    zoneRedundant: false
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: acrLoginServer
          identity: identityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'agent-stack'
          image: '${acrLoginServer}/agent-stack:${imageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'APP_CONFIG_ENDPOINT'
              value: appConfigEndpoint
            }
            {
              name: 'APP_ENV'
              value: 'production'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output url string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
