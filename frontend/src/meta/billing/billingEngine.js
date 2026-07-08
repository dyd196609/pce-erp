const plans = {
  basic: 99,
  pro: 299,
  enterprise: 999,
}

export function calculateBill(tenant = {}, usage = {}) {
  const plan = tenant.plan || tenant.config?.plan || 'basic'

  return {
    tenant: tenant.id,
    plan,
    cost: plans[plan] || plans.basic,
    usage,
  }
}

export function listPlans() {
  return plans
}
