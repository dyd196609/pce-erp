export const LIST_ACTION_COLUMN_RUNTIME_VERSION = 'V1.14.2.8.4.27.2.39'

export const LIST_SCHEMA_ACTION_CATALOG = Object.freeze({
  view: Object.freeze({ actionCode: 'view', actionName: '查看' }),
  edit: Object.freeze({ actionCode: 'edit', actionName: '编辑' }),
  delete: Object.freeze({ actionCode: 'delete', actionName: '删除' }),
  'toggle-status': Object.freeze({ actionCode: 'toggle-status', actionName: '停用' }),
})

function contractsAsArray(contracts = []) {
  return Array.isArray(contracts) ? contracts : Object.values(contracts || {})
}

export function normalizeListActionContract(contract = {}) {
  const actionCode = String(contract.actionCode || contract.code || '').trim()
  const actionName = String(contract.actionName || contract.label || '').trim()
  if (!actionCode || !actionName) throw new Error('LIST_ACTION_CONTRACT_CODE_AND_NAME_REQUIRED')
  const allowedStates = Object.freeze([...(contract.allowedStates || contract.allowedFromStates || ['*'])])
  return Object.freeze({ ...contract, actionCode, actionName, allowedStates })
}

export function resolveListRowState(row = {}, stateField = '') {
  return String((stateField && row[stateField]) || row.status || row.quoteStatus
    || row.comparisonStatus || row.preparationStatus || '')
}

export function resolveListRowActions({ contracts = [], row = {}, stateField = '', labelResolver = null } = {}) {
  const state = resolveListRowState(row, stateField)
  return Object.freeze(contractsAsArray(contracts).map(normalizeListActionContract).filter(contract => {
    if (contract.hidden === true || contract.visible === false) return false
    if (typeof contract.visibleWhen === 'function' && !contract.visibleWhen(row)) return false
    return contract.allowedStates.includes('*') || contract.allowedStates.includes(state)
  }).map(contract => Object.freeze({ ...contract,
    label: typeof labelResolver === 'function' ? labelResolver(row, contract) : contract.actionName,
    state, source: 'Action Contract' })))
}

export function createSchemaActionContracts(actionPolicy = []) {
  return Object.freeze((actionPolicy || []).map(action => {
    if (typeof action === 'object') return normalizeListActionContract(action)
    const contract = LIST_SCHEMA_ACTION_CATALOG[String(action)]
    if (!contract) throw new Error(`LIST_SCHEMA_ACTION_UNKNOWN:${action}`)
    return normalizeListActionContract(contract)
  }))
}

export function createListActionColumnRuntime(options = {}) {
  const contracts = contractsAsArray(options.contracts).map(normalizeListActionContract)
  return Object.freeze({ runtimeVersion: LIST_ACTION_COLUMN_RUNTIME_VERSION,
    actionSource: 'Action Contract', contracts: Object.freeze(contracts),
    resolve: row => resolveListRowActions({ ...options, contracts, row }) })
}
