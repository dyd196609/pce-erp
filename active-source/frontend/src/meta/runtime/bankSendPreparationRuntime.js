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

export const BANK_SEND_PREPARATION_VERSION = 'V1.14.2.8.4.7.58.1.4'

export const BANK_SEND_PREPARATION_MODULE = Object.freeze({
  pageCode: 'bank-send-preparation',
  moduleCode: 'bank-send-preparation',
  canonicalName: '银行发送准备',
  sourceDocumentType: 'formalPaymentOrder',
  route: '/finance/bank-send-prepares',
  previousModuleCode: 'formal-payment-order',
  previousCanonicalName: '正式付款单',
  nextModuleCode: 'bank-send-task',
  nextCanonicalName: '银行发送任务（未开放）',
})

export const BANK_SEND_PREPARATION_FILTER_SCHEMA =
  createPceAdvancedFilterSchema([
    { field: 'prepareNo', label: '银行发送准备编号', type: 'select' },
    {
      field: 'sourceFormalPaymentOrderNo',
      label: '来源正式付款单编号',
      type: 'select',
    },
    {
      field: 'status',
      label: '准备状态',
      type: 'select',
      displayMap: {
        ...PCE_FILTER_DISPLAY_MAP,
        prepared: '已准备',
      },
      options: [{ value: 'prepared', label: '已准备' }],
    },
    { field: 'supplierName', label: '供应商', type: 'select' },
    { field: 'legalEntityId', label: '法人', type: 'select' },
    { field: 'currency', label: '币种', type: 'select' },
    {
      field: 'previewStatus',
      label: '报文预览状态',
      type: 'select',
      options: [
        { value: 'not_generated', label: '未生成' },
        { value: 'preview_only', label: '仅预览' },
      ],
    },
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
  preview_only: '仅预览',
  not_generated: '未生成',
  available: '可用',
  server: '服务端',
})

export function bankSendPreparationDisplayValue(value) {
  if (value === true) return '是'
  if (value === false) return '否'
  if (Array.isArray(value)) return value.length ? value.join('；') : '无'
  if (value === null || value === undefined || value === '') return '-'
  return labels[String(value)] || displayPceFilterValue(value) || String(value)
}

const BANK_SEND_PREPARATION_COUNT_FIELDS = Object.freeze([
  'sourceFormalPaymentOrderCount',
  'bankSendPreparationCount',
  'preparedCount',
  'eligibleCount',
  'previewCount',
  'nextStageConsumedCount',
])

function assertServerCount(facts, field) {
  if (!Number.isInteger(facts?.[field]) || facts[field] < 0) {
    throw new Error(
      `bank-send-preparation:api:${field} must be a server-derived non-negative integer`,
    )
  }
}

function assertBankSendPreparationFacts(data) {
  const facts = data?.bankSendPreparationFacts
  if (
    facts?.factType !== 'BankSendPreparationFacts'
    || facts?.currentStateSource !== 'server'
  ) {
    throw new Error(
      'bank-send-preparation:api: BankSendPreparationFacts is missing',
    )
  }
  for (const field of BANK_SEND_PREPARATION_COUNT_FIELDS) {
    assertServerCount(facts, field)
    if (
      data[field] !== facts[field]
      || data.capacity?.[field] !== facts[field]
    ) {
      throw new Error(
        `bank-send-preparation:api:${field} fact mirrors are inconsistent`,
      )
    }
  }
  if (
    data.count !== facts.bankSendPreparationCount
    || JSON.stringify(data.writeIntentFacts)
      !== JSON.stringify(facts.writeIntentFacts)
  ) {
    throw new Error(
      'bank-send-preparation:api: fact mirrors are inconsistent',
    )
  }
  assertWriteIntentFacts(
    facts.writeIntentFacts,
    'bank-send-preparation:api:BankSendPreparationFacts',
  )
  return facts
}

