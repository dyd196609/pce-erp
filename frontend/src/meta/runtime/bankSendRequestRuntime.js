import {
  factLoadPassed,
  factLoadResultCount,
  readPceFactLoadEnvelope,
} from './pceFactLoadContract.js'
import { assertStatusTransitionCountMatchesHistory } from './pceStateMachineFactContract.js'

export const BANK_SEND_REQUEST_VERSION = 'V1.14.2.8.4.7.61.1.1'
export const BANK_SEND_REQUEST_MODULE = Object.freeze({
  pageCode: 'bank-send-request',
  moduleCode: 'FIN_BANK_SEND_REQUEST',
  canonicalName: '银行发送请求准备',
  route: '/finance/bank-send-requests',
})
export const BANK_SEND_REQUEST_FILTER_SCHEMA = Object.freeze([
  { field: 'requestNo', key: 'requestNo', label: '请求编号', type: 'searchable_select' },
  { field: 'bankSendExecutionGateNo', key: 'bankSendExecutionGateNo', label: '来源授权编号', type: 'searchable_select' },
  { field: 'bankSendTaskNo', key: 'bankSendTaskNo', label: '来源银行发送任务', type: 'searchable_select' },
  {
    field: 'status', key: 'status', label: '当前状态', type: 'select',
    options: [
      { value: 'draft', label: '草稿' },
      { value: 'validated', label: '校验通过' },
      { value: 'ready_to_dispatch', label: '发送前待分发' },
    ],
  },
])
const STATUS_LABELS = Object.freeze({
  draft: '草稿',
  validated: '校验通过',
  ready_to_dispatch: '发送前待分发',
})
const COUNT_FIELDS = Object.freeze([
  'requestCount', 'draftCount', 'validatedCount', 'readyToDispatchCount',
  'bankMessageSentCount', 'paymentExecutionCount', 'fundsDebitCount',
])
const CANARY_FIELDS = Object.freeze([
  'normalPoolCount', 'blockedPoolCount', 'reservePoolCount',
  'createdRequestCount', 'blockedRequestCount', 'availablePoolCount',
])

function count(value, name) {
  if (!Number.isInteger(value) || value < 0) throw new Error(`bank-send-request:${name} is not a server count`)
}
export function bankSendRequestDisplayValue(value) {
  if (value === true) return '是'
  if (value === false) return '否'
  if (value === null || value === undefined || value === '') return '-'
  return STATUS_LABELS[value] || String(value)
}
export function createBankSendRequestPageFacts(envelope = {}) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(
    envelope, '/api/finance/bank-send-requests/', 'bank-send-request',
  )
  const facts = data.bankSendRequestFacts
  if (facts?.factType !== 'BankSendRequestFacts' || facts?.currentStateSource !== 'server') {
    throw new Error('BankSendRequestFacts missing')
  }
  for (const field of COUNT_FIELDS) {
    count(facts[field], field)
    if (data.capacity?.[field] !== facts[field]) throw new Error(`${field} API mirror mismatch`)
  }
  for (const field of CANARY_FIELDS) {
    count(facts[field], field)
    if (data.canaryPoolFacts?.[field] !== facts[field]) throw new Error(`${field} canary mirror mismatch`)
  }
  if (facts.bankMessageSentCount || facts.paymentExecutionCount || facts.fundsDebitCount) {
    throw new Error('send boundary violated')
  }
  const rows = (Array.isArray(data.results) ? data.results : []).map(row => {
    if (row.statusLabel !== STATUS_LABELS[row.status] || ['sent', 'executed'].includes(row.status)) {
      throw new Error(`invalid request status:${row.requestNo}`)
    }
    assertStatusTransitionCountMatchesHistory(row, `bank-send-request:${row.requestNo}`)
    return row
  })
  if (rows.length !== facts.requestCount) throw new Error('request count mismatch')
  const strictServerFacts = {
    ...factLoadFacts, factLoadFacts,
    pageCode: BANK_SEND_REQUEST_MODULE.pageCode,
    moduleCode: BANK_SEND_REQUEST_MODULE.moduleCode,
    pageFactOwner: BANK_SEND_REQUEST_MODULE.moduleCode,
    pageFactOwnerGuard: 'page_fact_owner_unique',
    currentStateSource: 'server',
    resultCount: factLoadResultCount(factLoadFacts, facts.requestCount),
    passed: factLoadPassed(factLoadFacts, facts.passed === true),
    currentObject: rows[0] || null,
    sourceObjects: data.sources || [],
    rows,
    bankSendRequestFacts: facts,
    canaryPoolFacts: data.canaryPoolFacts,
    downstreamCounts: data.downstreamCounts,
    writeIntentFacts: data.writeIntentFacts,
  }
  return {
    factLoadFacts, facts, rows, sources: data.sources || [],
    capacity: data.capacity, canaryPoolFacts: data.canaryPoolFacts,
    downstreamCounts: data.downstreamCounts,
    writeIntentFacts: data.writeIntentFacts, strictServerFacts,
  }
}
