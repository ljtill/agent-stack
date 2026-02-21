@description('Name of the Static Web App')
param name string

@description('Location for the resource')
param location string

resource staticWebApp 'Microsoft.Web/staticSites@2023-12-01' = {
  name: name
  location: location
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {}
}

output url string = 'https://${staticWebApp.properties.defaultHostname}'
