export const BANK_SEND_PRODUCTION_RELEASE_VERSION = 'V1.14.2.8.4.7.67'

export const ISOLATION_FILTER_SCHEMA = Object.freeze([
  { field: 'checkNo', key: 'checkNo', label: '检查编号', type: 'searchable_select' },
  { field: 'traceNo', key: 'traceNo', label: '链路编号', type: 'searchable_select' },
  { field: 'approvalNo', key: 'approvalNo', label: '最终审批编号', type: 'searchable_select' },
  {
    field: 'result', key: 'result', label: '检查结果', type: 'select',
    options: [
      { value: 'passed', label: '隔离检查通过' },
      { value: 'failed', label: '隔离检查失败' },
    ],
  },
])

export const REVIEW_FILTER_SCHEMA = Object.freeze([
  { field: 'reviewNo', key: 'reviewNo', label: '评审编号', type: 'searchable_select' },
  { field: 'traceNo', key: 'traceNo', label: '链路编号', type: 'searchable_select' },
  { field: 'approvalNo', key: 'approvalNo', label: '最终审批编号', type: 'searchable_select' },
  {
    field: 'status', key: 'status', label: '评审状态', type: 'select',
    options: [
      { value: 'draft', label: '评审草稿' },
      { value: 'reviewing', label: '评审中' },
      { value: 'review_passed', label: '生产评审通过' },
      { value: 'locked', label: '生产评审已锁定' },
    ],
  },
])

function assertFacts(payload, factKey, factType) {
  const envelope = payload?.success === true ? payload.data : payload
  const data = envelope?.data
  const facts = data?.[factKey]
  if (!facts || facts.factType !== factType || facts.factSource !== 'server') {
    throw new Error(`${factType} missing`)
  }
  if (facts.factLoadStatus !== 'success') throw new Error(`${factType} read failed`)
  const rows = Array.isArray(data.results) ? data.results : []
  const counts = [
    rows.length,
    facts.recordCount,
    data.diagnosticFacts?.recordCount,
    data.strictFacts?.recordCount,
    data.acceptanceFacts?.recordCount,
  ]
  if (new Set(counts).size !== 1) throw new Error(`${factType} five-surface mismatch`)
  if (
    data.acceptanceFacts?.factSource !== 'server'
    || data.acceptanceFacts?.acceptanceStatus !== 'PASS'
    || data.acceptanceFacts?.unknownReason !== ''
  ) throw new Error(`${factType} acceptance failed`)
  return {
    rows,
    facts,
    diagnosticFacts: data.diagnosticFacts,
    strictFacts: data.strictFacts,
    acceptanceFacts: data.acceptanceFacts,
  }
}

export function createDualIsolationPageFacts(payload) {
  const loaded = assertFacts(
    payload, 'isolationFacts', 'BankSendDualIsolationCheckFacts',
  )
  if (loaded.rows.some(row => (
    row.factSource !== 'server'
    || row.result !== 'passed'
    || !row.environmentCheck
    || !row.credentialCheck
    || !row.permissionCheck
    || !row.interfaceCheck
  ))) throw new Error('dual isolation boundary violated')
  return loaded
}

export function createProductionReleaseReviewPageFacts(payload) {
  const loaded = assertFacts(
    payload, 'reviewFacts', 'BankSendProductionReleaseReviewFacts',
  )
  if (loaded.rows.some(row => (
    row.productionReviewMeansSent !== false
    || row.bankSent !== false
    || row.status === 'sent'
    || row.status === 'send_allowed'
    || row.stateMachineConsistent !== true
  ))) throw new Error('production release review boundary violated')
  return loaded
}
