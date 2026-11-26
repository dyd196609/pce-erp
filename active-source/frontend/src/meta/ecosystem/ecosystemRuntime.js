import { getPluginRegistry } from './pluginSDK.js'
import { getInstalledModules, listMarketplaceModules } from './marketplaceEngine.js'
import { getRevenueDistribution } from './revenueSharingEngine.js'
import { getSandboxLog } from './sandboxRuntime.js'
import { getDeveloperSDKSnapshot } from './sdk/developerSDK.js'
import { getPluginRuntimeSnapshot } from './runtime/pluginRuntimeEngine.js'
import { getPluginDistributionSnapshot } from './market/distributionEngine.js'
import { getRevenueSharingSnapshot } from './economy/revenueSharingEngine.js'

export function runEcosystemRuntime(context = {}) {
  const tenantId = context.tenantId || 'demo_company'
  const published = listMarketplaceModules()
  const installed = getInstalledModules(tenantId)
  const plugins = getPluginRegistry()
  const revenue = getRevenueDistribution()
  const sandboxEvents = getSandboxLog()
  const adoptionRate = published.length === 0 ? 0 : installed.length / published.length
  const developerActivity = plugins.reduce((map, plugin) => {
    map[plugin.developerId] = (map[plugin.developerId] || 0) + 1
    return map
  }, {})

  return {
    mode: 'V20_PLATFORM_ECOSYSTEM_OS',
    ecosystemMode: 'ON',
    pluginSystem: 'ACTIVE',
    sandboxMode: 'ENABLED',
    marketplaceMode: 'ACTIVE',
    revenueSharing: 'ACTIVE',
    marketplace: 'ENABLED',
    sandboxRuntime: 'ENABLED',
    tenantId,
    plugins,
    marketplaceModules: published,
    installedModules: installed,
    sandboxEvents,
    revenue,
    developerSDK: getDeveloperSDKSnapshot(),
    pluginRuntime: getPluginRuntimeSnapshot(),
    distribution: getPluginDistributionSnapshot(tenantId),
    revenueSharingSnapshot: getRevenueSharingSnapshot(),
    developerActivity,
    metrics: {
      ecosystemGrowthIndex: Math.min(100, plugins.length * 20 + installed.length * 10 + revenue.events * 5),
      pluginAdoptionRate: adoptionRate,
      marketplaceRevenue: revenue.totalRevenue,
      developerActivityHeatmap: Object.keys(developerActivity).length,
    },
  }
}
