import { checkPermission } from '../auth/rbacEngine.js'
import { calculateBill } from '../billing/billingEngine.js'
import { logEvent, traceRequest } from '../obs/observabilityHub.js'
import { runProfitOS } from '../profitOS.js'
import { ensureTenant } from '../tenant/tenantManager.js'

const rateLimitState = {}
const RATE_LIMIT = 100

function checkRateLimit(tenantId, api = 'profitos.run') {
  const windowMs = 60 * 1000
  const now = Date.now()
  const key = `${tenantId}:${api}`
  const current = rateLimitState[key]

  if (!current || now - current.startedAt > windowMs) {
    rateLimitState[key] = {
      startedAt: now,
      count: 1,
    }
    return true
  }

  current.count++
  return current.count <= RATE_LIMIT
}

export async function handleRequest(req = {}) {
  const {
    tenantId,
    input,
    context = {},
    role = 'viewer',
    action = 'EXECUTE',
  } = req

  const trace = traceRequest(req)
  const resolvedTenantId = tenantId || 'default'
  const withinLimit = checkRateLimit(resolvedTenantId, 'profitos.run')

  if (!withinLimit) {
    logEvent({
      type: 'RATE_LIMIT',
      tenantId: resolvedTenantId,
      status: 'BLOCKED',
    })

    return {
      success: false,
      error: 'RATE_LIMITED',
      trace,
    }
  }

  const allowed = checkPermission(role, action)

  if (!allowed) {
    logEvent({
      type: 'RBAC_DENY',
      tenantId,
      role,
      action,
    })

    return {
      success: false,
      error: 'FORBIDDEN',
      trace,
    }
  }

  const tenant = ensureTenant(resolvedTenantId, context.tenantConfig || {})
  const result = runProfitOS(input, {
    ...context,
    tenantId: tenant.id,
  })
  const billing = calculateBill(tenant, {
    requests: 1,
    goals: result.agent?.goals?.length || 0,
  })

  logEvent({
    type: 'PROFITOS_API_RUN',
    tenantId: tenant.id,
    role,
    action,
    status: 'SUCCESS',
  })

  return {
    success: true,
    data: result,
    tenant,
    billing,
    trace,
  }
}
