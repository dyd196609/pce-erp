import {
  PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION,
} from './paymentVoucherPreparePrecheckBaselines.js'
import {
  PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION,
  PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
  evaluatePaymentVoucherPreparePrecheck,
  normalizePaymentVoucherPreparePrecheckInput,
} from './paymentVoucherPreparePrecheckEngine.js'
import {
  PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
} from './paymentVoucherPreparePrecheckContract.js'
import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
  adaptPaymentVoucherPrepareSourceToSnapshotInput,
  normalizePaymentVoucherPrepareSourceSnapshot,
} from './paymentVoucherPrepareSourceSnapshot.js'
import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION,
  createPaymentVoucherPrepareSourceFingerprint,
} from './paymentVoucherPrepareSourceFingerprint.js'
import {
  detectPaymentVoucherPrepareSourceChanges,
} from './paymentVoucherPrepareSourceChangeDetector.js'

export const PAYMENT_VOUCHER_PREPARE_REQUEST_ADAPTER_VERSION = 'PVPP-REQUEST-ADAPTER-1.0.0'
export const PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION = 'PVPP-REQUEST-PACKAGE-1.0.0'

const TYPE = {
  string: 'string',
  number: 'number',
  boolean: 'boolean',
}

const packageFingerprintFields = new Set([
  'packageType',
  'operationType',
  'requesterId',
  'paymentExecutionPrepareNo',
  'sourceObjectType',
  'snapshotContractVersion',
  'sourceSnapshotStatus',
  'sourceSnapshotFieldCount',
  'sourceFingerprintVersion',
  'sourceDataFingerprint',
  'sourceFingerprintStatus',
  'referenceSnapshotAvailable',
  'sourceChangeStatus',
  'sourceUnchangedConfirmed',
  'precheckEngineVersion',
  'ruleSetVersion',
  'inputContractVersion',
  'baselineVersion',
  'precheckDecision',
  'precheckCanProceed',
  'precheckTotalRuleCount',
  'precheckPassedCount',
  'precheckBlockedCount',
  'precheckWarningCount',
  'precheckNotApplicableCount',
  'legalEntityId',
  'accountingBookId',
  'accountingTemplateId',
  'accountingTemplateVersion',
  'accountingPeriod',
  'accountingPeriodStatus',
  'currencyCode',
  'baseCurrencyCode',
  'executionAmount',
  'paymentMethod',
  'plannedPaymentDate',
  'enterpriseBankAccountId',
  'supplierBankAccountId',
  'permissionReady',
  'secondConfirmationReady',
  'zeroBusinessWriteBoundaryReady',
  'simulationResultStorageReady',
  'simulationLogStorageReady',
  'uniquenessRuleReady',
  'idempotencyRuleReady',
  'concurrencyControlReady',
])

const idempotencyMaterialFields = new Set([
  'requestPackageContractVersion',
  'operationType',
  'legalEntityId',
  'accountingBookId',
  'paymentExecutionPrepareNo',
  'sourceDataFingerprint',
  'ruleSetVersion',
  'inputContractVersion',
  'accountingTemplateVersion',
  'accountingPeriod',
  'currencyCode',
])

const lockScopeFields = new Set([
  'requestPackageContractVersion',
  'operationType',
  'legalEntityId',
  'accountingBookId',
  'paymentExecutionPrepareNo',
])

const businessRequiredFields = new Set([
  'paymentExecutionPrepareNo',
  'sourceObjectType',
  'sourceDataFingerprint',
  'precheckDecision',
  'legalEntityId',
  'accountingBookId',
  'accountingTemplateId',
  'accountingTemplateVersion',
  'accountingPeriod',
  'accountingPeriodStatus',
  'currencyCode',
  'baseCurrencyCode',
  'executionAmount',
  'paymentMethod',
  'plannedPaymentDate',
  'enterpriseBankAccountId',
  'supplierBankAccountId',
  'permissionReady',
  'secondConfirmationReady',
  'zeroBusinessWriteBoundaryReady',
  'simulationResultStorageReady',
  'simulationLogStorageReady',
  'uniquenessRuleReady',
  'idempotencyRuleReady',
  'concurrencyControlReady',
])

const runtimeFields = new Set(['transportRequestId', 'requestedAt', 'requesterId'])

