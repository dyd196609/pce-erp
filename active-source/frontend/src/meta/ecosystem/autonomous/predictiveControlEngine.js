import { runEcosystemGovernance } from '../governance/governanceRuntime.js'
import { analyzeModuleLifecycle } from './moduleLifecycleAI.js'

export function predictModuleFailure(context = {}) {
  const governance = runEcosystemGovernance(context)
  const lifecycle = analyzeModuleLifecycle(context)

  return [
    ...governance.quality.ranking
      .filter((plugin) => plugin.sandboxRisk === 'HIGH' || plugin.status === 'DEPRECATION_CANDIDATE')
      .map((plugin) => ({
        moduleKey: plugin.pluginId,
        probability: plugin.score < 50 ? 0.8 : 0.55,
        reason: 'LOW_PLUGIN_QUALITY',
      })),
    ...lifecycle.decayPredictions.map((module) => ({
      moduleKey: module.moduleKey,
      probability: 0.45,
      reason: 'LIFECYCLE_DECAY',
    })),
  ]
}

export function predictTenantChurn(context = {}) {
  const governance = runEcosystemGovernance(context)
  const usage = governance.health.moduleUsageRate
  const threatPenalty = governance.security.threatCount > 0 ? 0.25 : 0
  const churnRisk = Math.min(0.95, Math.max(0.05, 0.45 - usage * 0.25 + threatPenalty))

  return {
    tenantId: context.tenantId || 'demo_company',
    churnRisk,
    reason: churnRisk > 0.5 ? 'LOW_USAGE_OR_SECURITY_RISK' : 'STABLE_USAGE',
  }
}

export function predictApiBottlenecks(context = {}) {
  const governance = runEcosystemGovernance(context)
  const reliability = governance.health.apiReliability.reliability

  return {
    reliability,
    bottlenecks: reliability < 0.8
      ? [{ target: 'plugin_api_contract', probability: 0.7, reason: 'LOW_API_RELIABILITY' }]
      : [],
  }
}

export function generatePreemptiveOptimizations(context = {}) {
  const failures = predictModuleFailure(context)
  const churn = predictTenantChurn(context)
  const api = predictApiBottlenecks(context)

  return {
    mode: 'V22_PREDICTIVE_CONTROL',
    failures,
    churn,
    api,
    optimizations: [
      ...failures.map((failure) => ({
        type: 'MODULE_FAILURE_PREVENTION',
        target: failure.moduleKey,
        action: 'ENABLE_FALLBACK_ROUTE',
      })),
      ...(churn.churnRisk > 0.5
        ? [{ type: 'TENANT_CHURN_PREVENTION', target: churn.tenantId, action: 'PROMOTE_ONBOARDING_AND_SUPPORT' }]
        : []),
      ...api.bottlenecks.map((bottleneck) => ({
        type: 'API_BOTTLENECK_PREVENTION',
        target: bottleneck.target,
        action: 'PREPARE_API_REROUTE',
      })),
    ],
  }
}
