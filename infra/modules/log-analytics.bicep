@description('Name of the Log Analytics workspace')
param name string

@description('Location for the resource')
param location string

@description('Data retention in days')
param retentionInDays int = 30

resource workspace 'Microsoft.OperationalInsights/workspaces@2025-07-01' = {
  name: name
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
  }
}

output id string = workspace.id
output customerId string = workspace.properties.customerId

#disable-next-line outputs-should-not-contain-secrets
output sharedKey string = workspace.listKeys().primarySharedKey
