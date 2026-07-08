import { simulateEnterpriseState } from '../digitalTwin/enterpriseDigitalTwinEngine.js'
import { runReviewControlLoop } from '../review/reviewControlEngine.js'
import { canPerformAction } from '../runtime/permissionEngine.js'
import { stateManager } from '../runtime/stateManager.js'
import { recordUsage } from '../saas/billing/billingEngine.js'
import { recordQuotaUsage } from '../saas/quota/quotaManager.js'
import { recordLatency, recordModuleHealth } from '../saas/monitoring/productionMonitor.js'
import { recordActivation, activationSteps } from '../growth/activationEngine.js'
import { recordRetentionActivity } from '../growth/retentionEngine.js'
import { trackAiFeatureMonetization } from '../growth/revenueEngine.js'

function clampScore(value) {
  return Math.max(0, Math.min(100, Math.round(value)))
}

function riskToValue(riskLevel) {
  if (riskLevel === 'HIGH') return 0.8
  if (riskLevel === 'MEDIUM') return 0.45
  return 0.12
}

function riskScoreToValue(riskProfile = {}) {
  return Math.min(1, Number(riskProfile.riskScore || 0) / 12)
}

export function calculateDecisionScore(simulation = {}) {
  const trend = simulation.kpiForecast?.trendCurve || []
  const first = trend[0] || {}
  const last = trend[trend.length - 1] || {}
  const kpiImprovement = Number(last.executionScore || 0) - Number(first.executionScore || 0)
  const riskValue = riskScoreToValue(simulation.riskProfile)
  const workflowBlocked = simulation.workflowSimulation?.workflowBottleneck !== 'none'
  const cashPressure = simulation.state?.cashFlow?.pressure === 'HIGH'
  const impact = Number(simulation.decisionOutcome?.impactScore || 0)

  let score = 55
  score += kpiImprovement * 1.5
  score += impact * 25
  score += (1 - riskValue) * 15
  if (workflowBlocked) score -= 12
  if (cashPressure) score -= 10
  if (simulation.workflowSimulation?.transitionFailureRisk > 0.5) score -= 12

  return clampScore(score)
}

export function assessRisk(simulation = {}) {
  const riskProfile = simulation.riskProfile || {}
  const decisionRisk = riskToValue(simulation.decisionOutcome?.riskLevel)
  const profileRisk = riskScoreToValue(riskProfile)
  const transitionRisk = Number(simulation.workflowSimulation?.transitionFailureRisk || 0)
  const value = Math.max(decisionRisk, profileRisk, transitionRisk)

  return {
    value,
    level: value >= 0.65 ? 'HIGH' : value >= 0.3 ? 'MEDIUM' : 'LOW',
    profile: riskProfile,
  }
}

export function generateRecommendation(score, risk = {}) {
  if (risk.level === 'HIGH') return 'REJECT'
  if (risk.value < 0.2 && score > 85) return 'AUTO_APPROVE'
  if (score >= 70 && risk.level !== 'HIGH') return 'APPROVE'
  if (score >= 45) return 'DEFER'
  return 'REJECT'
}

function resolveModuleKey(context = {}) {
  const module = context.schema?.api?.module || context.schema?.name || context.module || ''
  const normalized = String(module).toLowerCase()

  if (normalized.includes('purchase')) return 'orders'
  if (normalized.includes('inventory')) return 'inventory'
  if (normalized.includes('customer')) return 'customers'
  if (normalized.includes('agent')) return 'agents'
  if (normalized.includes('profit')) return 'profit-analysis'

  return normalized || 'dashboard'
}

export function applyPolicyConstraints(context = {}) {
  const runtimeState = context.runtimeState || stateManager.snapshot()
  const review = runReviewControlLoop(context.schema || {})
  const roleAllowed = canPerformAction(runtimeState.role, 'EXECUTE')
  const blocked = review.controlMode === 'BLOCKED'
  const reviewAllowsAutoApproval = ['NORMAL', 'MONITOR'].includes(review.controlMode)
  const moduleKey = resolveModuleKey(context)

  return {
    finalAuthority: 'reviewControlEngine',
    permissionOverrideRequired: true,
    roleAllowed,
    moduleKey,
    reviewControlMode: review.controlMode,
    blocked,
    canAutoApprove: roleAllowed && !blocked && reviewAllowsAutoApproval,
    reason: blocked
      ? 'BLOCKED state cannot be overridden'
      : !reviewAllowsAutoApproval
        ? 'review control does not allow automatic approval'
        : roleAllowed
        ? 'permission and review constraints passed'
        : 'role does not allow execution',
  }
}

function autoExecuteDecision(recommendation, risk, score, policy) {
  const allowed = recommendation === 'AUTO_APPROVE'
    && risk.value < 0.2
    && score > 85
    && policy.canAutoApprove

  return {
    executed: allowed,
    mode: allowed ? 'AUTO_APPROVAL_SIMULATED' : 'NO_AUTO_EXECUTION',
    sideEffect: 'NONE',
    reason: allowed
      ? 'low risk and high score passed policy constraints'
      : policy.reason,
  }
}

export function evaluateDecision(context = {}) {
  const start = Date.now()
  const runtimeState = context.runtimeState || stateManager.snapshot()
  const module = context.schema?.api?.module || context.schema?.name || context.module || 'decision'
  const simulation = simulateEnterpriseState(context)
  const score = calculateDecisionScore(simulation)
  const risk = assessRisk(simulation)
  const recommendation = generateRecommendation(score, risk)
  const policy = applyPolicyConstraints(context)
  const autoApproval = autoExecuteDecision(recommendation, risk, score, policy)

  recordUsage({ tenantId: runtimeState.tenant?.id, module, type: 'aiDecision', units: 1 })
  recordQuotaUsage(runtimeState, 'aiDecisions', 1)
  recordLatency({ tenantId: runtimeState.tenant?.id, module, action: 'aiDecision', latency: Date.now() - start })
  recordModuleHealth({ tenantId: runtimeState.tenant?.id, module, status: 'HEALTHY' })
  recordActivation({ tenantId: runtimeState.tenant?.id, module, step: activationSteps.FIRST_AI_DECISION })
  recordRetentionActivity({ tenantId: runtimeState.tenant?.id, module, workflow: 'aiDecision' })
  trackAiFeatureMonetization({ tenantId: runtimeState.tenant?.id, module, amount: 0.2 })

  return {
    mode: 'V13.2_AI_AUTONOMOUS_DECISION',
    score,
    recommendation: policy.blocked ? 'REJECT' : recommendation,
    risk,
    policy,
    autoApprovalEnabled: policy.canAutoApprove,
    autoApproval,
    explanation: {
      kpiImpact: simulation.decisionOutcome?.impactScore || 0,
      workflowBottleneck: simulation.workflowSimulation?.workflowBottleneck || 'none',
      cashFlowPressure: simulation.state?.cashFlow?.pressure || 'NORMAL',
      finalAuthority: policy.finalAuthority,
    },
    simulation,
  }
}
