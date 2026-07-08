const planQuotas = {
  free: {
    workflowExecutions: 20,
    aiDecisions: 0,
    simulations: 5,
    apiCalls: 200,
  },
  basic: {
    workflowExecutions: 100,
    aiDecisions: 20,
    simulations: 30,
    apiCalls: 1000,
  },
  pro: {
    workflowExecutions: 500,
    aiDecisions: 150,
    simulations: 200,
    apiCalls: 5000,
  },
  enterprise: {
    workflowExecutions: 5000,
    aiDecisions: 2000,
    simulations: 2000,
    apiCalls: 50000,
  },
}

const quotaUsage = {}

function tenantKey(context = {}) {
  return context.tenantId || context.runtimeState?.tenant?.id || context.tenant?.id || 'demo_company'
}

function planKey(context = {}) {
  return context.plan || context.runtimeState?.plan || context.tenant?.plan || 'free'
}

function getBucket(context = {}) {
  const key = tenantKey(context)
  if (!quotaUsage[key]) {
    quotaUsage[key] = {
      workflowExecutions: 0,
      aiDecisions: 0,
      simulations: 0,
      apiCalls: 0,
    }
  }

  return quotaUsage[key]
}

export function recordQuotaUsage(context = {}, type = 'apiCalls', units = 1) {
  const bucket = getBucket(context)
  bucket[type] = Number(bucket[type] || 0) + Number(units || 1)
  return getQuotaStatus(context)
}

export function getQuotaStatus(context = {}) {
  const plan = planKey(context)
  const limits = planQuotas[plan] || planQuotas.free
  const usage = getBucket(context)
  const remaining = Object.keys(limits).reduce((result, key) => {
    result[key] = Math.max(0, limits[key] - (usage[key] || 0))
    return result
  }, {})

  return {
    mode: 'SAAS_QUOTA',
    tenantId: tenantKey(context),
    plan,
    limits,
    usage: {
      ...usage,
    },
    remaining,
    exceeded: Object.keys(limits).filter((key) => (usage[key] || 0) > limits[key]),
  }
}

export function canUseQuota(context = {}, type = 'apiCalls') {
  const status = getQuotaStatus(context)
  return (status.remaining[type] || 0) > 0
}

export function resetQuotaUsage(tenantId) {
  if (tenantId) {
    delete quotaUsage[tenantId]
  } else {
    Object.keys(quotaUsage).forEach((key) => delete quotaUsage[key])
  }
}
