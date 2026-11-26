import {
  factLoadPassed,
  factLoadResultCount,
  readPceFactLoadEnvelope,
} from './pceFactLoadContract.js'
import { assertStatusTransitionCountMatchesHistory } from './pceStateMachineFactContract.js'

export const BANK_SEND_EXECUTION_GATE_VERSION = 'V1.14.2.8.4.7.60'
export const BANK_SEND_EXECUTION_GATE_MODULE = Object.freeze({
  pageCode: 'bank-send-execution-gate',
  moduleCode: 'FIN_BANK_SEND_EXECUTION_GATE',
  canonicalName: '银行发送执行授权',
  route: '/finance/bank-send-execution-gates',
})
export const BANK_SEND_EXECUTION_GATE_FILTER_SCHEMA = Object.freeze([
  { field: 'gateNo', key: 'gateNo', label: '授权编号', type: 'searchable_select' },
  { field: 'bankSendTaskNo', key: 'bankSendTaskNo', label: '来源银行发送任务', type: 'searchable_select' },
  { field: 'formalPaymentOrderNo', key: 'formalPaymentOrderNo', label: '来源正式付款单', type: 'searchable_select' },
  {
    field: 'status',
    key: 'status',
    label: '授权状态',
    type: 'select',
    options: Object.entries({
      pending_review: '待最终授权审核',
      approved: '授权审核通过',
      ready_for_execution: '执行前就绪',
    }).map(([value, label]) => ({ value, label })),
  },
])

const STATUS_LABELS = Object.freeze({
  pending_review: '待最终授权审核',
  approved: '授权审核通过',
  ready_for_execution: '执行前就绪',
})
const COUNT_FIELDS = Object.freeze([
  'gateCount',
  'pendingReviewCount',
  'approvedCount',
  'readyForExecutionCount',
  'executedCount',
  'bankSendExecutionCount',
  'bankMessageSentCount',
  'paymentExecutionCount',
])
const CANARY_FIELDS = Object.freeze([
  'normalPoolCount',
  'blockedPoolCount',
  'reservePoolCount',
  'createdGateCount',
  'blockedGateCount',
  'availablePoolCount',
])

function assertCount(value, name) {
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(`bank-send-execution-gate:${name} is not a server count`)
  }
}

export function executionGateDisplayValue(value) {
  if (value === true) return '是'
  if (value === false) return '否'
  if (value === null || value === undefined || value === '') return '-'
  return STATUS_LABELS[value] || String(value)
}

export function createBankSendExecutionGatePageFacts(envelope = {}) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(
    envelope,
    '/api/finance/bank-send-execution-gates/',
    'bank-send-execution-gate',
  )
  const facts = data.bankSendExecutionGateFacts
  if (
    facts?.factType !== 'BankSendExecutionGateFacts'
    || facts?.currentStateSource !== 'server'
  ) throw new Error('BankSendExecutionGateFacts missing')
  for (const field of COUNT_FIELDS) {
    assertCount(facts[field], field)
    if (data.capacity?.[field] !== facts[field]) {
      throw new Error(`${field} API mirror mismatch`)
    }
  }
  for (const field of CANARY_FIELDS) {
    assertCount(facts[field], field)
    if (data.canaryPoolFacts?.[field] !== facts[field]) {
      throw new Error(`${field} canary mirror mismatch`)
    }
  }
  if (
    facts.executedCount !== 0
    || facts.bankSendExecutionCount !== 0
    || facts.bankMessageSentCount !== 0
    || facts.paymentExecutionCount !== 0
  ) throw new Error('execution boundary violated')
  const rows = (Array.isArray(data.results) ? data.results : []).map(row => {
    if (
      row.statusCode !== row.status
      || row.statusLabel !== STATUS_LABELS[row.statusCode]
      || ['sent', 'executed'].includes(row.statusCode)
    ) throw new Error(`invalid gate status: ${row.gateNo}`)
    assertStatusTransitionCountMatchesHistory(
      row,
      `bank-send-execution-gate:${row.gateNo}`,
    )
    return row
  })
  if (rows.length !== facts.gateCount) throw new Error('gate count mismatch')
  const strictRows = rows.map(row => ({
    objectNo: row.gateNo,
    sourceObjectNo: row.bankSendTaskNo,
    formalPaymentOrderNo: row.formalPaymentOrderNo,
    status: row.status,
    statusCode: row.statusCode,
    statusLabel: row.statusLabel,
    statusTransitionHistory: row.statusTransitionHistory,
    statusTransitionCount: row.statusTransitionCount,
    stateMachineConsistent: row.stateMachineConsistent,
    stateTransitionGuard: row.stateTransitionGuard,
    authorizationChecks: row.authorizationChecks,
    writeIntentFacts: row.writeIntentFacts,
    currentStateSource: 'server',
  }))
  const strictServerFacts = {
    ...factLoadFacts,
    factLoadFacts,
    pageCode: BANK_SEND_EXECUTION_GATE_MODULE.pageCode,
    moduleCode: BANK_SEND_EXECUTION_GATE_MODULE.moduleCode,
    pageFactOwner: BANK_SEND_EXECUTION_GATE_MODULE.moduleCode,
    pageFactOwnerGuard: 'page_fact_owner_unique',
    currentStateSource: 'server',
    resultCount: factLoadResultCount(factLoadFacts, facts.gateCount),
    passed: factLoadPassed(factLoadFacts, facts.passed === true),
    currentObject: strictRows[0] || null,
    sourceObjects: data.sources || [],
    rows: strictRows,
    bankSendExecutionGateFacts: facts,
    canaryPoolFacts: data.canaryPoolFacts,
    downstreamCounts: data.downstreamCounts,
    writeIntentFacts: data.writeIntentFacts,
  }
  return {
    factLoadFacts,
    facts,
    rows,
    sources: data.sources || [],
    capacity: data.capacity,
    canaryPoolFacts: data.canaryPoolFacts,
    downstreamCounts: data.downstreamCounts,
    writeIntentFacts: data.writeIntentFacts,
    strictServerFacts,
  }
}
