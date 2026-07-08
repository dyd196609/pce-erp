/**
 * ============================
 * Meta Runtime V13 - Billing System
 * SaaS计费核心
 * ============================
 */

const plans = {
  free: { limit: 10 },
  pro: { limit: 100 },
  enterprise: { limit: -1 },
}

/**
 * 计费检查
 */
export const checkQuota = (tenant) => {
  const plan = plans[tenant.plan]

  if (!plan) return false

  if (plan.limit === -1) return true

  return tenant.usage < plan.limit
}

/**
 * 增加使用量
 */
export const addUsage = (tenant) => {
  tenant.usage = (tenant.usage || 0) + 1
}

/**
 * 升级套餐
 */
export const upgradePlan = (tenant, plan) => {
  tenant.plan = plan
}