function requestField(field, chineseName, type, nullable, requiredForBusinessReady, defaultValue, businessMeaning, sourceDescription) {
  return {
    field,
    chineseName,
    type,
    nullable,
    requiredForPreview: true,
    requiredForBusinessReady,
    includedInPackageFingerprint: packageFingerprintFields.has(field),
    includedInIdempotencyMaterial: idempotencyMaterialFields.has(field),
    includedInLockScope: lockScopeFields.has(field),
    defaultValue,
    businessMeaning,
    sourceDescription,
    introducedInRequestPackageVersion: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
  }
}

export const PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS = [
  requestField('packageType', '请求输入包类型', TYPE.string, false, false, 'payment_voucher_prepare_simulation_request', '标识当前输入包用途。', '固定预览字段。'),
  requestField('operationType', '操作类型', TYPE.string, false, false, 'payment_voucher_prepare_simulation', '标识未来模拟动作。', '固定预览字段。'),
  requestField('transportRequestId', '传输请求号', TYPE.string, true, false, null, '未来传输层请求号，本轮不生成。', '未来运行时字段。'),
  requestField('requestedAt', '请求时间', TYPE.string, true, false, null, '未来请求时间，本轮不读取当前时间。', '未来运行时字段。'),
  requestField('requesterId', '请求人', TYPE.string, true, false, null, '未来操作人，本轮不推断。', '未来运行时字段。'),
  requestField('paymentExecutionPrepareNo', '付款执行准备单号', TYPE.string, true, true, null, '来源付款执行准备业务单号。', '付款执行准备对象。'),
  requestField('sourceObjectType', '来源对象类型', TYPE.string, true, true, null, '来源对象类型。', '来源快照。'),
  requestField('snapshotContractVersion', '来源快照契约版本', TYPE.string, false, false, PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION, '来源快照契约版本。', '来源快照模块。'),
  requestField('sourceSnapshotStatus', '来源快照状态', TYPE.string, false, false, 'source_not_found', '来源快照预览状态。', '来源快照模块。'),
  requestField('sourceSnapshotFieldCount', '来源快照字段数', TYPE.number, false, false, 0, '来源快照字段数量。', '来源快照模块。'),
  requestField('sourceFingerprintVersion', '来源指纹版本', TYPE.string, false, false, PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION, '来源指纹算法版本。', '来源指纹模块。'),
  requestField('sourceDataFingerprint', '来源数据指纹', TYPE.string, true, true, null, '来源数据稳定识别值。', '来源指纹模块。'),
  requestField('sourceFingerprintStatus', '来源指纹状态', TYPE.string, false, false, 'source_not_found', '来源指纹预览状态。', '来源指纹模块。'),
  requestField('referenceSnapshotAvailable', '是否存在参考快照', TYPE.boolean, false, false, false, '是否存在正式参考快照。', '来源变更检测模块。'),
  requestField('sourceChangeStatus', '来源变更状态', TYPE.string, false, false, 'source_not_found', '来源变化检测状态。', '来源变更检测模块。'),
  requestField('sourceUnchangedConfirmed', '来源未变化是否已确认', TYPE.boolean, false, false, false, '是否确认来源未变化。', '来源变更检测模块。'),
  requestField('precheckEngineVersion', '预检查引擎版本', TYPE.string, false, false, PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION, '预检查引擎版本。', '预检查模块。'),
  requestField('ruleSetVersion', '规则集版本', TYPE.string, false, true, PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION, '规则集版本。', '预检查模块。'),
  requestField('inputContractVersion', '输入契约版本', TYPE.string, false, true, PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION, '预检查输入契约版本。', '预检查模块。'),
  requestField('baselineVersion', '回归基线版本', TYPE.string, false, false, PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION, '回归基线版本。', '基线模块。'),
  requestField('precheckDecision', '预检查决策', TYPE.string, true, true, null, '当前预检查决策。', '预检查结果。'),
  requestField('precheckCanProceed', '预检查是否允许继续', TYPE.boolean, false, false, false, '当前是否允许继续模拟。', '预检查结果。'),
  requestField('precheckTotalRuleCount', '预检查规则总数', TYPE.number, false, false, 0, '规则总数。', '预检查结果。'),
  requestField('precheckPassedCount', '预检查通过项数量', TYPE.number, false, false, 0, '通过项数量。', '预检查结果。'),
  requestField('precheckBlockedCount', '预检查阻断项数量', TYPE.number, false, false, 0, '阻断项数量。', '预检查结果。'),
  requestField('precheckWarningCount', '预检查警告项数量', TYPE.number, false, false, 0, '警告项数量。', '预检查结果。'),
  requestField('precheckNotApplicableCount', '预检查不适用项数量', TYPE.number, false, false, 0, '不适用项数量。', '预检查结果。'),
  requestField('legalEntityId', '法人主体编号', TYPE.string, true, true, null, '法人主体编号。', '来源快照。'),
  requestField('accountingBookId', '会计账套编号', TYPE.string, true, true, null, '会计账套编号。', '来源快照。'),
  requestField('accountingTemplateId', '会计模板编号', TYPE.string, true, true, null, '会计模板编号。', '来源快照。'),
  requestField('accountingTemplateVersion', '会计模板版本', TYPE.string, true, true, null, '会计模板版本。', '来源快照。'),
  requestField('accountingPeriod', '会计期间', TYPE.string, true, true, null, '会计期间。', '来源快照。'),
  requestField('accountingPeriodStatus', '会计期间状态', TYPE.string, false, true, 'unknown', '会计期间状态。', '来源快照。'),
  requestField('currencyCode', '付款币种', TYPE.string, true, true, null, '付款币种。', '来源快照。'),
  requestField('baseCurrencyCode', '本位币', TYPE.string, true, true, null, '本位币。', '来源快照。'),
  requestField('executionAmount', '执行金额', TYPE.number, false, true, 0, '付款执行金额。', '来源快照。'),
  requestField('paymentMethod', '付款方式', TYPE.string, true, true, null, '付款方式。', '来源快照。'),
  requestField('plannedPaymentDate', '计划付款日期', TYPE.string, true, true, null, '计划付款日期。', '来源快照。'),
  requestField('enterpriseBankAccountId', '企业银行账户编号', TYPE.string, true, true, null, '付款方银行账户。', '来源快照。'),
  requestField('supplierBankAccountId', '供应商银行账户编号', TYPE.string, true, true, null, '收款方银行账户。', '来源快照。'),
  requestField('permissionReady', '权限是否就绪', TYPE.boolean, false, true, false, '未来模拟权限是否就绪。', '预检查输入。'),
  requestField('secondConfirmationReady', '二次确认是否就绪', TYPE.boolean, false, true, false, '未来二次确认机制是否就绪。', '预检查输入。'),
  requestField('zeroBusinessWriteBoundaryReady', '零写入边界是否就绪', TYPE.boolean, false, true, false, '零业务写入边界是否就绪。', '预检查输入。'),
  requestField('simulationResultStorageReady', '模拟结果存储是否就绪', TYPE.boolean, false, true, false, '模拟结果独立存储是否就绪。', '预检查输入。'),
  requestField('simulationLogStorageReady', '模拟日志存储是否就绪', TYPE.boolean, false, true, false, '模拟日志存储是否就绪。', '预检查输入。'),
  requestField('uniquenessRuleReady', '唯一性规则是否就绪', TYPE.boolean, false, true, false, '唯一性规则是否落地。', '预检查输入。'),
  requestField('idempotencyRuleReady', '幂等规则是否就绪', TYPE.boolean, false, true, false, '幂等规则是否落地。', '预检查输入。'),
  requestField('concurrencyControlReady', '并发控制是否就绪', TYPE.boolean, false, true, false, '并发控制是否落地。', '预检查输入。'),
]