export function createBankSendPreparationPageFacts(apiEnvelope = {}) {
  const { data, factLoadFacts } = readPceFactLoadEnvelope(
    apiEnvelope,
    '/api/finance/bank-send-prepares/',
    'bank-send-preparation',
  )
  const bankSendPreparationFacts = assertBankSendPreparationFacts(data)
  if (
    bankSendPreparationFacts.factLoadStatus
      !== factLoadFacts.factLoadStatus
    || bankSendPreparationFacts.apiUrl !== factLoadFacts.apiUrl
    || bankSendPreparationFacts.tenantId !== factLoadFacts.tenantId
    || bankSendPreparationFacts.batchId !== factLoadFacts.batchId
  ) {
    throw new Error(
      'bank-send-preparation:api: fact load mirrors are inconsistent',
    )
  }
  const writeIntentFacts = bankSendPreparationFacts.writeIntentFacts
  const rows = (Array.isArray(data.results) ? data.results : []).map(row => {
    assertStatusTransitionCountMatchesHistory(
      row,
      `bank-send-preparation:api:${row.prepareNo || row.id || 'unknown'}`,
    )
    return {
      ...row,
      previewStatus: row.messagePreview?.status || 'not_generated',
    }
  })
  const capacity = Object.fromEntries(
    BANK_SEND_PREPARATION_COUNT_FIELDS.map(field => [
      field,
      bankSendPreparationFacts[field],
    ]),
  )
  const strictRows = rows.map(row => ({
    objectNo: row.prepareNo,
    sourceObjectNo: row.sourceFormalPaymentOrderNo,
    sourceDocumentType: row.sourceDocumentType,
    status: row.status,
    statusTransitionCount: row.statusTransitionCount,
    statusTransitionHistory: row.statusTransitionHistory,
    stateMachineConsistent: row.stateMachineConsistent === true,
    gateEligible: row.gate?.eligible === true,
    freezeHashPassed: row.gate?.freezeHashPassed === true,
    bankInterfaceAvailable: row.gate?.bankInterfaceAvailable === true,
    signingCapabilityReady: row.gate?.signingCapabilityReady === true,
    previewStatus: row.messagePreview?.status || 'not_generated',
    writeIntentFacts: assertWriteIntentFacts(
      row.writeIntentFacts,
      `bank-send-preparation:row:${row.prepareNo || row.id || 'unknown'}`,
    ),
    bankSendTaskCreated: row.writeIntentFacts.bankSendTaskCreated === true,
    bankSendCreated: row.writeIntentFacts.bankSendCreated === true,
    paymentExecuted: false,
    currentStateSource: 'server',
  }))
  const currentObject = rows[0] || null
  const strictServerFacts = {
    ...factLoadFacts,
    factLoadFacts,
    currentStateSource: 'server',
    tenantId: factLoadFacts.tenantId,
    batchId: factLoadFacts.batchId,
    pageCode: BANK_SEND_PREPARATION_MODULE.pageCode,
    resultCount: factLoadResultCount(
      factLoadFacts,
      bankSendPreparationFacts.bankSendPreparationCount,
    ),
    passed: factLoadPassed(
      factLoadFacts,
      bankSendPreparationFacts.passed === true,
    ),
    currentObject: strictRows[0] || null,
    sourceObjects: rows.map(row => ({
      id: row.sourceFormalPaymentOrderId,
      objectNo: row.sourceFormalPaymentOrderNo,
      sourceDocumentType: 'formalPaymentOrder',
      status: 'frozen_for_execution',
    })),
    status: currentObject?.status || '',
    statusTransitionHistory: currentObject?.statusTransitionHistory || [],
    statusTransitionCount: currentObject?.statusTransitionCount || 0,
    stateMachineConsistent:
      currentObject?.stateMachineConsistent === true,
    gate: currentObject?.gate || {},
    eligibility: currentObject?.eligibility || {},
    messagePreview: currentObject?.messagePreview || {},
    downstreamCounts: data.downstreamCounts || {},
    writeIntentFacts,
    bankSendPreparationFacts,
    rows: strictRows,
  }
  if (currentObject) {
    assertStatusTransitionCountMatchesHistory(
      strictServerFacts,
      'bank-send-preparation:strictServerFacts',
    )
  }
  return {
    version: BANK_SEND_PREPARATION_VERSION,
    canonicalName: BANK_SEND_PREPARATION_MODULE.canonicalName,
    currentStateSource: 'server',
    ...factLoadFacts,
    factLoadFacts,
    rows,
    capacity,
    downstreamCounts: data.downstreamCounts || {},
    writeIntentFacts,
    bankSendPreparationFacts,
    currentObject,
    selectedObject: currentObject,
    sourceObjects: strictServerFacts.sourceObjects,
    resultCount: factLoadResultCount(
      factLoadFacts,
      bankSendPreparationFacts.bankSendPreparationCount,
    ),
    passed: factLoadPassed(
      factLoadFacts,
      bankSendPreparationFacts.passed === true,
    ),
    strictServerFacts,
    bankSendEnabled: data.bankSendEnabled === true,
    productionRolloutEnabled: data.productionRolloutEnabled === true,
  }
}
