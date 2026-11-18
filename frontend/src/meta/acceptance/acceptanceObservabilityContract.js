export const PCE_ACCEPTANCE_OBSERVABILITY_CONTRACT_VERSION =
  'PCE-ACCEPTANCE-OBSERVABILITY-CONTRACT-V1.0'

export const ACCEPTANCE_FACT_FIELDS = Object.freeze([
  'pageCode',
  'factSource',
  'recordCount',
  'selectedCount',
  'actionCount',
  'dangerActionCount',
  'businessProgressWriteCount',
  'downstreamObjectCount',
])

const DANGEROUS_ACTION_CODES = Object.freeze([
  'send-bank',
  'submit-bank',
  'execute-bank-send',
  'bank-send-execution',
  'execute-payment',
  'debit-funds',
  'create-bank-transaction',
  'write-general-ledger',
  'post-ledger',
])

export function summarizeAcceptanceActions(actions = []) {
  const normalized = Array.isArray(actions) ? actions : []
  return {
    actionCount: normalized.length,
    dangerActionCount: normalized.filter(action => (
      DANGEROUS_ACTION_CODES.includes(action.actionId || action.actionCode)
    )).length,
  }
}

function nullableCount(value, field) {
  if (value === null && field === 'recordCount') return null
  const number = Number(value)
  if (!Number.isInteger(number) || number < 0) {
    throw new Error(`acceptanceFacts.${field} must be a non-negative integer`)
  }
  return number
}

export function createAcceptanceFacts(input = {}) {
  for (const field of ACCEPTANCE_FACT_FIELDS) {
    if (!Object.hasOwn(input, field)) {
      throw new Error(`acceptanceFacts missing ${field}`)
    }
  }
  const facts = {
    contractVersion: PCE_ACCEPTANCE_OBSERVABILITY_CONTRACT_VERSION,
    factLoadContractVersion: String(input.factLoadContractVersion || ''),
    factLoadStatus: String(input.factLoadStatus || 'success'),
    apiUrl: String(input.apiUrl || ''),
    httpStatus: Number(input.httpStatus || 200),
    loadedAt: String(input.loadedAt || ''),
    tenantId: String(input.tenantId || ''),
    batchId: String(input.batchId || ''),
    errorCode: String(input.errorCode || ''),
    errorMessage: String(input.errorMessage || ''),
    pageCode: String(input.pageCode || '').trim(),
    factSource: input.factSource || 'server',
    recordCount: nullableCount(input.recordCount, 'recordCount'),
    selectedCount: nullableCount(input.selectedCount || 0, 'selectedCount'),
    actionCount: nullableCount(input.actionCount || 0, 'actionCount'),
    dangerActionCount: nullableCount(input.dangerActionCount || 0, 'dangerActionCount'),
    businessProgressWriteCount: nullableCount(
      input.businessProgressWriteCount || 0,
      'businessProgressWriteCount',
    ),
    downstreamObjectCount: nullableCount(
      input.downstreamObjectCount || 0,
      'downstreamObjectCount',
    ),
    recordCountUnavailableReason: String(input.recordCountUnavailableReason || ''),
    fieldSources: { ...(input.fieldSources || {}) },
  }
  if (!facts.pageCode) throw new Error('acceptanceFacts.pageCode is required')
  if (facts.factSource !== 'server') {
    throw new Error('acceptanceFacts.factSource must be server')
  }
  if (facts.recordCount === null && !facts.recordCountUnavailableReason) {
    if (facts.factLoadStatus !== 'read_failed') {
      throw new Error('nullable recordCount requires read_failed or recordCountUnavailableReason')
    }
  }
  if (facts.factLoadStatus === 'read_failed' && (
    !facts.errorCode || !facts.errorMessage || facts.recordCount !== null
  )) {
    throw new Error('read_failed requires null recordCount, errorCode and errorMessage')
  }
  return Object.freeze(facts)
}

export function assertAcceptanceFacts(value) {
  for (const field of ACCEPTANCE_FACT_FIELDS) {
    if (!Object.hasOwn(value || {}, field)) {
      throw new Error(`acceptanceFacts missing ${field}`)
    }
  }
  return createAcceptanceFacts(value)
}
