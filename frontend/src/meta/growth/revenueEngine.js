const revenueEvents = []

const planExpansionValue = {
  free: 0,
  basic: 99,
  pro: 299,
  enterprise: 999,
}

export function trackRevenueEvent(event = {}) {
  const entry = {
    tenantId: event.tenantId || event.tenant?.id || 'demo_company',
    type: event.type || 'usage',
    amount: Number(event.amount || 0),
    module: event.module || 'platform',
    plan: event.plan,
    timestamp: Date.now(),
  }

  revenueEvents.push(entry)
  return entry
}

export function trackSubscriptionUpgrade(event = {}) {
  const from = event.fromPlan || 'free'
  const to = event.toPlan || event.plan || 'basic'
  return trackRevenueEvent({
    ...event,
    type: 'subscription_upgrade',
    amount: Math.max(0, (planExpansionValue[to] || 0) - (planExpansionValue[from] || 0)),
    plan: to,
  })
}

export function trackModulePurchase(event = {}) {
  return trackRevenueEvent({
    ...event,
    type: 'module_purchase',
    amount: Number(event.amount || event.price || 0),
  })
}

export function trackAiFeatureMonetization(event = {}) {
  return trackRevenueEvent({
    ...event,
    type: 'ai_feature',
    module: event.module || 'ai-decision',
    amount: Number(event.amount || 0.2),
  })
}

export function getRevenueGrowth() {
  const total = revenueEvents.reduce((sum, event) => sum + Number(event.amount || 0), 0)
  const byType = revenueEvents.reduce((map, event) => {
    map[event.type] = (map[event.type] || 0) + Number(event.amount || 0)
    return map
  }, {})

  return {
    mode: 'V17_REVENUE_GROWTH',
    expansionRevenue: Number(total.toFixed(2)),
    subscriptionUpgrades: revenueEvents.filter((event) => event.type === 'subscription_upgrade').length,
    modulePurchases: revenueEvents.filter((event) => event.type === 'module_purchase').length,
    aiMonetizationEvents: revenueEvents.filter((event) => event.type === 'ai_feature').length,
    byType,
    events: revenueEvents.slice(-20),
  }
}

export function getRevenueEvents() {
  return revenueEvents
}

export function clearRevenueEvents() {
  revenueEvents.length = 0
}
