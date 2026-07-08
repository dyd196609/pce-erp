function moduleFromEvent(event = {}) {
  const [rawModule] = String(event.type || '').split('.')
  return rawModule === 'purchaseOrder' ? 'purchase' : rawModule || 'enterprise'
}

export function createCostOptimizationStrategy(event = {}, risk = {}) {
  return {
    type: 'cost_optimization',
    priority: risk.financial?.score > 45 ? 'HIGH' : 'MEDIUM',
    objective: 'control_purchase_and_payable_cost',
    levers: ['supplier_price_check', 'payment_term_review', 'cost_center_validation'],
  }
}

export function createSupplyChainOptimizationStrategy(event = {}, risk = {}) {
  return {
    type: 'supply_chain_optimization',
    priority: risk.supplyChain?.score > 55 ? 'HIGH' : 'MEDIUM',
    objective: 'restore_supply_continuity',
    levers: ['reorder_planning', 'supplier_follow_up', 'delivery_schedule_adjustment'],
  }
}

export function createRevenueOptimizationStrategy(event = {}) {
  return {
    type: 'revenue_optimization',
    priority: 'MEDIUM',
    objective: 'convert_revenue_signal_to_fulfillment',
    levers: ['order_creation', 'margin_review', 'delivery_commitment'],
  }
}

export function createRiskMitigationStrategy(event = {}, risk = {}) {
  return {
    type: 'risk_mitigation',
    priority: risk.level === 'HIGH' ? 'HIGH' : 'MEDIUM',
    objective: 'reduce_cross_module_execution_risk',
    levers: ['approval_gate', 'manual_review', 'event_chain_monitoring'],
  }
}

export function generateStrategy(event = {}, risk = {}, reasoning = {}) {
  const type = String(event.type || '')
  const module = moduleFromEvent(event)
  const strategies = []

  if (module === 'finance' || module === 'purchase' || type.includes('Payable')) {
    strategies.push(createCostOptimizationStrategy(event, risk))
  }
  if (module === 'inventory' || module === 'scm' || type === 'inventory.lowStock' || type === 'scm.delay') {
    strategies.push(createSupplyChainOptimizationStrategy(event, risk))
  }
  if (module === 'crm' || type === 'crm.dealClosed') {
    strategies.push(createRevenueOptimizationStrategy(event))
  }
  if (risk.level !== 'LOW' || reasoning.patterns?.chainDepth > 2) {
    strategies.push(createRiskMitigationStrategy(event, risk))
  }

  if (!strategies.length) {
    strategies.push({
      type: 'operational_monitoring',
      priority: 'LOW',
      objective: 'keep_event_under_observation',
      levers: ['status_tracking', 'owner_notification'],
    })
  }

  return {
    primary: strategies[0],
    candidates: strategies,
    generatedAt: Date.now(),
  }
}
