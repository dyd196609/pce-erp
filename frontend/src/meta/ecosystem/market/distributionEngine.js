import {
  getInstalledModules,
  getModuleVersions,
  installModule,
  publishModule,
  uninstallModule,
} from '../marketplaceEngine.js'

const pluginDistributionHistory = []

function pluginToModule(plugin = {}) {
  const pluginId = plugin.id || plugin.pluginId || plugin.schema?.api?.module || plugin.schema?.name

  return {
    key: plugin.module?.key || pluginId,
    name: plugin.name || plugin.schema?.meta?.title || pluginId,
    route: plugin.route || plugin.module?.route || `/plugins/${pluginId}`,
    developerId: plugin.developerId || 'unknownDeveloper',
    price: plugin.price || plugin.marketplace?.price || 0,
    version: plugin.version || plugin.marketplace?.version || '1.0.0',
    schema: plugin.schema,
  }
}

export function publishPlugin(plugin = {}) {
  const result = publishModule(pluginToModule(plugin), {
    developerId: plugin.developerId,
    version: plugin.version || plugin.marketplace?.version || '1.0.0',
    price: plugin.price || plugin.marketplace?.price || 0,
  })

  pluginDistributionHistory.unshift({
    type: 'PUBLISH',
    pluginId: result.module?.pluginId || result.module?.key,
    status: result.status,
    timestamp: Date.now(),
  })

  return result
}

export function installPlugin(pluginId, tenantId = 'demo_company') {
  const result = installModule(pluginId, tenantId)
  pluginDistributionHistory.unshift({
    type: 'INSTALL',
    pluginId,
    tenantId,
    status: result.status,
    timestamp: Date.now(),
  })
  return result
}

export function uninstallPlugin(pluginId, tenantId = 'demo_company') {
  const result = uninstallModule(pluginId, tenantId)
  pluginDistributionHistory.unshift({
    type: 'UNINSTALL',
    pluginId,
    tenantId,
    status: result.status,
    timestamp: Date.now(),
  })
  return result
}

export function getPluginVersion(pluginId) {
  return getModuleVersions(pluginId)
}

export function getPluginDistributionSnapshot(tenantId = 'demo_company') {
  return {
    marketplaceMode: 'ACTIVE',
    distribution: 'ACTIVE',
    installed: getInstalledModules(tenantId),
    history: [...pluginDistributionHistory],
  }
}
