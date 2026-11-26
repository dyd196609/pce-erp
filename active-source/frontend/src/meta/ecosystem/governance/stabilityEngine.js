import { getPluginRegistry } from '../pluginSDK.js'
import { listMarketplaceModules } from '../marketplaceEngine.js'
import { getSandboxLog } from '../sandboxRuntime.js'

export function detectEcosystemOverload() {
  const plugins = getPluginRegistry()
  const sandboxLog = getSandboxLog()
  const blocked = sandboxLog.filter((item) => item.status === 'BLOCKED').length
  const overloadScore = plugins.length * 5 + blocked * 15

  return {
    overloaded: overloadScore > 80,
    overloadScore,
    pluginCount: plugins.length,
    blockedRuns: blocked,
  }
}

export function preventPluginExplosion() {
  const marketplaceSize = listMarketplaceModules().length

  return {
    controlled: marketplaceSize <= 50,
    marketplaceSize,
    maxRecommendedPlugins: 50,
    action: marketplaceSize > 50 ? 'LIMIT_NEW_PLUGIN_PUBLICATION' : 'ALLOW_PLUGIN_GROWTH',
  }
}

export function maintainSystemBalance() {
  const overload = detectEcosystemOverload()
  const explosion = preventPluginExplosion()

  return {
    ecosystemStabilityIndex: Math.max(0, 100 - overload.overloadScore),
    balance: overload.overloaded || !explosion.controlled ? 'REBALANCE_REQUIRED' : 'BALANCED',
    overload,
    explosion,
  }
}
