import {
  PCE_FILTER_DISPLAY_MAP,
  createPceAdvancedFilterSchema,
  displayPceFilterValue,
} from './pceAdvancedFilterContract.js'
import { assertStatusTransitionCountMatchesHistory } from './pceStateMachineFactContract.js'
import { assertWriteIntentFacts } from './pceWriteIntentContract.js'
import {
  factLoadPassed,
  factLoadResultCount,
  readPceFactLoadEnvelope,
} from './pceFactLoadContract.js'

export const BANK_SEND_TASK_VERSION = 'V1.14.2.8.4.7.59.1.1'

export const BANK_SEND_TASK_MODULE = Object.freeze({
  pageCode: 'bank-send-task',
  moduleCode: 'FIN_BANK_SEND_TASK',
  canonicalName: '银行发送任务',
  sourceDocumentType: 'bankSendPreparation',
  route: '/finance/bank-send-tasks',
  previousModuleCode: 'bank-send-preparation',
  previousCanonicalName: '银行发送准备',
  nextModuleCode: 'bank-send-execution',
  nextCanonicalName: '银行发送（未开放）',
})

export const BANK_SEND_TASK_FILTER_SCHEMA =
  createPceAdvancedFilterSchema([
    { field: 'taskNo', label: '银行发送任务编号', type: 'select' },
    {
      field: 'sourcePreparationNo',
      label: '来源银行发送准备编号',
      type: 'select',
    },
    {
      field: 'status',
      label: '任务状态',
      type: 'select',
      displayMap: {
        ...PCE_FILTER_DISPLAY_MAP,
        prepared: '已准备',
        queued: '已进入发送队列',
        ready_to_send: '发送前就绪',
      },
      options: [
        { value: 'prepared', label: '已准备' },
        { value: 'queued', label: '已进入发送队列' },
        { value: 'ready_to_send', label: '发送前就绪' },
      ],
    },
    { field: 'supplierName', label: '供应商', type: 'select' },
    { field: 'legalEntityId', label: '法人', type: 'select' },
    { field: 'currency', label: '币种', type: 'select' },
    {
      field: 'executionDateFrom',
      label: '计划执行日期起',
      type: 'dateRange',
      sourceKey: 'plannedExecutionDate',
    },
    {
      field: 'executionDateTo',
      label: '计划执行日期止',
      type: 'dateRange',
      sourceKey: 'plannedExecutionDate',
    },
  ])

const labels = Object.freeze({
  ...PCE_FILTER_DISPLAY_MAP,
  prepared: '已准备',
  queued: '已进入发送队列',
  ready_to_send: '发送前就绪',
  preview_only: '仅预览',
  committed: '已提交',
  consumed: '已使用',
  server: '服务端',
})

export function bankSendTaskDisplayValue(value) {
  if (value === true) return '是'
  if (value === false) return '否'
  if (Array.isArray(value)) return value.length ? value.join('；') : '无'
  if (value === null || value === undefined || value === '') return '-'
  return labels[String(value)] || displayPceFilterValue(value) || String(value)
}

const COUNT_FIELDS = Object.freeze([
  'sourceBankSendPreparationCount',
  'previewReadySourceCount',
  'bankSendTaskCount',
  'taskCount',
  'preparedCount',
  'queuedCount',
  'readyToSendCount',
  'sentCount',
  'executionCount',
])
const CANARY_COUNT_FIELDS = Object.freeze([
  'normalPoolCount',
  'blockedPoolCount',
  'reservePoolCount',
  'createdTaskCount',
  'blockedTaskCount',
  'availablePoolCount',
])
const SERVER_STATUS_LABELS = Object.freeze({
  prepared: '已准备',
  queued: '已进入发送队列',
  ready_to_send: '发送前就绪',
})

function assertCount(facts, field) {
  if (!Number.isInteger(facts?.[field]) || facts[field] < 0) {
    throw new Error(
      `bank-send-task:api:${field} must be a server-derived non-negative integer`,
    )
  }
}

function assertBankSendTaskFacts(data) {
  const facts = data?.bankSendTaskFacts
  if (
    facts?.factType !== 'BankSendTaskFacts'
    || facts?.currentStateSource !== 'server'
  ) {
    throw new Error('bank-send-task:api: BankSendTaskFacts is missing')
  }
  for (const field of COUNT_FIELDS) {
    assertCount(facts, field)
    if (
      data[field] !== facts[field]
      || data.capacity?.[field] !== facts[field]
    ) {
      throw new Error(
        `bank-send-task:api:${field} fact mirrors are inconsistent`,
      )
    }
  }
  for (const field of CANARY_COUNT_FIELDS) {
    assertCount(facts, field)
  }
  if (
    data.count !== facts.bankSendTaskCount
    || facts.taskCount !== facts.bankSendTaskCount
    || facts.sentCount !== 0
    || facts.executionCount !== 0
    || JSON.stringify(data.writeIntentFacts)
      !== JSON.stringify(facts.writeIntentFacts)
  ) {
    throw new Error('bank-send-task:api: fact mirrors are inconsistent')
  }
  const writeFacts = assertWriteIntentFacts(
    facts.writeIntentFacts,
    'bank-send-task:api:BankSendTaskFacts',
  )
  if (
    writeFacts.bankSendExecutionWriteCount !== 0
    || writeFacts.bankSendExecutionWriteBlocked !== true
  ) {
    throw new Error('bank-send-task:api: bank send execution write detected')
  }
  return facts
}

