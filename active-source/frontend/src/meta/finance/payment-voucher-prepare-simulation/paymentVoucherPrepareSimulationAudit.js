import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION,
  paymentVoucherPrepareSimulationResultContractInternals,
} from './paymentVoucherPrepareSimulationResultContract.js'
import {
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_VALIDITY_STATUSES,
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_STATUSES,
} from './paymentVoucherPrepareSimulationResultLifecycle.js'

export { PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION }

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_EVENT_TYPES = [
  'RESULT_CREATED',
  'CALCULATION_COMPLETED',
  'VALIDATION_PASSED',
  'VALIDATION_FAILED',
  'RESULT_FROZEN',
  'RESULT_INVALIDATED',
  'RESULT_SUPERSEDED',
  'RESULT_CANCELLED',
  'RESULT_ARCHIVED',
]

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_FORBIDDEN_AUDIT_EVENT_TYPES = [
  'PAYMENT_EXECUTED',
  'VOUCHER_POSTED',
  'LEDGER_WRITTEN',
  'PAYMENT_WRITTEN_OFF',
]

const TYPE = {
  string: 'string',
  number: 'number',
  boolean: 'boolean',
}

const eventPayloadFingerprintFields = new Set([
  'auditContractVersion',
  'resultReferenceNo',
  'simulationRequestReferenceNo',
  'paymentExecutionPrepareNo',
  'eventSequence',
  'eventType',
  'previousLifecycleStatus',
  'nextLifecycleStatus',
  'previousValidityStatus',
  'nextValidityStatus',
  'eventReasonCode',
  'eventReasonText',
  'sourceDataFingerprint',
  'requestPackageFingerprint',
  'resultRecordFingerprint',
  'previousEventFingerprint',
  'appendOnly',
  'businessDataWritten',
  'formalBusinessObjectAffected',
])

const eventFingerprintFields = new Set([
  ...eventPayloadFingerprintFields,
  'eventPayloadFingerprint',
])

const runtimeAuditFields = new Set(['eventReferenceNo', 'actorId', 'occurredAt'])

const { stableStringify, stableHash } = paymentVoucherPrepareSimulationResultContractInternals

