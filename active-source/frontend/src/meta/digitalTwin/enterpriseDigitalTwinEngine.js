function toNumber(value, fallback = 0) {
  const next = Number(value)
  return Number.isFinite(next) ? next : fallback
}

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, value))
}

function average(values) {
  if (!values.length) return 0
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function normalizeRows(context = {}) {
  if (Array.isArray(context.rows)) return context.rows
  if (Array.isArray(context.data)) return context.data
  if (context.record) return [context.record]
  return []
}

export function buildEnterpriseState(context = {}) {
  const rows = normalizeRows(context)
  const record = context.record || rows[0] || {}
  const amountValues = rows.map((row) => toNumber(row.amount || row.actual_amount || row.revenue))
  const inventoryQty = rows.reduce((sum, row) => sum + toNumber(row.stock_qty || row.qty || row.quantity), 0)
  const openOrders = rows.filter((row) => !['CLOSED', 'STOCKED'].includes(row.workflow_state)).length
  const workflowState = record.workflow_state || context.schema?.workflow?.states?.[0] || 'DRAFT'

  return {
    module: context.schema?.api?.module || context.schema?.name || context.module || 'enterprise',
    action: context.action || 'simulate',
    inventory: {
      stockQty: inventoryQty,
      turnover: clamp(inventoryQty / 1000, 0, 2),
      shortageRisk: inventoryQty > 0 && inventoryQty < 120 ? 'HIGH' : inventoryQty < 300 ? 'MEDIUM' : 'LOW',
    },
    cashFlow: {
      current: amountValues.reduce((sum, value) => sum + value, 0),
      averageOrderValue: average(amountValues),
      pressure: average(amountValues) > 100000 ? 'HIGH' : 'NORMAL',
    },
    production: {
      openWork: openOrders,
      capacityLoad: clamp(openOrders / 12, 0, 1),
      throughputRisk: openOrders > 8 ? 'HIGH' : openOrders > 4 ? 'MEDIUM' : 'LOW',
    },
    order: {
      count: rows.length,
      open: openOrders,
      currentState: workflowState,
      amount: toNumber(record.amount || record.actual_amount || record.revenue),
    },
  }
}

export function simulateWorkflow(state = {}) {
  const delayDays = state.order.currentState === 'SUBMITTED' ? 2 : state.order.currentState === 'APPROVED' ? 1 : 0
  const bottleneck = state.production.capacityLoad > 0.7
    ? 'production_capacity'
    : state.inventory.shortageRisk === 'HIGH'
      ? 'inventory_shortage'
      : 'none'
  const transitionFailureRisk = clamp(
    (delayDays * 0.12) +
    (state.production.capacityLoad * 0.25) +
    (state.inventory.shortageRisk === 'HIGH' ? 0.25 : 0)
  )

  return {
    approvalDelayImpact: {
      delayDays,
      impactScore: clamp(delayDays / 5),
    },
    workflowBottleneck: bottleneck,
    transitionFailureRisk,
    simulatedPath: [state.order.currentState, 'NEXT_STATE', 'CLOSED'],
  }
}

export function forecastKPIs(state = {}) {
  const baseRevenue = state.cashFlow.current || state.order.amount || 10000
  const riskDrag = state.inventory.shortageRisk === 'HIGH' ? 0.96 : state.production.throughputRisk === 'HIGH' ? 0.98 : 1.02
  const trendCurve = Array.from({ length: 7 }, (_, index) => {
    const day = index + 1
    const revenue = Math.round(baseRevenue * (1 + day * 0.015) * riskDrag)
    const orderClosure = clamp(0.45 + day * 0.06 - state.production.capacityLoad * 0.12)
    const executionScore = Math.round(clamp(0.82 + day * 0.01 - state.production.capacityLoad * 0.08, 0, 1) * 100)

    return {
      day,
      revenue,
      orderClosure,
      executionScore,
    }
  })
  const anomalies = trendCurve
    .filter((point) => point.executionScore < 75 || point.orderClosure < 0.5)
    .map((point) => ({
      day: point.day,
      type: point.executionScore < 75 ? 'EXECUTION_SCORE_DROP' : 'LOW_ORDER_CLOSURE',
    }))

  return {
    horizon: '7-day',
    trendCurve,
    anomalies,
  }
}

export function simulateRisk(state = {}) {
  const financialRisk = state.cashFlow.pressure === 'HIGH' ? 'MEDIUM' : 'LOW'
  const supplyChainRisk = state.inventory.shortageRisk
  const workflowRisk = state.order.currentState === 'SUBMITTED' ? 'MEDIUM' : 'LOW'
  const executionRisk = state.production.throughputRisk
  const riskScore = [
    financialRisk,
    supplyChainRisk,
    workflowRisk,
    executionRisk,
  ].reduce((score, risk) => score + (risk === 'HIGH' ? 3 : risk === 'MEDIUM' ? 2 : 1), 0)

  return {
    financialRisk,
    supplyChainRisk,
    workflowRisk,
    executionRisk,
    riskLevel: riskScore >= 10 ? 'HIGH' : riskScore >= 7 ? 'MEDIUM' : 'LOW',
    riskScore,
  }
}

export function predictDecision(state = {}) {
  const action = String(state.action || '').toLowerCase()
  let predictedOutcome = 'NO_CHANGE'
  let impactScore = 0.2

  if (action.includes('approve')) {
    predictedOutcome = state.inventory.shortageRisk === 'HIGH'
      ? 'APPROVAL_WITH_SUPPLY_RISK'
      : 'APPROVAL_ACCELERATES_CLOSURE'
    impactScore = state.inventory.shortageRisk === 'HIGH' ? 0.55 : 0.82
  }

  if (action.includes('reject')) {
    predictedOutcome = 'ORDER_DELAY_AND_REWORK'
    impactScore = 0.35
  }

  if (action.includes('submit')) {
    predictedOutcome = 'REVIEW_QUEUE_INCREASE'
    impactScore = 0.5
  }

  const riskLevel = impactScore > 0.75 && state.inventory.shortageRisk !== 'HIGH'
    ? 'LOW'
    : impactScore > 0.5
      ? 'MEDIUM'
      : 'HIGH'

  return {
    action: state.action,
    predictedOutcome,
    impactScore,
    riskLevel,
  }
}

export function simulateEnterpriseState(context = {}) {
  const state = buildEnterpriseState(context)
  const workflowSimulation = simulateWorkflow(state)
  const kpiForecast = forecastKPIs(state)
  const riskProfile = simulateRisk(state)
  const decisionOutcome = predictDecision(state)

  return {
    mode: 'V13.1_ENTERPRISE_DIGITAL_TWIN',
    state,
    workflowSimulation,
    kpiForecast,
    riskProfile,
    decisionOutcome,
    readonly: true,
  }
}
