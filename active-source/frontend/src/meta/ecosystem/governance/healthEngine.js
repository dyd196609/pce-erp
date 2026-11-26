import { getExposedAPIs, getPluginRegistry } from '../pluginSDK.js'
import { getInstalledModules, listMarketplaceModules } from '../marketplaceEngine.js'
import { getSandboxLog } from '../sandboxRuntime.js'

function calculateStability() {
  const sandboxLog = getSandboxLog()
  if (sandboxLog.length === 0) return 100

  const blocked = sandboxLog.filter((item) => item.status === 'BLOCKED').length
  return Math.max(0, Math.round(100 - (blocked / sandboxLog.length) * 100))
}

function calculateUsage(tenantId = 'demo_company') {
  const published = listMarketplaceModules()
  const installed = getInstalledModules(tenantId)

  return published.length === 0 ? 0 : installed.length / published.length
}

function analyzeTenantStatus(tenantId = 'demo_company') {
  const installed = getInstalledModules(tenantId)

  return {
    tenantId,
    installedModules: installed.length,
    health: installed.length > 0 ? 'ACTIVE' : 'READY',
  }
}

function measureAPIHealth() {
  const apis = getExposedAPIs()
  const valid = apis.filter((item) => item.api?.list && item.api?.detail).length

  return {
    total: apis.length,
    valid,
    reliability: apis.length === 0 ? 1 : valid / apis.length,
  }
}

export function evaluateEcosystemHealth(context = {}) {
  const plugins = getPluginRegistry()

  return {
    mode: 'V21_ECOSYSTEM_HEALTH',
    pluginStability: calculateStability(),
    moduleUsageRate: calculateUsage(context.tenantId),
    tenantHealth: analyzeTenantStatus(context.tenantId),
    apiReliability: measureAPIHealth(),
    pluginCount: plugins.length,
  }
}
