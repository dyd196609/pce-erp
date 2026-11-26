import { runEcosystemGovernance } from '../governance/governanceRuntime.js'
import { analyzeModuleLifecycle } from './moduleLifecycleAI.js'
import { generatePreemptiveOptimizations } from './predictiveControlEngine.js'
import { runEcosystemSelfHealing } from './selfHealingEngine.js'
import { generateAutonomousPolicy } from './policyGenerator.js'

export function analyzeEcosystem(ecosystemState = {}) {
  const context = {
    tenantId: ecosystemState.tenantId,
  }
  const governance = ecosystemState.governance || runEcosystemGovernance(context)
  const lifecycle = analyzeModuleLifecycle(context)
  const predictive = generatePreemptiveOptimizations(context)

  return {
    governance,
    lifecycle,
    predictive,
    riskDetected: governance.security.threatCount > 0 || predictive.failures.length > 0,
  }
}

export function proposeOptimizations(insights = {}) {
  const actions = []

  if (insights.governance?.quality?.averageScore < 70) {
    actions.push({ type: 'QUALITY_TUNING', action: 'RAISE_PLUGIN_REVIEW_THRESHOLD' })
  }

  insights.predictive?.optimizations?.forEach((optimization) => {
    actions.push({
      type: optimization.type,
      action: optimization.action,
      target: optimization.target,
    })
  })

  insights.lifecycle?.births?.forEach((module) => {
    actions.push({
      type: 'MODULE_GROWTH',
      action: 'PROMOTE_NEW_MODULE',
      target: module.moduleKey,
    })
  })

  return actions
}

export function applySafeMutations(mutations = []) {
  return mutations.map((mutation) => ({
    ...mutation,
    status: 'SAFE_SIMULATION',
    applied: false,
    reason: 'AUTONOMOUS_LAYER_IS_SUGGEST_ONLY',
  }))
}

export function evolveSystem(ecosystemState = {}) {
  const insights = analyzeEcosystem(ecosystemState)
  const mutations = proposeOptimizations(insights)
  const safeMutations = applySafeMutations(mutations)
  const selfHealing = runEcosystemSelfHealing({ tenantId: ecosystemState.tenantId })
  const policy = generateAutonomousPolicy({ tenantId: ecosystemState.tenantId })

  return {
    mode: 'V22_SELF_EVOLUTION',
    insights,
    mutations: safeMutations,
    selfHealing,
    policy,
    autonomyIndex: Math.min(100, 60 + safeMutations.length * 5 + selfHealing.healingRate * 20),
  }
}