export function createBankSendTaskPageFacts(apiEnvelope = {}) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(
    apiEnvelope,
    '/api/finance/bank-send-tasks/',
    'bank-send-task',
  )
  const bankSendTaskFacts = assertBankSendTaskFacts(data)
  const canaryPoolFacts = data.canaryPoolFacts
  if (
    canaryPoolFacts?.factType !== 'BankSendTaskCanaryFacts'
    || canaryPoolFacts?.currentStateSource !== 'server'
  ) {
    throw new Error('bank-send-task:api: BankSendTaskCanaryFacts is missing')
  }
  for (const field of CANARY_COUNT_FIELDS) {
    assertCount(canaryPoolFacts, field)
    if (bankSendTaskFacts[field] !== canaryPoolFacts[field]) {
      throw new Error(
        `bank-send-task:api:${field} fact mirrors are inconsistent`,
      )
    }
  }
  if (
    bankSendTaskFacts.factLoadStatus !== factLoadFacts.factLoadStatus
    || bankSendTaskFacts.apiUrl !== factLoadFacts.apiUrl
    || bankSendTaskFacts.tenantId !== factLoadFacts.tenantId
    || bankSendTaskFacts.batchId !== factLoadFacts.batchId
  ) {
    throw new Error(
      'bank-send-task:api: fact load mirrors are inconsistent',
    )
  }
  const rows = (Array.isArray(data.results) ? data.results : []).map(row => {
    if (
      row.statusCode !== row.status
      || row.statusLabel !== SERVER_STATUS_LABELS[row.statusCode]
      || row.statusCode === 'sent'
    ) {
      throw new Error(
        `bank-send-task:api:${row.taskNo || row.id}: server status label is inconsistent`,
      )
    }
    assertStatusTransitionCountMatchesHistory(
      row,
      `bank-send-task:api:${row.taskNo || row.id || 'unknown'}`,
    )
    assertWriteIntentFacts(
      row.writeIntentFacts,
      `bank-send-task:row:${row.taskNo || row.id || 'unknown'}`,
    )
    return row
  })
  const sources = Array.isArray(data.sources) ? data.sources : []
  if (
    sources.length !== bankSendTaskFacts.sourceBankSendPreparationCount
  ) {
    throw new Error('bank-send-task:api: source facts are inconsistent')
  }
  const capacity = Object.fromEntries(
    COUNT_FIELDS.map(field => [field, bankSendTaskFacts[field]]),
  )
  const currentObject = rows[0] || null
  const strictRows = rows.map(row => ({
    objectNo: row.taskNo,
    sourceObjectNo: row.sourcePreparationNo,
    scenarioCode: row.sourceFormalPaymentOrderNo,
    status: row.status,
    statusCode: row.statusCode,
    statusLabel: row.statusLabel,
    batchId: row.batchId,
    statusTransitionHistory: row.statusTransitionHistory,
    statusTransitionCount: row.statusTransitionCount,
    stateMachineConsistent: row.stateMachineConsistent === true,
    stateTransitionGuard: row.stateTransitionGuard,
    messagePreviewStatus: row.messagePreview?.status || '',
    idempotencyStatus: row.idempotencyStatus,
    numberReservationStatus: row.numberReservationStatus,
    transactionStatus: row.transactionStatus,
    writeIntentFacts: row.writeIntentFacts,
    bankSendExecuted: false,
    paymentExecuted: false,
    currentStateSource: 'server',
  }))
  const strictServerFacts = {
    ...factLoadFacts,
    factLoadFacts,
    currentStateSource: 'server',
    tenantId: factLoadFacts.tenantId,
    batchId: factLoadFacts.batchId,
    pageCode: BANK_SEND_TASK_MODULE.pageCode,
    moduleCode: BANK_SEND_TASK_MODULE.moduleCode,
    pageFactOwner: BANK_SEND_TASK_MODULE.moduleCode,
    pageFactOwnerGuard: 'page_fact_owner_unique',
    resultCount: factLoadResultCount(
      factLoadFacts,
      bankSendTaskFacts.taskCount,
    ),
    passed: factLoadPassed(
      factLoadFacts,
      bankSendTaskFacts.passed === true,
    ),
    currentObject: strictRows[0] || null,
    sourceObjects: sources.map(source => ({
      id: source.id,
      objectNo: source.prepareNo,
      sourceDocumentType: 'bankSendPreparation',
      status: source.status,
      eligible: source.taskEligibility?.eligible === true,
    })),
    status: currentObject?.status || '',
    statusTransitionHistory:
      currentObject?.statusTransitionHistory || [],
    statusTransitionCount:
      currentObject?.statusTransitionCount ?? 0,
    stateMachineConsistent:
      currentObject?.stateMachineConsistent === true,
    downstreamCounts: data.downstreamCounts || {},
    writeIntentFacts: bankSendTaskFacts.writeIntentFacts,
    bankSendTaskFacts,
    canaryPoolFacts,
    rows: strictRows,
  }
  if (currentObject) {
    assertStatusTransitionCountMatchesHistory(
      strictServerFacts,
      'bank-send-task:strictServerFacts',
    )
  }
  return {
    version: BANK_SEND_TASK_VERSION,
    canonicalName: BANK_SEND_TASK_MODULE.canonicalName,
    currentStateSource: 'server',
    ...factLoadFacts,
    factLoadFacts,
    rows,
    sources,
    capacity,
    downstreamCounts: data.downstreamCounts || {},
    writeIntentFacts: bankSendTaskFacts.writeIntentFacts,
    bankSendTaskFacts,
    canaryPoolFacts,
    currentObject,
    resultCount: factLoadResultCount(
      factLoadFacts,
      bankSendTaskFacts.taskCount,
    ),
    passed: factLoadPassed(
      factLoadFacts,
      bankSendTaskFacts.passed === true,
    ),
    strictServerFacts,
    bankSendExecutionEnabled: data.bankSendExecutionEnabled === true,
    productionRolloutEnabled: data.productionRolloutEnabled === true,
  }
}
