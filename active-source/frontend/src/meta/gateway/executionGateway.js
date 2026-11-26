import { supportSQLDatabase, writeDatabase } from '../data/databaseLayer.js'
import { enforceTenantFilter } from '../data/tenantIsolationLayer.js'

export function executeRequest({ module, action = 'list', tenantId, params = {} } = {}) {
  const scopedParams = enforceTenantFilter({ ...params, tenantId })
  const isWriteAction = ['create', 'update', 'execute', 'approve', 'complete', 'delete'].includes(action)
  const data = isWriteAction
    ? writeDatabase(module, { ...scopedParams, action, updatedAt: Date.now() }, scopedParams)
    : supportSQLDatabase(module, action, scopedParams)

  if (!data || (Array.isArray(data) && data.length === 0)) {
    return {
      success: true,
      data: action === 'detail' ? null : [],
      error: null,
      meta: {
        source: 'real-data-gateway',
        module,
        action,
        tenantId: scopedParams.tenantId,
      },
    }
  }

  return {
    success: true,
    data,
    error: null,
    meta: {
      source: 'real-data-gateway',
      module,
      action,
      tenantId: scopedParams.tenantId,
    },
  }
}

export const executionGateway = {
  executeRequest,
}
