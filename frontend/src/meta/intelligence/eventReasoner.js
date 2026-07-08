const moduleMeanings = {
  purchase: 'procurement_commitment',
  finance: 'financial_obligation',
  crm: 'revenue_signal',
  inventory: 'stock_pressure',
  scm: 'supply_chain_pressure',
}

function moduleFromEvent(event = {}) {
  const [rawModule] = String(event.type || '').split('.')
  return rawModule === 'purchaseOrder' ? 'purchase' : rawModule || 'enterprise'
}

export function analyzeEventPatterns(event = {}, stream = []) {
  const module = moduleFromEvent(event)
  const relatedEvents = stream.filter((item) => moduleFromEvent(item) === module)
  const sourceEvents = stream.filter((item) => item.source === event.type || item.type === event.source)

  return {
    module,
    frequency: relatedEvents.length,
    chainDepth: Number(event.depth || 0),
    hasRecentDependency: sourceEvents.length > 0,
    pattern: relatedEvents.length > 3 ? 'REPEATED_SIGNAL' : 'NORMAL_SIGNAL',
  }
}

export function inferBusinessMeaning(event = {}) {
  const module = moduleFromEvent(event)
  const type = String(event.type || '')

  if (type === 'purchase.approved') return 'approved_purchase_creates_finance_obligation'
  if (type === 'crm.dealClosed') return 'closed_deal_requires_fulfillment'
  if (type === 'inventory.lowStock') return 'inventory_shortage_requires_reorder'
  if (type === 'scm.delay') return 'supply_delay_requires_plan_adjustment'

  return moduleMeanings[module] || 'enterprise_event'
}

export function detectHiddenDependencies(event = {}, stream = []) {
  const payload = event.payload || {}
  const module = moduleFromEvent(event)
  const dependencies = new Set()

  if (module === 'purchase' || payload.supplierId) dependencies.add('finance')
  if (module === 'crm') dependencies.add('purchase')
  if (module === 'inventory') dependencies.add('purchase')
  if (module === 'scm') dependencies.add('purchase')

  stream
    .filter((item) => item.correlationId === event.correlationId && item.type !== event.type)
    .forEach((item) => dependencies.add(moduleFromEvent(item)))

  dependencies.delete(module)

  return [...dependencies]
}

export function reasonAboutEvent(event = {}, stream = []) {
  return {
    patterns: analyzeEventPatterns(event, stream),
    meaning: inferBusinessMeaning(event),
    hiddenDependencies: detectHiddenDependencies(event, stream),
  }
}
