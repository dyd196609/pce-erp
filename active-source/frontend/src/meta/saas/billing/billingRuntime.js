import {
  calculateSaasBill,
  getUsage,
  listSaasPlans,
  recordUsage,
} from './billingEngine.js'
import { getEnabledModules } from '../market/moduleMarketplace.js'

function resolveTenantId(context = {}) {
  return context.tenantId || context.tenant?.id || context.runtimeState?.tenant?.id || 'commercial_demo'
}

function resolvePlan(context = {}) {
  return context.plan || context.tenant?.plan || context.runtimeState?.plan || 'enterprise'
}

export function getSubscriptionPlans() {
  return listSaasPlans()
}

export function recordUsageBilling(context = {}) {
  const tenantId = resolveTenantId(context)
  const entries = context.usageEntries || [
    { tenantId, module: 'dashboard', type: 'api', units: 120 },
    { tenantId, module: 'orders', type: 'execution', units: 28 },
    { tenantId, module: 'profit-analysis', type: 'aiDecision', units: 12 },
  ]

  return {
    mode: 'COMMERCIAL_USAGE_BILLING',
    tenantId,
    entries: entries.map((entry) => recordUsage(entry)),
  }
}

export function calculateEnterpriseBilling(context = {}) {
  const tenantId = resolveTenantId(context)
  const plan = resolvePlan(context)
  const enabledModules = context.enabledModules || getEnabledModules({
    tenantId,
    plan,
  })

  return {
    mode: 'COMMERCIAL_ENTERPRISE_BILLING',
    tenantId,
    plan,
    bill: calculateSaasBill({
      tenantId,
      plan,
      enabledModules,
    }),
  }
}

export function generateInvoice(context = {}) {
  const billing = context.billing || calculateEnterpriseBilling(context)
  const bill = billing.bill || billing

  return {
    mode: 'COMMERCIAL_INVOICE_GENERATION',
    invoiceId: `INV-${bill.tenantId || resolveTenantId(context)}-${Date.now()}`,
    tenantId: bill.tenantId || resolveTenantId(context),
    plan: bill.plan || resolvePlan(context),
    lineItems: [
      { label: 'Subscription', amount: bill.baseCost || 0 },
      { label: 'Enabled modules', amount: bill.moduleCost || 0 },
      { label: 'Usage', amount: bill.usageCost || 0 },
    ],
    total: bill.total || 0,
    status: 'ISSUED',
    issuedAt: Date.now(),
  }
}

export function initBillingSystem(context = {}) {
  const tenantId = resolveTenantId(context)
  const plan = resolvePlan(context)
  const usage = recordUsageBilling({
    ...context,
    tenantId,
  })
  const enterprise = calculateEnterpriseBilling({
    ...context,
    tenantId,
    plan,
  })
  const invoice = generateInvoice({
    ...context,
    billing: enterprise,
  })

  return {
    mode: 'COMMERCIAL_BILLING_RUNTIME',
    status: 'ACTIVE',
    plans: getSubscriptionPlans(),
    usage,
    usageLedger: getUsage(tenantId),
    enterprise,
    invoice,
  }
}