function auditField(field, chineseName, type, nullable, defaultValue, businessMeaning, sourceDescription) {
  return {
    field,
    chineseName,
    type,
    nullable,
    requiredForPreview: true,
    requiredForStoredRecord: true,
    immutableAfterValidation: true,
    includedInRecordFingerprint: eventFingerprintFields.has(field),
    defaultValue,
    businessMeaning,
    sourceDescription,
    introducedInContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION,
  }
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_FIELDS = [
  auditField('auditContractVersion', '审计契约版本', TYPE.string, false, PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION, '模拟审计事件契约版本。', '审计契约。'),
  auditField('eventReferenceNo', '审计事件编号', TYPE.string, true, null, '未来审计事件编号，本轮不生成。', '未来运行时字段。'),
  auditField('resultReferenceNo', '模拟结果编号', TYPE.string, true, null, '关联模拟结果编号。', '模拟结果。'),
  auditField('simulationRequestReferenceNo', '模拟请求编号', TYPE.string, true, null, '关联模拟请求编号。', '模拟请求。'),
  auditField('paymentExecutionPrepareNo', '付款执行准备单号', TYPE.string, true, null, '来源付款执行准备单号。', '付款执行准备。'),
  auditField('eventSequence', '事件顺序号', TYPE.number, false, 0, '追加式事件顺序号。', '审计链。'),
  auditField('eventType', '事件类型', TYPE.string, true, null, '模拟结果审计事件类型。', '审计契约。'),
  auditField('previousLifecycleStatus', '原生命周期状态', TYPE.string, true, null, '事件前生命周期状态。', '生命周期模块。'),
  auditField('nextLifecycleStatus', '新生命周期状态', TYPE.string, true, null, '事件后生命周期状态。', '生命周期模块。'),
  auditField('previousValidityStatus', '原有效性状态', TYPE.string, true, null, '事件前有效性状态。', '生命周期模块。'),
  auditField('nextValidityStatus', '新有效性状态', TYPE.string, true, null, '事件后有效性状态。', '生命周期模块。'),
  auditField('eventReasonCode', '事件原因编码', TYPE.string, true, null, '审计事件原因编码。', '审计事件。'),
  auditField('eventReasonText', '事件原因说明', TYPE.string, true, null, '审计事件原因说明。', '审计事件。'),
  auditField('actorId', '操作人', TYPE.string, true, null, '未来操作人，本轮不推断。', '未来运行时字段。'),
  auditField('occurredAt', '发生时间', TYPE.string, true, null, '未来发生时间，本轮不读取当前时间。', '未来运行时字段。'),
  auditField('sourceDataFingerprint', '来源数据指纹', TYPE.string, true, null, '来源数据指纹。', '来源指纹模块。'),
  auditField('requestPackageFingerprint', '请求输入包指纹', TYPE.string, true, null, '请求输入包指纹。', '请求输入包。'),
  auditField('resultRecordFingerprint', '结果记录指纹', TYPE.string, true, null, '模拟结果记录指纹。', '模拟结果。'),
  auditField('previousEventFingerprint', '前序事件指纹', TYPE.string, true, null, '前序审计事件指纹。', '审计链。'),
  auditField('eventPayloadFingerprint', '事件载荷指纹', TYPE.string, true, null, '审计事件载荷指纹。', '审计事件。'),
  auditField('eventFingerprint', '事件指纹', TYPE.string, true, null, '审计事件稳定指纹。', '审计事件。'),
  auditField('appendOnly', '是否追加式', TYPE.boolean, false, true, '审计事件是否追加式。', '审计规则。'),
  auditField('businessDataWritten', '是否写业务数据', TYPE.boolean, false, false, '审计事件是否写业务数据。', '保护边界。'),
  auditField('formalBusinessObjectAffected', '是否影响正式业务对象', TYPE.boolean, false, false, '是否影响正式业务对象。', '保护边界。'),
]

const auditFieldNames = PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_FIELDS.map((item) => item.field)
const auditFieldSet = new Set(auditFieldNames)

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function isBlank(value) {
  return value === null || value === undefined || value === ''
}

function toStringValue(value, defaultValue) {
  if (isBlank(value)) return defaultValue
  return String(value).trim()
}

function toNumberValue(value, defaultValue) {
  if (isBlank(value)) return defaultValue
  const next = Number(value)
  return Number.isFinite(next) ? Number(next.toFixed(6)) : defaultValue
}

function toBooleanValue(value, defaultValue) {
  if (isBlank(value)) return defaultValue
  if (value === true || value === false) return value
  if (String(value).toLowerCase() === 'true') return true
  if (String(value).toLowerCase() === 'false') return false
  return defaultValue
}

function normalizeValue(field, value) {
  if (field.type === TYPE.number) return toNumberValue(value, field.defaultValue)
  if (field.type === TYPE.boolean) return toBooleanValue(value, field.defaultValue)
  return toStringValue(value, field.defaultValue)
}

export function normalizePaymentVoucherPrepareSimulationAuditEvent(input = {}) {
  const raw = input && typeof input === 'object' ? input : {}
  const event = {}
  PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_FIELDS.forEach((field) => {
    event[field.field] = field.field === 'eventPayloadFingerprint' || field.field === 'eventFingerprint'
      ? null
      : normalizeValue(field, raw[field.field])
  })
  event.auditContractVersion = PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION
  event.appendOnly = true
  event.businessDataWritten = false
  event.formalBusinessObjectAffected = false
  event.eventPayloadFingerprint = createPaymentVoucherPrepareSimulationAuditPayloadFingerprint(event)
  event.eventFingerprint = createPaymentVoucherPrepareSimulationAuditEventFingerprint(event)
  return event
}

export function validatePaymentVoucherPrepareSimulationAuditEvent(input = {}) {
  const event = normalizePaymentVoucherPrepareSimulationAuditEvent(input)
  const fieldNames = PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_FIELDS.map((field) => field.field)
  const allowedTypes = new Set(Object.values(TYPE))
  const errors = []
  if (!PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_EVENT_TYPES.includes(event.eventType)) errors.push('EVENT_TYPE_INVALID')
  if (PAYMENT_VOUCHER_PREPARE_SIMULATION_FORBIDDEN_AUDIT_EVENT_TYPES.includes(event.eventType)) errors.push('FORMAL_BUSINESS_EVENT_FORBIDDEN')
  if (!Number.isInteger(Number(event.eventSequence)) || Number(event.eventSequence) <= 0) errors.push('EVENT_SEQUENCE_INVALID')
  if (event.eventSequence === 1 && event.previousEventFingerprint !== null) errors.push('FIRST_EVENT_PREVIOUS_FINGERPRINT_MUST_BE_NULL')
  if (!PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_STATUSES.includes(event.previousLifecycleStatus)) errors.push('PREVIOUS_LIFECYCLE_STATUS_INVALID')
  if (!PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_STATUSES.includes(event.nextLifecycleStatus)) errors.push('NEXT_LIFECYCLE_STATUS_INVALID')
  if (!PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_VALIDITY_STATUSES.includes(event.previousValidityStatus)) errors.push('PREVIOUS_VALIDITY_STATUS_INVALID')
  if (!PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_VALIDITY_STATUSES.includes(event.nextValidityStatus)) errors.push('NEXT_VALIDITY_STATUS_INVALID')
  if (event.appendOnly !== true) errors.push('APPEND_ONLY_REQUIRED')
  if (event.businessDataWritten !== false) errors.push('BUSINESS_DATA_WRITE_FORBIDDEN')
  if (event.formalBusinessObjectAffected !== false) errors.push('FORMAL_BUSINESS_OBJECT_AFFECTED_FORBIDDEN')
  return {
    auditContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION,
    auditFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_FIELDS.length,
    auditFieldNamesUnique: new Set(fieldNames).size === fieldNames.length,
    auditFieldOrderStable: fieldNames.join('|') === auditFieldNames.join('|'),
    auditFieldTypesValid: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_FIELDS.every((field) => allowedTypes.has(field.type)),
    auditEventValidationStatus: errors.length === 0 ? 'passed' : 'failed',
    errors,
    event,
  }
}

export function createPaymentVoucherPrepareSimulationAuditContractFingerprint(fields = PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_FIELDS) {
  const payload = {
    lifecycleVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_VERSION,
    fields: fields.map((field) => ({
      field: field.field,
      chineseName: field.chineseName,
      type: field.type,
      nullable: field.nullable,
      requiredForPreview: field.requiredForPreview,
      requiredForStoredRecord: field.requiredForStoredRecord,
      immutableAfterValidation: field.immutableAfterValidation,
      includedInRecordFingerprint: field.includedInRecordFingerprint,
      defaultValue: field.defaultValue,
      businessMeaning: field.businessMeaning,
      sourceDescription: field.sourceDescription,
      introducedInContractVersion: field.introducedInContractVersion,
    })),
    eventTypes: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_EVENT_TYPES,
    forbiddenEventTypes: PAYMENT_VOUCHER_PREPARE_SIMULATION_FORBIDDEN_AUDIT_EVENT_TYPES,
    appendRules: {
      appendOnly: true,
      sequenceStartsAt: 1,
      sequenceContinuous: true,
      previousFingerprintRule: 'first-null-then-previous-event',
      historicalMutationAllowed: false,
      businessDataWritten: false,
      formalBusinessObjectAffected: false,
    },
  }
  return `PVPP-SIM-AUDIT-CONTRACT-FP-${stableHash(payload)}`
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT = createPaymentVoucherPrepareSimulationAuditContractFingerprint()

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION]: 'PVPP-SIM-AUDIT-CONTRACT-FP-9FCF1ADC',
}

