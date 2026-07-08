function amountFromPayload(payload = {}) {
  const record = payload.record || payload
  const quantity = Number(record.quantity || record.stockQuantity || 0)
  const price = Number(record.price || record.cost || record.balance || 0)
  const explicit = Number(record.amount || record.opportunityValue || 0)
  return explicit || quantity * price
}

function scoreLevel(score) {
  if (score >= 75) return 'HIGH'
  if (score >= 45) return 'MEDIUM'
  return 'LOW'
}

export function detectFinancialRisk(event = {}) {
  const amount = amountFromPayload(event.payload || {})
  const type = String(event.type || '')
  let score = 12

  if (type.includes('finance') || type === 'purchase.approved') score += 18
  if (amount > 100000) score += 35
  else if (amount > 30000) score += 18

  return {
    score: Math.min(score, 100),
    level: scoreLevel(score),
    reason: amount > 0 ? `amount:${amount}` : 'normal_financial_signal',
  }
}

export function detectSupplyChainRisk(event = {}) {
  const type = String(event.type || '')
  const record = event.payload?.record || event.payload || {}
  let score = 10

  if (type === 'inventory.lowStock') score += 45
  if (type === 'scm.delay') score += 50
  if (Number(record.stockQuantity ?? 999999) <= Number(record.reorderLevel ?? -1)) score += 20

  return {
    score: Math.min(score, 100),
    level: scoreLevel(score),
    reason: type === 'scm.delay' ? 'supplier_delay' : type === 'inventory.lowStock' ? 'low_stock' : 'normal_supply_signal',
  }
}

export function detectWorkflowRisk(event = {}, context = {}) {
  const depth = Number(event.depth || 0)
  const blocked = context.blockedTransitions || 0
  const score = Math.min(100, 8 + depth * 14 + blocked * 20)

  return {
    score,
    level: scoreLevel(score),
    reason: depth > 2 ? 'deep_event_chain' : blocked ? 'blocked_transition' : 'normal_workflow',
  }
}

export function detectExecutionRisk(event = {}, context = {}) {
  const circularTriggers = context.circularTriggers || 0
  const retryCount = context.retryCount || event.payload?.retryCount || 0
  const score = Math.min(100, 10 + circularTriggers * 40 + retryCount * 15)

  return {
    score,
    level: scoreLevel(score),
    reason: circularTriggers ? 'circular_trigger_detected' : retryCount ? 'retry_pressure' : 'normal_execution',
  }
}

export function assessRisk(event = {}, context = {}) {
  const financial = detectFinancialRisk(event)
  const supplyChain = detectSupplyChainRisk(event)
  const workflow = detectWorkflowRisk(event, context)
  const execution = detectExecutionRisk(event, context)
  const averageScore = Math.round((financial.score + supplyChain.score + workflow.score + execution.score) / 4)
  const score = Math.max(averageScore, financial.score, supplyChain.score, workflow.score, execution.score)

  return {
    score,
    level: scoreLevel(score),
    financial,
    supplyChain,
    workflow,
    execution,
  }
}
