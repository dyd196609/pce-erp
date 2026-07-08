import { emitEvent } from './eventBus.js'

export const businessTriggerRules = [
  {
    event: 'purchase.approved',
    targetModule: 'finance',
    action: 'createPayable',
    description: 'purchase.approved -> finance.createPayable',
  },
  {
    event: 'crm.dealClosed',
    targetModule: 'purchase',
    action: 'createOrder',
    description: 'crm.dealClosed -> purchase.createOrder',
  },
  {
    event: 'inventory.lowStock',
    targetModule: 'purchase',
    action: 'triggerReorder',
    description: 'inventory.lowStock -> purchase.triggerReorder',
  },
  {
    event: 'scm.delay',
    targetModule: 'purchase',
    action: 'adjustPlan',
    description: 'scm.delay -> purchase.adjustPlan',
  },
]

const triggerHistory = []

export function resolveBusinessTriggers(event = {}) {
  return businessTriggerRules.filter((rule) => rule.event === event.type)
}

export function runBusinessTriggers(event = {}) {
  const rules = resolveBusinessTriggers(event)
  const triggered = rules.map((rule) => {
    const next = {
      sourceEvent: event.type,
      targetModule: rule.targetModule,
      action: rule.action,
      payload: {
        ...(event.payload || {}),
        sourceEvent: event.type,
        targetModule: rule.targetModule,
        orchestrationAction: rule.action,
      },
      timestamp: Date.now(),
    }
    triggerHistory.unshift(next)
    emitEvent({
      type: `${rule.targetModule}.${rule.action}`,
      source: event.type,
      payload: next.payload,
      correlationId: event.correlationId,
      depth: Number(event.depth || 0) + 1,
    })
    return next
  })

  return triggered
}

export function getBusinessTriggerDashboard() {
  return {
    rules: businessTriggerRules,
    history: [...triggerHistory],
  }
}
