import { analyzeModuleLifecycle } from '../ecosystem/autonomous/moduleLifecycleAI.js'
import { evaluatePluginQuality } from '../ecosystem/governance/qualityEngine.js'

export function evolveModuleStructure(context = {}) {
  const lifecycle = analyzeModuleLifecycle(context)

  return lifecycle.births.map((module) => ({
    moduleKey: module.moduleKey,
    action: 'EXPAND_DISCOVERY_SURFACE',
    reason: 'NEW_MODULE_NEEDS_ADOPTION',
  }))
}

export function removeLowValueFeatures(context = {}) {
  const lifecycle = analyzeModuleLifecycle(context)
  const quality = evaluatePluginQuality()
  const weakPlugins = new Set(quality.ranking.filter((item) => item.score < 60).map((item) => item.pluginId))

  return lifecycle.lifecycle
    .filter((module) => module.decayRisk === 'ELEVATED' || weakPlugins.has(module.pluginId))
    .map((module) => ({
      moduleKey: module.moduleKey,
      action: 'HIDE_LOW_VALUE_FEATURES',
      reason: 'LOW_USAGE_OR_LOW_QUALITY',
    }))
}

export function enhanceHighValueWorkflows(context = {}) {
  const quality = evaluatePluginQuality()

  return quality.ranking
    .filter((plugin) => plugin.score >= 85)
    .map((plugin) => ({
      pluginId: plugin.pluginId,
      action: 'PROMOTE_HIGH_VALUE_WORKFLOW',
      reason: 'HIGH_PLUGIN_SCORE',
    }))
}

export function evolveProduct(context = {}) {
  const structure = evolveModuleStructure(context)
  const removal = removeLowValueFeatures(context)
  const workflows = enhanceHighValueWorkflows(context)

  return {
    mode: 'V23_PRODUCT_EVOLUTION',
    structure,
    removal,
    workflows,
    timeline: [
      ...structure,
      ...removal,
      ...workflows,
    ].map((item, index) => ({
      step: index + 1,
      ...item,
      status: 'SUGGESTED',
    })),
  }
}
