import { getAllSchemas } from '../core/schemaRegistry.js'

const requiredModules = {
  finance: ['accountId', 'accountName', 'debit', 'credit', 'balance'],
  crm: ['customerId', 'customerName', 'contactInfo', 'leadStage'],
  scm: ['supplierId', 'materialId', 'supplyStatus', 'leadTime'],
  inventory: ['skuId', 'stockQuantity', 'warehouseLocation', 'reorderLevel'],
  purchase: ['purchaseOrderId', 'supplierId', 'quantity', 'approvalStatus'],
}

function normalizeModuleName(schema = {}) {
  const source = `${schema.name || ''} ${schema.api?.module || ''} ${schema.meta?.module || ''} ${schema.meta?.title || ''}`.toLowerCase()
  if (source.includes('purchase')) return 'purchase'
  if (source.includes('finance')) return 'finance'
  if (source.includes('crm')) return 'crm'
  if (source.includes('scm')) return 'scm'
  if (source.includes('inventory')) return 'inventory'
  return null
}

function collectFields(schema = {}) {
  const columns = schema.columns || schema.fields || schema.ui?.list?.columns || []
  return columns.map((item) => item.prop || item.key || item.field || item.name).filter(Boolean)
}

export function validateModule(moduleName, schemas = getAllSchemas()) {
  const schema = schemas.find((item) => normalizeModuleName(item) === moduleName)
  const fields = collectFields(schema || {})
  const required = requiredModules[moduleName] || []
  const missing = required.filter((field) => !fields.includes(field))

  return {
    module: moduleName,
    compliant: Boolean(schema) && missing.length === 0,
    schemaFound: Boolean(schema),
    required,
    fields,
    missing,
    score: required.length ? Math.round(((required.length - missing.length) / required.length) * 100) : 100,
  }
}

export function checkModuleCompliance() {
  const schemas = getAllSchemas()
  const modules = Object.keys(requiredModules).map((moduleName) => validateModule(moduleName, schemas))
  const score = Math.round(modules.reduce((sum, item) => sum + item.score, 0) / modules.length)

  return {
    compliant: modules.every((item) => item.compliant),
    moduleComplianceIndex: score,
    modules,
    timestamp: Date.now(),
  }
}
