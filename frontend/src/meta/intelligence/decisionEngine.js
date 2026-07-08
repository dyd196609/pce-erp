import { getEventStream } from '../orchestration/eventBus.js'
import { reasonAboutEvent } from './eventReasoner.js'
import { generateStrategy } from './strategyEngine.js'
import { createActionPlan } from './actionPlanner.js'
import { assessRisk } from './riskEngine.js'

const decisionHistory = []
const evaluatedEvents = new Set()
const maxHistory = 80

function makeDecision(event = {}, risk = {}, reasoning = {}) {
  const type = String(event.type || '')
  const hiddenDependencyCount = reasoning.hiddenDependencies?.length || 0

  if (risk.score >= 90 || Number(event.depth || 0) > 4) {
    return {
      decision: 'REVIEW_REQUIRED',
      action: 'BLOCK_AUTOMATION',
      confidence: 72,
      reason: 'risk_above_automation_threshold',
      allowAutomation: false,
    }
  }

  if (risk.level === 'HIGH') {
    return {
      decision: 'MITIGATE',
      action: 'CONTROLLED_AUTOMATION',
      confidence: 78,
      reason: 'high_risk_requires_guardrails',
      allowAutomation: true,
    }
  }

  if (type === 'purchase.approved' || type === 'crm.dealClosed' || type === 'inventory.lowStock' || type === 'scm.delay') {
    return {
      decision: 'AUTOMATE',
      action: 'TRIGGER_CROSS_MODULE_FLOW',
      confidence: hiddenDependencyCount ? 88 : 82,
      reason: 'recognized_cross_module_business_signal',
      allowAutomation: true,
    }
  }

  return {
    decision: 'MONITOR',
    action: 'OBSERVE',
    confidence: 70,
    reason: 'standard_enterprise_event',
    allowAutomation: true,
  }
}

function remember(event = {}, result = {}) {
  const key = event.id || `${event.type}-${event.timestamp}`
  if (evaluatedEvents.has(key)) return result

  evaluatedEvents.add(key)
  decisionHistory.unshift({
    eventId: key,
    eventType: event.type || 'unknown.event',
    timestamp: Date.now(),
    ...result,
  })

  if (decisionHistory.length > maxHistory) {
    decisionHistory.length = maxHistory
  }

  return result
}

export function evaluateDecision(event = {}) {
  const stream = getEventStream()
  const reasoning = reasonAboutEvent(event, stream)
  const risk = assessRisk(event, {
    circularTriggers: event.payload?.circularTriggers || 0,
  })
  const decision = makeDecision(event, risk, reasoning)
  const strategy = generateStrategy(event, risk, reasoning)
  const actionPlan = createActionPlan(event, decision, strategy, risk)

  return remember(event, {
    decision,
    strategy,
    risk,
    actionPlan,
    reasoning,
  })
}

export function getDecisionHistory() {
  return [...decisionHistory]
}

export function getIntelligenceSnapshot() {
  const history = getDecisionHistory()
  const latest = history[0] || null
  const highRiskCount = history.filter((item) => item.risk?.level === 'HIGH').length
  const executableCount = history.filter((item) => item.actionPlan?.executable).length
  const strategyCount = history.filter((item) => item.strategy?.primary).length
  const total = history.length || 1

  return {
    intelligenceMode: 'ON',
    decisionEngine: 'ACTIVE',
    strategyEngine: 'ENABLED',
    riskEngine: 'ACTIVE',
    latest,
    history,
    metrics: {
      decisionAccuracyIndex: Math.max(70, Math.round(94 - highRiskCount * 2)),
      strategyEfficiencyScore: Math.round((strategyCount / total) * 100),
      riskExposureMeter: Math.min(100, Math.round((highRiskCount / total) * 100)),
      actionExecutionRate: Math.round((executableCount / total) * 100),
    },
  }
}
