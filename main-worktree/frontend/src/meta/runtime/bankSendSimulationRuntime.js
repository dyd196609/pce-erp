import {
  factLoadPassed,
  factLoadResultCount,
  readPceFactLoadEnvelope,
} from './pceFactLoadContract.js'
import { assertStatusTransitionCountMatchesHistory } from './pceStateMachineFactContract.js'

export const BANK_SEND_SIMULATION_VERSION = 'V1.14.2.8.4.7.64'
export const BANK_SEND_SIMULATION_MODULE = Object.freeze({
  pageCode: 'bank-send-simulation',
  moduleCode: 'FIN_BANK_SEND_SIMULATION',
  canonicalName: '银行发送执行模拟',
  route: '/finance/bank-send-simulations',
})
export const BANK_SEND_SIMULATION_FILTER_SCHEMA = Object.freeze([
  { field: 'simulationNo', key: 'simulationNo', label: '模拟编号', type: 'searchable_select' },
  { field: 'bankSendRequestNo', key: 'bankSendRequestNo', label: '来源发送请求', type: 'searchable_select' },
  {
    field: 'status', key: 'status', label: '业务状态', type: 'select',
    options: [
      { value: 'created', label: '已创建' },
      { value: 'validated', label: '校验通过' },
      { value: 'simulation_running', label: '模拟执行中' },
      { value: 'simulation_success', label: '模拟成功' },
      { value: 'simulation_failed', label: '模拟失败' },
    ],
  },
])
const STATUS_LABELS = Object.freeze({
  created: '已创建',
  validated: '校验通过',
  simulation_running: '模拟执行中',
  simulation_success: '模拟成功',
  simulation_failed: '模拟失败',
})
const COUNT_FIELDS = Object.freeze([
  'simulationCount', 'createdCount', 'validatedCount', 'runningCount',
  'successCount', 'failedCount', 'bankMessageSentCount',
  'paymentExecutionCount', 'fundsDebitCount', 'bankTransactionCount',
])

function assertCount(value, field) {
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(`bank-send-simulation:${field} is not a server count`)
  }
}

export function createBankSendSimulationPageFacts(envelope = {}) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(
    envelope, '/api/finance/bank-send-simulations/', 'bank-send-simulation',
  )
  const facts = data.simulationFacts
  if (facts?.factType !== 'BankSendExecutionSimulationFacts' || facts?.factSource !== 'server') {
    throw new Error('BankSendExecutionSimulationFacts missing')
  }
  COUNT_FIELDS.forEach(field => assertCount(facts[field], field))
  if (
    facts.bankMessageSentCount || facts.paymentExecutionCount
    || facts.fundsDebitCount || facts.bankTransactionCount
  ) {
    throw new Error('simulation execution boundary violated')
  }
  const rows = (Array.isArray(data.results) ? data.results : []).map(row => {
    if (row.statusLabel !== STATUS_LABELS[row.status]) {
      throw new Error(`simulation status label mismatch:${row.simulationNo}`)
    }
    if (['sent', 'executed'].includes(row.status)) {
      throw new Error(`forbidden simulation status:${row.status}`)
    }
    assertStatusTransitionCountMatchesHistory(row, `bank-send-simulation:${row.simulationNo}`)
    return row
  })
  if (rows.length !== facts.simulationCount) throw new Error('simulation count mismatch')
  const acceptanceFacts = {
    ...data.acceptanceFacts,
    factLoadContractVersion: facts.factLoadContractVersion,
    factLoadStatus: facts.factLoadStatus,
    apiUrl: facts.apiUrl,
    httpStatus: facts.httpStatus,
    tenantId: facts.tenantId,
    batchId: facts.batchId,
  }
  const strictServerFacts = {
    ...facts, factLoadFacts, pageCode: BANK_SEND_SIMULATION_MODULE.pageCode,
    moduleCode: BANK_SEND_SIMULATION_MODULE.moduleCode,
    pageFactOwner: BANK_SEND_SIMULATION_MODULE.moduleCode,
    pageFactOwnerGuard: 'page_fact_owner_unique',
    resultCount: factLoadResultCount(factLoadFacts, facts.simulationCount),
    passed: factLoadPassed(factLoadFacts, true),
    simulationFacts: facts, acceptanceFacts, rows,
  }
  return { facts, rows, factLoadFacts, acceptanceFacts, strictServerFacts }
}