export function createPaymentVoucherPrepareSimulationAuditPayloadFingerprint(event = {}) {
  const material = PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_FIELDS
    .filter((field) => eventPayloadFingerprintFields.has(field.field))
    .map((field) => ({ field: field.field, value: normalizeValue(field, event[field.field]) }))
  return `PVPP-SIM-AUDIT-PAYLOAD-FP-${stableHash(material)}`
}

export function createPaymentVoucherPrepareSimulationAuditEventFingerprint(event = {}) {
  const payloadFingerprint = event.eventPayloadFingerprint || createPaymentVoucherPrepareSimulationAuditPayloadFingerprint(event)
  const material = PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_FIELDS
    .filter((field) => eventFingerprintFields.has(field.field))
    .map((field) => ({
      field: field.field,
      value: field.field === 'eventPayloadFingerprint' ? payloadFingerprint : normalizeValue(field, event[field.field]),
    }))
  return `PVPP-SIM-AUDIT-EVENT-FP-${stableHash(material)}`
}

export function createPaymentVoucherPrepareSimulationAuditEventPreview(input = {}, previousEvent = null) {
  const previousFingerprint = previousEvent ? previousEvent.eventFingerprint : null
  const event = normalizePaymentVoucherPrepareSimulationAuditEvent({
    ...input,
    previousEventFingerprint: previousFingerprint,
    appendOnly: true,
    businessDataWritten: false,
    formalBusinessObjectAffected: false,
  })
  return {
    auditContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION,
    auditEventPreviewCreated: true,
    realAuditEventCreated: false,
    event,
  }
}

