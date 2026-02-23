@description('Name of the Service Bus namespace')
param name string

@description('Location for the resource')
param location string

@description('Principal ID for RBAC assignment')
param principalId string

resource namespace 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: name
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
}

resource topic 'Microsoft.ServiceBus/namespaces/topics@2024-01-01' = {
  parent: namespace
  name: 'pipeline-events'
  properties: {
    defaultMessageTimeToLive: 'PT1H'
    maxSizeInMegabytes: 1024
  }
}

resource subscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2024-01-01' = {
  parent: topic
  name: 'web-consumer'
  properties: {
    lockDuration: 'PT30S'
    maxDeliveryCount: 5
    defaultMessageTimeToLive: 'PT1H'
  }
}

// Azure Service Bus Data Sender role for the worker
resource senderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: namespace
  name: guid(namespace.id, principalId, '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39')
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39'
    )
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// Azure Service Bus Data Receiver role for the web
resource receiverRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: namespace
  name: guid(namespace.id, principalId, '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0')
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0'
    )
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output namespaceName string = namespace.name
output connectionString string = listKeys(
  '${namespace.id}/AuthorizationRules/RootManageSharedAccessKey',
  namespace.apiVersion
).primaryConnectionString
