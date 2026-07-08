import { registerPlugin as registerLegacyPlugin } from '../pluginSDK.js'
import { sandboxDeploy } from '../sandbox/sandboxEngine.js'
import { publishPlugin } from '../market/distributionEngine.js'

function validate(schema = {}) {
  if (!schema.name && !schema.api?.module) {
    throw new Error('[Developer SDK] plugin.schema.name or plugin.schema.api.module is required')
  }

  if (!Array.isArray(schema?.ui?.list?.columns)) {
    throw new Error('[Developer SDK] plugin.schema.ui.list.columns is required')
  }

  return true
}

export function registerToMarketplace(plugin = {}) {
  return publishPlugin(plugin)
}

export function registerPlugin(plugin = {}) {
  validate(plugin.schema)
  const sandbox = sandboxDeploy(plugin)
  const registration = registerLegacyPlugin(plugin)
  const marketplace = registerToMarketplace({
    ...plugin,
    id: registration.id,
  })

  return {
    status: 'ACTIVE',
    sandbox: true,
    pluginSystem: 'ACTIVE',
    registration,
    sandboxDeployment: sandbox,
    marketplace,
  }
}

export function getDeveloperSDKSnapshot() {
  return {
    developerSDK: 'ACTIVE',
    pluginValidation: 'ENABLED',
    sandboxDeploy: 'ENABLED',
    marketplaceRegistration: 'ENABLED',
  }
}