export function verifyPaymentVoucherPrepareSimulationAuditChain(events = []) {
  const normalizedEvents = Array.isArray(events) ? events.map((event) => normalizePaymentVoucherPrepareSimulationAuditEvent(event)) : []
  const errors = []
  const seenSequences = new Set()
  normalizedEvents.forEach((event, index) => {
    const expectedSequence = index + 1
    if (event.eventSequence !== expectedSequence) errors.push({ index, code: 'SEQUENCE_NOT_CONTINUOUS', expected: expectedSequence, actual: event.eventSequence })
    if (seenSequences.has(event.eventSequence)) errors.push({ index, code: 'SEQUENCE_DUPLICATED', actual: event.eventSequence })
    seenSequences.add(event.eventSequence)
    const expectedPrevious = index === 0 ? null : normalizedEvents[index - 1].eventFingerprint
    if (event.previousEventFingerprint !== expectedPrevious) errors.push({ index, code: 'PREVIOUS_FINGERPRINT_MISMATCH', expected: expectedPrevious, actual: event.previousEventFingerprint })
    const validation = validatePaymentVoucherPrepareSimulationAuditEvent(event)
    if (validation.auditEventValidationStatus !== 'passed') errors.push({ index, code: 'EVENT_INVALID', details: validation.errors })
  })
  return {
    auditContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION,
    auditChainVerified: normalizedEvents.length > 0 && errors.length === 0,
    auditChainStatus: normalizedEvents.length === 0 ? 'no_events' : (errors.length === 0 ? 'passed' : 'failed'),
    auditEventCount: normalizedEvents.length,
    appendOnlyPolicyReadyPreview: true,
    errors,
    events: normalizedEvents,
    realAuditEventCreatedCount: 0,
    businessSimulationAuditStorageReady: false,
  }
}

export function summarizePaymentVoucherPrepareSimulationAuditTrail(events = []) {
  const chain = verifyPaymentVoucherPrepareSimulationAuditChain(events)
  return {
    auditContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION,
    auditEventCount: chain.auditEventCount,
    auditChainStatus: chain.auditChainStatus,
    auditChainVerified: chain.auditChainVerified,
    appendOnlyPolicyReadyPreview: true,
    firstEventType: chain.events[0]?.eventType || null,
    lastEventType: chain.events[chain.events.length - 1]?.eventType || null,
    businessDataWritten: false,
    formalBusinessObjectAffected: false,
  }
}

export function validatePaymentVoucherPrepareSimulationAuditContract(fields = PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_FIELDS) {
  const fieldNames = fields.map((field) => field.field)
  const allowedTypes = new Set(Object.values(TYPE))
  const fingerprint = createPaymentVoucherPrepareSimulationAuditContractFingerprint(fields)
  const locked = PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION]
  return {
    auditContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION,
    auditContractFingerprint: fingerprint,
    auditContractLockedFingerprint: locked,
    auditContractFingerprintMatched: fingerprint === locked,
    auditFieldCount: fields.length,
    auditFieldNamesUnique: new Set(fieldNames).size === fieldNames.length,
    auditFieldOrderStable: fieldNames.join('|') === auditFieldNames.join('|'),
    auditFieldTypesValid: fields.every((field) => allowedTypes.has(field.type)),
    runtimeAuditFieldCount: runtimeAuditFields.size,
    auditContractValidationStatus: fields.length === 24 && new Set(fieldNames).size === fieldNames.length && fields.every((field) => allowedTypes.has(field.type)) ? 'passed' : 'failed',
  }
}

export function verifyPaymentVoucherPrepareSimulationAuditPurity(input = {}) {
  const before = stableStringify(input)
  const first = createPaymentVoucherPrepareSimulationAuditEventPreview(input, null)
  const second = createPaymentVoucherPrepareSimulationAuditEventPreview(clone(input), null)
  const after = stableStringify(input)
  return {
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    inputMutated: before !== after,
    auditEventSaved: false,
    auditTrailModified: false,
    businessDataWritten: false,
    formalBusinessObjectAffected: false,
  }
}

export const paymentVoucherPrepareSimulationAuditInternals = {
  auditFieldSet,
}
