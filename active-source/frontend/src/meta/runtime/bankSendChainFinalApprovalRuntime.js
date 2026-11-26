export const BANK_SEND_CHAIN_FINAL_APPROVAL_VERSION = 'V1.14.2.8.4.7.66'

export const TRACE_FILTER_SCHEMA = Object.freeze([
  { field: 'traceNo', key: 'traceNo', label: '追踪编号', type: 'searchable_select' },
  { field: 'formalPaymentOrderNo', key: 'formalPaymentOrderNo', label: '正式付款单', type: 'searchable_select' },
  { field: 'bankSendRequestNo', key: 'bankSendRequestNo', label: '发送请求', type: 'searchable_select' },
  { field: 'simulationNo', key: 'simulationNo', label: '模拟编号', type: 'searchable_select' },
])

export const APPROVAL_FILTER_SCHEMA = Object.freeze([
  { field: 'approvalNo', key: 'approvalNo', label: '审批编号', type: 'searchable_select' },
  { field: 'traceNo', key: 'traceNo', label: '链路编号', type: 'searchable_select' },
  { field: 'requestNo', key: 'requestNo', label: '请求编号', type: 'searchable_select' },
  {
    field: 'status', key: 'status', label: '审批状态', type: 'select',
    options: [
      { value: 'pending', label: '待审批' },
      { value: 'first_approved', label: '第一审批通过' },
      { value: 'second_approved', label: '第二审批通过' },
      { value: 'final_locked', label: '最终审批已锁定' },
    ],
  },
])

function assertServerFacts(payload, factKey, factType) {
  const envelope = payload?.success === true ? payload.data : payload
  const data = envelope?.data
  const facts = data?.[factKey]
  if (!facts || facts.factType !== factType || facts.factSource !== 'server') {
    throw new Error(`${factType} missing`)
  }
  if (facts.factLoadStatus !== 'success') throw new Error(`${factType} read failed`)
  const rows = Array.isArray(data.results) ? data.results : []
  if (rows.length !== facts.recordCount) throw new Error(`${factType} count mismatch`)
  for (const key of ['diagnosticFacts', 'strictFacts']) {
    if (data[key]?.recordCount !== facts.recordCount) {
      throw new Error(`${factType} ${key} mismatch`)
    }
  }
  if (
    data.acceptanceFacts?.recordCount !== facts.recordCount
    || data.acceptanceFacts?.factSource !== 'server'
    || data.acceptanceFacts?.pageAcceptanceContractVersion
      !== 'PCE-PAGE-ACCEPTANCE-CONTRACT-V2.0'
    || data.acceptanceFacts?.acceptanceStatus !== 'PASS'
    || data.acceptanceFacts?.unknownReason !== ''
  ) {
    throw new Error(`${factType} acceptance mismatch`)
  }
  return {
    rows,
    facts,
    diagnosticFacts: data.diagnosticFacts,
    strictFacts: data.strictFacts,
    acceptanceFacts: data.acceptanceFacts,
  }
}

export function createChainTracePageFacts(payload) {
  const loaded = assertServerFacts(
    payload, 'traceFacts', 'BankSendChainTraceFacts',
  )
  if (loaded.rows.some(row => (
    row.traceComplete !== true
    || row.traceSource !== 'server'
    || row.nodeCount !== 8
    || row.missingNodeCount !== 0
    || row.nodes.some((node, index) => (
      node.order !== index + 1 || node.source !== 'server' || !node.businessNo
    ))
  ))) {
    throw new Error('bank send chain trace completeness violated')
  }
  return loaded
}

export function createFinalApprovalPageFacts(payload) {
  const loaded = assertServerFacts(
    payload, 'approvalFacts', 'BankSendFinalApprovalFacts',
  )
  if (loaded.rows.some(row => (
    row.finalApprovalMeansSent !== false
    || row.bankSent !== false
    || row.status === 'sent'
    || row.status === 'approved_to_send'
    || row.stateMachineConsistent !== true
  ))) {
    throw new Error('bank send final approval boundary violated')
  }
  return loaded
}
