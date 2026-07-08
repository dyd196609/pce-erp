import { getInstalledModules, listMarketplaceModules } from '../marketplaceEngine.js'
import { evaluatePluginQuality } from '../governance/qualityEngine.js'

function getAgeStage(module = {}) {
  const ageMs = Date.now() - (module.marketplace?.publishedAt || Date.now())
  const ageDays = ageMs / 86400000

  if (ageDays < 1) return 'BIRTH'
  if (ageDays < 30) return 'GROWTH'
  return 'MATURE'
}

export function analyzeModuleLifecycle(context = {}) {
  const tenantId = context.tenantId || 'demo_company'
  const modules = listMarketplaceModules()
  const installed = getInstalledModules(tenantId)
  const installedKeys = new Set(installed.map((module) => module.key))
  const quality = evaluatePluginQuality()
  const qualityMap = new Map(quality.ranking.map((plugin) => [plugin.pluginId, plugin]))

  const lifecycle = modules.map((module) => {
    const score = qualityMap.get(module.pluginId || module.key)?.score || 80
    const usage = installedKeys.has(module.key) ? 1 : 0
    const stage = getAgeStage(module)
    const decayRisk = score < 60 || usage === 0 ? 'ELEVATED' : 'LOW'

    return {
      moduleKey: module.key,
      pluginId: module.pluginId || module.key,
      stage,
      usage,
      score,
      decayRisk,
      suggestion: decayRisk === 'ELEVATED'
        ? 'REVIEW_OR_DEPRECATE'
        : stage === 'BIRTH'
        ? 'PROMOTE_DISCOVERY'
        : 'KEEP_ACTIVE',
    }
  })

  return {
    mode: 'V22_MODULE_LIFECYCLE_AI',
    lifecycle,
    births: lifecycle.filter((item) => item.stage === 'BIRTH'),
    growth: lifecycle.filter((item) => item.stage === 'GROWTH'),
    decayPredictions: lifecycle.filter((item) => item.decayRisk === 'ELEVATED'),
  }
}
