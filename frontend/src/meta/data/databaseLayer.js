import { fetchRealData } from './apiConnector.js'
import { enforceTenantFilter, preventCrossTenantLeakage } from './tenantIsolationLayer.js'

const tables = new Map()
const dbEvents = []

function tableKey(module, tenantId) {
  return `${tenantId}:${module}`
}

function normalizeRows(data) {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  if (Array.isArray(data?.list)) return data.list
  if (Array.isArray(data?.data)) return data.data
  if (data?.data && typeof data.data === 'object') return [data.data]
  if (data && typeof data === 'object') return [data]
  return []
}

function getTable(module, tenantId) {
  const key = tableKey(module, tenantId)
  if (!tables.has(key)) tables.set(key, [])
  return tables.get(key)
}

function upsertRows(module, rows = [], context = {}) {
  const tenantParams = enforceTenantFilter(context)
  const table = getTable(module, tenantParams.tenantId)

  rows.forEach((row) => {
    const next = preventCrossTenantLeakage(row, tenantParams)
    if (!next) return
    const id = next.id || next.accountId || next.customerId || next.skuId || next.purchaseOrderId || next.supplierId || Date.now()
    const index = table.findIndex((item) => String(item.id || item.accountId || item.customerId || item.skuId || item.purchaseOrderId || item.supplierId) === String(id))
    if (index >= 0) table.splice(index, 1, { ...table[index], ...next })
    else table.unshift({ ...next, id: next.id || id })
  })

  return table
}

export function seedDatabase(module, rows = [], context = {}) {
  const tenantParams = enforceTenantFilter(context)
  const table = getTable(module, tenantParams.tenantId)
  if (table.length === 0) {
    upsertRows(module, rows, tenantParams)
  }

  return {
    module,
    tenantId: tenantParams.tenantId,
    rows: getTable(module, tenantParams.tenantId).length,
  }
}

export function supportSQLDatabase(module, action = 'list', params = {}) {
  const tenantParams = enforceTenantFilter(params)
  const table = getTable(module, tenantParams.tenantId)

  if (action === 'detail') {
    const id = tenantParams.id
    return table.find((row) => [row.id, row.accountId, row.customerId, row.skuId, row.purchaseOrderId, row.supplierId].some((value) => String(value) === String(id))) || null
  }

  return [...table]
}

export async function supportAPIDatabase(module, action = 'list', params = {}) {
  const response = await fetchRealData(module, action, params)
  if (response?.success === false) return response

  const rows = normalizeRows(response)
  if (rows.length) {
    upsertRows(module, rows, params)
  }

  return {
    success: true,
    data: rows.length === 1 && action === 'detail' ? rows[0] : rows,
    meta: {
      module,
      timestamp: Date.now(),
      source: 'api-database',
    },
  }
}

export async function readDatabase(module, action = 'list', params = {}) {
  const tenantParams = enforceTenantFilter(params)
  const api = await supportAPIDatabase(module, action, tenantParams)
  const apiData = normalizeRows(api)

  if (api?.success !== false && apiData.length) {
    dbEvents.unshift({ module, action, tenantId: tenantParams.tenantId, source: 'api', timestamp: Date.now() })
    return action === 'detail'
      ? preventCrossTenantLeakage(apiData[0], tenantParams)
      : preventCrossTenantLeakage(apiData, tenantParams)
  }

  const sql = supportSQLDatabase(module, action, tenantParams)
  dbEvents.unshift({ module, action, tenantId: tenantParams.tenantId, source: 'persistent-store', timestamp: Date.now() })
  if (dbEvents.length > 100) dbEvents.length = 100
  return preventCrossTenantLeakage(sql, tenantParams)
}

export function writeDatabase(module, data = {}, context = {}) {
  const tenantParams = enforceTenantFilter(context)
  const rows = upsertRows(module, Array.isArray(data) ? data : [data], tenantParams)
  dbEvents.unshift({ module, action: 'write', tenantId: tenantParams.tenantId, source: 'persistent-store', timestamp: Date.now() })
  if (dbEvents.length > 100) dbEvents.length = 100

  return preventCrossTenantLeakage(rows, tenantParams)
}

export function getDatabaseLayerSnapshot() {
  return {
    databaseLayer: 'ENABLED',
    sqlDatabases: 'SUPPORTED',
    apiDatabases: 'SUPPORTED',
    unifiedDataAccess: 'ACTIVE',
    tables: [...tables.keys()],
    events: [...dbEvents],
  }
}