const requestPackageFieldNames = PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.map((item) => item.field)
const requestPackageFieldSet = new Set(requestPackageFieldNames)

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function stableStringify(value) {
  if (value === null) return 'null'
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`
  if (typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function stableHash(value) {
  const text = typeof value === 'string' ? value : stableStringify(value)
  let hash = 2166136261
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash = (hash * 16777619) >>> 0
  }
  return hash.toString(16).toUpperCase().padStart(8, '0').slice(0, 8)
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

function hasPresentValue(value, field) {
  if (field.type === TYPE.boolean) return value === true
  if (field.type === TYPE.number) return Number.isFinite(Number(value)) && Number(value) > 0
  return !isBlank(value) && value !== 'unknown'
}

function asSnapshotResult(source = {}) {
  if (source && Object.prototype.hasOwnProperty.call(source, 'snapshotPreviewCreated')) return source
  return normalizePaymentVoucherPrepareSourceSnapshot(adaptPaymentVoucherPrepareSourceToSnapshotInput(source))
}

function asFingerprintResult(snapshotResult = {}) {
  if (snapshotResult && Object.prototype.hasOwnProperty.call(snapshotResult, 'fingerprintPreviewGenerated')) return snapshotResult
  return createPaymentVoucherPrepareSourceFingerprint(snapshotResult)
}

function asPrecheckResult(precheckInput = {}, existingResult = null) {
  if (existingResult && Object.prototype.hasOwnProperty.call(existingResult, 'totalRuleCount')) return existingResult
  return evaluatePaymentVoucherPreparePrecheck(precheckInput)
}

export function adaptPaymentVoucherPrepareToSimulationRequestPackage(source = {}, context = {}) {
  const snapshotResult = asSnapshotResult(context.sourceSnapshotResult || source)
  const snapshot = snapshotResult.snapshot || {}
  const fingerprintResult = asFingerprintResult(context.sourceFingerprintResult || snapshotResult)
  const changeResult = context.sourceChangeResult || detectPaymentVoucherPrepareSourceChanges(null, snapshotResult)
  const precheckInput = normalizePaymentVoucherPreparePrecheckInput(context.precheckInput || {
    routePaymentExecutionPrepareNo: snapshot.paymentExecutionPrepareNo || null,
    paymentExecutionPrepareFound: Boolean(snapshotResult.sourceFound),
    paymentExecutionPrepareNo: snapshot.paymentExecutionPrepareNo || null,
    reviewStatus: snapshot.reviewStatus || 'unknown',
    executionAmount: snapshot.executionAmount || 0,
    paymentMethod: snapshot.paymentMethod || null,
    sourcePaymentInstructionPrepareNo: snapshot.sourcePaymentInstructionPrepareNo || null,
    sourcePaymentApplicationNo: snapshot.sourcePaymentApplicationNo || null,
    sourcePayableConfirmNo: snapshot.sourcePayableConfirmNo || null,
    sourceInvoicePrepareNo: snapshot.sourceInvoicePrepareNo || null,
    sourceSettlementNo: snapshot.sourceSettlementNo || null,
    sourceChainComplete: Boolean(snapshot.sourceChainComplete),
    legalEntityId: snapshot.legalEntityId || null,
    accountingBookId: snapshot.accountingBookId || null,
    currencyCode: snapshot.currencyCode || null,
    baseCurrencyCode: snapshot.baseCurrencyCode || null,
    accountingTemplateId: snapshot.accountingTemplateId || null,
    accountingTemplateVersion: snapshot.accountingTemplateVersion || null,
    accountingTemplateStatus: snapshot.accountingTemplateStatus || 'unknown',
    accountingPeriod: snapshot.accountingPeriod || null,
    accountingPeriodStatus: snapshot.accountingPeriodStatus || 'unknown',
  })
  const precheckResult = asPrecheckResult(precheckInput, context.precheckResult)
  return {
    sourceFound: Boolean(snapshotResult.sourceFound),
    packageType: 'payment_voucher_prepare_simulation_request',
    operationType: 'payment_voucher_prepare_simulation',
    transportRequestId: null,
    requestedAt: null,
    requesterId: null,
    paymentExecutionPrepareNo: snapshot.paymentExecutionPrepareNo || null,
    sourceObjectType: snapshot.sourceObjectType || null,
    snapshotContractVersion: snapshotResult.snapshotContractVersion || PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
    sourceSnapshotStatus: snapshotResult.snapshotStructureStatus || 'source_not_found',
    sourceSnapshotFieldCount: snapshotResult.snapshotFieldCount || 0,
    sourceFingerprintVersion: fingerprintResult.fingerprintVersion || PAYMENT_VOUCHER_PREPARE_SOURCE_FINGERPRINT_VERSION,
    sourceDataFingerprint: fingerprintResult.sourceDataFingerprint || null,
    sourceFingerprintStatus: fingerprintResult.fingerprintStatus || 'source_not_found',
    referenceSnapshotAvailable: Boolean(changeResult.referenceSnapshotAvailable),
    sourceChangeStatus: changeResult.changeStatus || 'source_not_found',
    sourceUnchangedConfirmed: Boolean(changeResult.businessSourceUnchanged),
    precheckEngineVersion: precheckResult.engineVersion || PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION,
    ruleSetVersion: PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
    inputContractVersion: PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
    baselineVersion: PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION,
    precheckDecision: precheckResult.decision || null,
    precheckCanProceed: Boolean(precheckResult.canProceed),
    precheckTotalRuleCount: precheckResult.totalRuleCount || 0,
    precheckPassedCount: precheckResult.passedCount || 0,
    precheckBlockedCount: precheckResult.blockedCount || 0,
    precheckWarningCount: precheckResult.warningCount || 0,
    precheckNotApplicableCount: precheckResult.notApplicableCount || 0,
    legalEntityId: snapshot.legalEntityId || null,
    accountingBookId: snapshot.accountingBookId || null,
    accountingTemplateId: snapshot.accountingTemplateId || null,
    accountingTemplateVersion: snapshot.accountingTemplateVersion || null,
    accountingPeriod: snapshot.accountingPeriod || null,
    accountingPeriodStatus: snapshot.accountingPeriodStatus || 'unknown',
    currencyCode: snapshot.currencyCode || null,
    baseCurrencyCode: snapshot.baseCurrencyCode || null,
    executionAmount: snapshot.executionAmount || 0,
    paymentMethod: snapshot.paymentMethod || null,
    plannedPaymentDate: snapshot.plannedPaymentDate || null,
    enterpriseBankAccountId: snapshot.enterpriseBankAccountId || null,
    supplierBankAccountId: snapshot.supplierBankAccountId || null,
    permissionReady: Boolean(precheckInput.permissionReady),
    secondConfirmationReady: Boolean(precheckInput.secondConfirmationReady),
    zeroBusinessWriteBoundaryReady: Boolean(precheckInput.zeroBusinessWriteBoundaryReady),
    simulationResultStorageReady: Boolean(precheckInput.simulationResultStorageReady),
    simulationLogStorageReady: Boolean(precheckInput.simulationLogStorageReady),
    uniquenessRuleReady: Boolean(precheckInput.uniquenessRuleReady),
    idempotencyRuleReady: Boolean(precheckInput.idempotencyRuleReady),
    concurrencyControlReady: Boolean(precheckInput.concurrencyControlReady),
  }
}

export function normalizePaymentVoucherPrepareSimulationRequestPackage(input = {}) {
  const before = stableStringify(input)
  const raw = input && typeof input === 'object' ? input : {}
  const sourceFound = Boolean(raw.sourceFound !== false && raw.paymentExecutionPrepareNo)
  const unknownInputFieldCount = Object.keys(raw).filter((key) => key !== 'sourceFound' && !requestPackageFieldSet.has(key)).length
  const businessRequiredFieldCount = PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.filter((field) => field.requiredForBusinessReady).length
  const runtimeFieldCount = PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.filter((field) => runtimeFields.has(field.field)).length
  if (!sourceFound) {
    return {
      requestAdapterVersion: PAYMENT_VOUCHER_PREPARE_REQUEST_ADAPTER_VERSION,
      requestPackageContractVersion: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
      sourceFound: false,
      requestPackagePreviewEvaluated: true,
      requestPackagePreviewCreated: false,
      requestPackageStatus: 'source_not_found',
      requestPackage: null,
      requestPackageFieldCount: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.length,
      presentFieldCount: 0,
      missingFieldCount: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.length,
      businessRequiredFieldCount,
      missingBusinessRequiredFieldCount: businessRequiredFieldCount,
      missingBusinessRequiredFields: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.filter((field) => field.requiredForBusinessReady).map((field) => field.field),
      runtimeFieldCount,
      missingRuntimeFieldCount: runtimeFieldCount,
      unknownInputFieldCount,
      inputMutated: before !== stableStringify(input),
      requestPackageFingerprintPreviewGenerated: false,
      requestPackageFingerprint: null,
      businessRequestPackageReady: false,
    }
  }

  const requestPackage = {}
  const missingFields = []
  const missingBusinessRequiredFields = []
  let missingRuntimeFieldCount = 0
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.forEach((field) => {
    requestPackage[field.field] = normalizeValue(field, raw[field.field])
    const present = hasPresentValue(requestPackage[field.field], field)
    if (!present) missingFields.push(field.field)
    if (field.requiredForBusinessReady && !present) missingBusinessRequiredFields.push(field.field)
    if (runtimeFields.has(field.field) && !present) missingRuntimeFieldCount += 1
  })
  requestPackage.transportRequestId = null
  requestPackage.requestedAt = null
  requestPackage.requesterId = null

  const fingerprint = createPaymentVoucherPrepareRequestPackageFingerprint(requestPackage)
  return {
    requestAdapterVersion: PAYMENT_VOUCHER_PREPARE_REQUEST_ADAPTER_VERSION,
    requestPackageContractVersion: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
    sourceFound: true,
    requestPackagePreviewEvaluated: true,
    requestPackagePreviewCreated: true,
    requestPackageStatus: missingBusinessRequiredFields.length ? 'partial_preview' : 'complete_preview',
    requestPackage,
    requestPackageFieldCount: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.length,
    presentFieldCount: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS.length - missingFields.length,
    missingFieldCount: missingFields.length,
    businessRequiredFieldCount,
    missingBusinessRequiredFieldCount: missingBusinessRequiredFields.length,
    missingBusinessRequiredFields,
    runtimeFieldCount,
    missingRuntimeFieldCount,
    unknownInputFieldCount,
    inputMutated: before !== stableStringify(input),
    requestPackageFingerprintPreviewGenerated: true,
    requestPackageFingerprint: fingerprint,
    businessRequestPackageReady: false,
  }
}

export function validatePaymentVoucherPrepareSimulationRequestPackage(fields = PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS) {
  const fieldNames = fields.map((field) => field.field)
  const allowedTypes = new Set(Object.values(TYPE))
  const fingerprint = createPaymentVoucherPrepareRequestPackageContractFingerprint(fields)
  const locked = PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION]
  return {
    requestPackageContractVersion: PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
    requestPackageContractFingerprint: fingerprint,
    requestPackageContractLockedFingerprint: locked,
    requestPackageContractFingerprintMatched: fingerprint === locked,
    requestPackageFieldCount: fields.length,
    requestPackageFieldNamesUnique: new Set(fieldNames).size === fieldNames.length,
    requestPackageFieldOrderStable: fieldNames.join('|') === requestPackageFieldNames.join('|'),
    requestPackageFieldTypesValid: fields.every((field) => allowedTypes.has(field.type)),
    requestPackageValidationStatus: fields.length === 48 && new Set(fieldNames).size === fieldNames.length && fields.every((field) => allowedTypes.has(field.type)) ? 'passed' : 'failed',
  }
}

export function createPaymentVoucherPrepareRequestPackageContractFingerprint(fields = PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS) {
  const payload = fields.map((field) => ({
    field: field.field,
    chineseName: field.chineseName,
    type: field.type,
    nullable: field.nullable,
    requiredForPreview: field.requiredForPreview,
    requiredForBusinessReady: field.requiredForBusinessReady,
    includedInPackageFingerprint: field.includedInPackageFingerprint,
    includedInIdempotencyMaterial: field.includedInIdempotencyMaterial,
    includedInLockScope: field.includedInLockScope,
    defaultValue: field.defaultValue,
    businessMeaning: field.businessMeaning,
    sourceDescription: field.sourceDescription,
    introducedInRequestPackageVersion: field.introducedInRequestPackageVersion,
  }))
  return `PVPP-REQUEST-CONTRACT-FP-${stableHash(payload)}`
}

export const PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT = createPaymentVoucherPrepareRequestPackageContractFingerprint()

export const PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION]: 'PVPP-REQUEST-CONTRACT-FP-ACFB056C',
}

export function createPaymentVoucherPrepareRequestPackageFingerprint(input = {}) {
  const requestPackage = input && Object.prototype.hasOwnProperty.call(input, 'requestPackage') ? input.requestPackage : input
  if (!requestPackage) return null
  const payload = PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_FIELDS
    .filter((field) => field.includedInPackageFingerprint)
    .map((field) => ({
      field: field.field,
      value: requestPackage[field.field] ?? field.defaultValue,
    }))
  return `PVPP-REQUEST-PACKAGE-FP-${stableHash(payload)}`
}

export function verifyPaymentVoucherPrepareRequestPackagePurity(input = {}) {
  const before = stableStringify(input)
  const adapted = adaptPaymentVoucherPrepareToSimulationRequestPackage(input)
  const first = normalizePaymentVoucherPrepareSimulationRequestPackage(adapted)
  const second = normalizePaymentVoucherPrepareSimulationRequestPackage(clone(adapted))
  const after = stableStringify(input)
  return {
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    inputMutated: before !== after,
    requestPackagePreviewOnly: true,
    requestPackageSaved: false,
    transportRequestIdGenerated: false,
    requestAttemptIdGenerated: false,
    businessDataWritten: false,
    stateMachineStarted: false,
    simulationRequestCreated: false,
  }
}
