const planPrices = {
  free: 0,
  basic: 99,
  pro: 299,
  enterprise: 999,
}

const usageLedger = []
const invoiceLedger = []

function detectPlan(context = {}) {
  return context.plan || context.tenant?.plan || context.runtimeState?.plan || 'free'
}

function getModulePrice(moduleKey) {
  const premiumModules = {
    agents: 49,
    inventory: 29,
    customers: 29,
    'profit-analysis': 79,
    'system-health': 39,
  }

  return premiumModules[moduleKey] || 0
}

export function recordUsage(entry = {}) {
  const normalized = {
    tenantId: entry.tenantId || 'demo_company',
    module: entry.module || 'dashboard',
    type: entry.type || 'api',
    units: Number(entry.units || 1),
    timestamp: Date.now(),
  }

  usageLedger.push(normalized)
  return normalized
}

export function getUsage(tenantId) {
  return usageLedger.filter((entry) => !tenantId || entry.tenantId === tenantId)
}

export function calculateSaasBill(context = {}) {
  const tenantId = context.tenantId || context.tenant?.id || context.runtimeState?.tenant?.id || 'demo_company'
  const plan = detectPlan(context)
  const usage = getUsage(tenantId)
  const enabledModules = context.enabledModules || []
  const moduleCost = enabledModules.reduce((sum, moduleKey) => sum + getModulePrice(moduleKey), 0)
  const executionUnits = usage.filter((entry) => entry.type === 'execution').reduce((sum, entry) => sum + entry.units, 0)
  const apiUnits = usage.filter((entry) => entry.type === 'api').reduce((sum, entry) => sum + entry.units, 0)
  const aiDecisionUnits = usage.filter((entry) => entry.type === 'aiDecision').reduce((sum, entry) => sum + entry.units, 0)
  const usageCost = executionUnits * 0.05 + apiUnits * 0.01 + aiDecisionUnits * 0.2

  return {
    mode: 'SAAS_BILLING',
    tenantId,
    plan,
    baseCost: planPrices[plan] ?? planPrices.free,
    moduleCost,
    usageCost: Number(usageCost.toFixed(2)),
    total: Number(((planPrices[plan] ?? 0) + moduleCost + usageCost).toFixed(2)),
    usage: {
      apiCalls: apiUnits,
      executions: executionUnits,
      aiDecisions: aiDecisionUnits,
      records: usage.length,
    },
  }
}

export function listSaasPlans() {
  return {
    ...planPrices,
  }
}

export function createSubscription(tenant = {}, plan = 'enterprise') {
  return {
    tenantId: tenant.id || tenant.tenantId || 'commercial_demo',
    plan,
    status: 'ACTIVE',
    startedAt: Date.now(),
    price: planPrices[plan] ?? planPrices.enterprise,
  }
}

export function generateInvoice(context = {}) {
  const bill = calculateSaasBill(context)
  const invoice = {
    invoiceId: `INV-${bill.tenantId}-${Date.now()}`,
    tenantId: bill.tenantId,
    plan: bill.plan,
    total: bill.total,
    lineItems: [
      { type: 'base', amount: bill.baseCost },
      { type: 'modules', amount: bill.moduleCost },
      { type: 'usage', amount: bill.usageCost },
    ],
    status: 'ISSUED',
    issuedAt: Date.now(),
  }

  invoiceLedger.unshift(invoice)
  if (invoiceLedger.length > 100) invoiceLedger.length = 100
  return invoice
}

export function calculateEnterpriseBilling(context = {}) {
  const subscription = createSubscription({
    id: context.tenantId || context.tenant?.id,
  }, context.plan || 'enterprise')
  const bill = calculateSaasBill({
    ...context,
    plan: subscription.plan,
  })
  const invoice = generateInvoice({
    ...context,
    plan: subscription.plan,
  })

  return {
    billing: 'ENABLED',
    subscription,
    bill,
    invoice,
    invoices: [...invoiceLedger],
    revenueStream: invoiceLedger.reduce((sum, item) => sum + Number(item.total || 0), 0),
  }
}

export function getCommercialBillingSnapshot(context = {}) {
  const enterprise = calculateEnterpriseBilling(context)

  return {
    ...enterprise,
    metrics: {
      revenueStream: enterprise.revenueStream,
      invoiceCount: enterprise.invoices.length,
      usageRecords: getUsage(enterprise.bill.tenantId).length,
    },
  }
}
