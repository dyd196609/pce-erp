import { evaluateSecurity } from '../governance/securityEngine.js'
import { generatePreemptiveOptimizations } from './predictiveControlEngine.js'

export function generateFallbackRouting(context = {}) {
  const predictive = generatePreemptiveOptimizations(context)

  return predictive.failures.map((failure) => ({
    moduleKey: failure.moduleKey,
    route: `/fallback/${failure.moduleKey}`,
    status: 'READY',
  }))
}

export function repairWorkflows(context = {}) {
  const security = evaluateSecurity(context)

  return security.isolatedWorkflows.map((workflow) => ({
    entity: workflow.entity,
    repair: 'RESET_TO_SAFE_WORKFLOW',
    status: 'SIMULATED',
  }))
}

export function rerouteAPIs(context = {}) {
  const predictive = generatePreemptiveOptimizations(context)

  return predictive.api.bottlenecks.map((bottleneck) => ({
    target: bottleneck.target,
    fallbackApi: '/api/execution/fallback/list',
    status: 'PREPARED',
  }))
}

export function degradeModules(context = {}) {
  const predictive = generatePreemptiveOptimizations(context)

  return predictive.failures.map((failure) => ({
    moduleKey: failure.moduleKey,
    mode: 'READ_ONLY_FALLBACK',
    status: 'SUGGESTED',
  }))
}

export function runEcosystemSelfHealing(context = {}) {
  const fallbackRouting = generateFallbackRouting(context)
  const workflowRepair = repairWorkflows(context)
  const apiRerouting = rerouteAPIs(context)
  const moduleDegradation = degradeModules(context)

  return {
    mode: 'V22_ECOSYSTEM_SELF_HEALING',
    fallbackRouting,
    workflowRepair,
    apiRerouting,
    moduleDegradation,
    healingRate: fallbackRouting.length + workflowRepair.length + apiRerouting.length + moduleDegradation.length > 0
      ? 1
      : 0,
  }
}
