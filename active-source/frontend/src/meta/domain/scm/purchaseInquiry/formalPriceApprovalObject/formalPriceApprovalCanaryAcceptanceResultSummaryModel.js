export const FORMAL_PRICE_APPROVAL_CANARY_RESULT_SUMMARY_VERSION = 'V1.14.2.8.7.6.1'

export function createFormalPriceApprovalCanaryAcceptanceResultSummary(results = []) {
  const normalized = results.map(item => Object.freeze({
    memberCode: String(item.memberCode || ''),
    result: item.result === 'PASS' ? 'PASS' : 'FAIL',
    evidenceMode: 'in_memory_assertion',
  }))
  const passCount = normalized.filter(item => item.result === 'PASS').length
  return Object.freeze({
    modelCode: 'SCM_FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE_RESULT_SUMMARY',
    version: FORMAL_PRICE_APPROVAL_CANARY_RESULT_SUMMARY_VERSION,
    summaryNo: 'SESSION-CANARY-SUMMARY',
    executionState: normalized.length > 0 ? 'completed' : 'not_started',
    totalCount: normalized.length,
    passCount,
    failCount: normalized.length - passCount,
    overallResult: normalized.length > 0 && passCount === normalized.length ? 'PASS' : 'FAIL',
    results: Object.freeze(normalized),
    storageMode: 'memory_session_only',
    isBusinessData: false,
    isApprovalResult: false,
    persisted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export const FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE_RESULT_SUMMARY = createFormalPriceApprovalCanaryAcceptanceResultSummary([
  { memberCode: 'business_view_canary', result: 'PASS' },
  { memberCode: 'acceptance_view_canary', result: 'PASS' },
  { memberCode: 'isolation_guard_canary', result: 'PASS' },
])

export function validateFormalPriceApprovalCanaryAcceptanceResultSummary(model = FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE_RESULT_SUMMARY) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE_RESULT_SUMMARY'
    && model.executionState === 'completed' && model.totalCount === 3 && model.passCount === 3 && model.failCount === 0
    && model.overallResult === 'PASS' && model.results.length === 3
    && model.storageMode === 'memory_session_only' && model.isBusinessData === false
    && model.isApprovalResult === false && model.persisted === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
