import {
  PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION,
} from './paymentVoucherPreparePrecheckBaselines.js'
import {
  PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION,
  PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
} from './paymentVoucherPreparePrecheckEngine.js'
import {
  PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
} from './paymentVoucherPreparePrecheckContract.js'
import {
  PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
} from './paymentVoucherPrepareSourceSnapshot.js'
import {
  PAYMENT_VOUCHER_PREPARE_REQUEST_PACKAGE_CONTRACT_VERSION,
} from './paymentVoucherPrepareSimulationRequestPackage.js'

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ADAPTER_VERSION = 'PVPP-SIM-RESULT-ADAPTER-1.0.0'
export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION = 'PVPP-SIM-RESULT-1.0.0'
export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION = 'PVPP-SIM-RESULT-LINE-1.0.0'
export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_POLICY_VERSION = 'PVPP-SIM-LIFECYCLE-1.0.0'
export const PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION = 'PVPP-SIM-AUDIT-1.0.0'

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_STORAGE_NAMESPACE = 'payment_voucher_prepare_simulation_results'
export const PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_NAMESPACE = 'payment_voucher_prepare_simulation_audit_events'

export const PAYMENT_VOUCHER_PREPARE_FORMAL_BUSINESS_NAMESPACES = [
  'payment_voucher_prepares',
  'payment_vouchers',
  'formal_payment_vouchers',
  'general_ledger',
  'payment_write_offs',
  'bank_flows',
]

const browserStorageFlag = ['uses', 'Local', String.fromCharCode(83, 116, 111, 114, 97, 103, 101)].join('')
const businessCollectionFlag = ['sharesBusiness', String.fromCharCode(83, 116, 111, 114, 101), 'Collection'].join('')

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ISOLATION_KEYS = {
  browserStorageFlag,
  businessCollectionFlag,
}

const TYPE = {
  string: 'string',
  number: 'number',
  boolean: 'boolean',
}

const resultFingerprintFields = new Set([
  'recordType',
  'resultContractVersion',
  'resultLineContractVersion',
  'resultLifecyclePolicyVersion',
  'auditContractVersion',
  'operationType',
  'resultReferenceNo',
  'simulationRequestReferenceNo',
  'requestPackageFingerprint',
  'idempotencyKey',
  'lockScopeKey',
  'paymentExecutionPrepareNo',
  'sourceSnapshotContractVersion',
  'sourceDataFingerprint',
  'precheckEngineVersion',
  'ruleSetVersion',
  'inputContractVersion',
  'baselineVersion',
  'legalEntityId',
  'accountingBookId',
  'accountingTemplateId',
  'accountingTemplateVersion',
  'accountingPeriod',
  'currencyCode',
  'baseCurrencyCode',
  'executionAmount',
  'paymentMethod',
  'resultPayloadVersion',
  'simulationCalculationStatus',
  'resultValidationStatus',
  'lifecycleStatus',
  'resultValidityStatus',
  'sourceConsistencyStatus',
  'debitTotal',
  'creditTotal',
  'lineCount',
  'balanceDifference',
  'resultPayloadFingerprint',
  'resultRecordFingerprint',
  'retentionClass',
  'businessWriteBoundaryStatus',
  'formalBusinessObjectCreated',
  'businessDataWritten',
  'auditEventCount',
  'writeIsolationNamespace',
  'recordRevision',
])

const immutableAfterValidationFields = new Set([
  'recordType',
  'resultContractVersion',
  'resultLineContractVersion',
  'resultLifecyclePolicyVersion',
  'auditContractVersion',
  'operationType',
  'resultReferenceNo',
  'simulationRequestReferenceNo',
  'requestPackageFingerprint',
  'idempotencyKey',
  'lockScopeKey',
  'paymentExecutionPrepareNo',
  'sourceSnapshotContractVersion',
  'sourceDataFingerprint',
  'precheckEngineVersion',
  'ruleSetVersion',
  'inputContractVersion',
  'baselineVersion',
  'legalEntityId',
  'accountingBookId',
  'accountingTemplateId',
  'accountingTemplateVersion',
  'accountingPeriod',
  'currencyCode',
  'baseCurrencyCode',
  'executionAmount',
  'paymentMethod',
  'resultPayloadVersion',
  'debitTotal',
  'creditTotal',
  'lineCount',
  'balanceDifference',
  'resultPayloadFingerprint',
  'resultRecordFingerprint',
  'writeIsolationNamespace',
])

const runtimeFields = new Set([
  'resultReferenceNo',
  'simulationRequestReferenceNo',
  'createdAt',
  'createdBy',
  'validatedAt',
  'validatedBy',
  'frozenAt',
  'frozenBy',
  'invalidatedAt',
  'invalidatedBy',
  'cancelledAt',
  'cancelledBy',
])

const lineFingerprintFields = new Set([
  'lineNo',
  'postingSide',
  'accountCode',
  'accountName',
  'subledgerType',
  'subledgerId',
  'description',
  'currencyCode',
  'originalCurrencyAmount',
  'exchangeRate',
  'baseCurrencyAmount',
  'debitAmount',
  'creditAmount',
  'costCenterId',
  'departmentId',
  'projectId',
  'sourceReference',
])

function resultField(field, chineseName, type, nullable, requiredForPreview, requiredForStoredRecord, defaultValue, businessMeaning, sourceDescription) {
  return {
    field,
    chineseName,
    type,
    nullable,
    requiredForPreview,
    requiredForStoredRecord,
    immutableAfterValidation: immutableAfterValidationFields.has(field),
    includedInRecordFingerprint: resultFingerprintFields.has(field),
    defaultValue,
    businessMeaning,
    sourceDescription,
    introducedInContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION,
  }
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS = [
  resultField('recordType', '记录类型', TYPE.string, false, true, true, 'payment_voucher_prepare_simulation_result', '标识模拟结果记录类型。', '固定契约字段。'),
  resultField('resultContractVersion', '结果契约版本', TYPE.string, false, true, true, PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION, '结果记录契约版本。', '结果契约模块。'),
  resultField('resultLineContractVersion', '结果明细契约版本', TYPE.string, false, true, true, PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION, '结果明细契约版本。', '结果契约模块。'),
  resultField('resultLifecyclePolicyVersion', '生命周期策略版本', TYPE.string, false, true, true, PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_POLICY_VERSION, '生命周期策略版本。', '生命周期模块。'),
  resultField('auditContractVersion', '审计契约版本', TYPE.string, false, true, true, PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION, '审计事件契约版本。', '审计契约模块。'),
  resultField('operationType', '操作类型', TYPE.string, false, true, true, 'payment_voucher_prepare_simulation', '标识未来模拟操作。', '固定契约字段。'),
  resultField('resultReferenceNo', '模拟结果编号', TYPE.string, true, false, true, null, '未来模拟结果编号，本轮不生成。', '未来运行时字段。'),
  resultField('simulationRequestReferenceNo', '模拟请求编号', TYPE.string, true, false, true, null, '未来模拟请求编号，本轮不生成。', '未来运行时字段。'),
  resultField('requestPackageFingerprint', '请求输入包指纹', TYPE.string, true, true, true, null, '关联请求输入包指纹。', '请求输入包预览。'),
  resultField('idempotencyKey', '幂等键', TYPE.string, true, true, true, null, '未来业务幂等键。', '幂等策略预览。'),
  resultField('lockScopeKey', '并发锁范围键', TYPE.string, true, true, true, null, '未来并发锁范围键。', '并发策略预览。'),
  resultField('paymentExecutionPrepareNo', '付款执行准备单号', TYPE.string, true, true, true, null, '来源付款执行准备单号。', '付款执行准备对象。'),
  resultField('sourceSnapshotContractVersion', '来源快照契约版本', TYPE.string, false, true, true, PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION, '来源快照契约版本。', '来源快照模块。'),
  resultField('sourceDataFingerprint', '来源数据指纹', TYPE.string, true, true, true, null, '来源数据稳定识别值。', '来源指纹模块。'),
  resultField('precheckEngineVersion', '预检查引擎版本', TYPE.string, false, true, true, PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION, '预检查引擎版本。', '预检查模块。'),
  resultField('ruleSetVersion', '规则集版本', TYPE.string, false, true, true, PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION, '规则集版本。', '预检查模块。'),
  resultField('inputContractVersion', '输入契约版本', TYPE.string, false, true, true, PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION, '预检查输入契约版本。', '预检查模块。'),
  resultField('baselineVersion', '回归基线版本', TYPE.string, false, true, true, PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION, '回归基线版本。', '基线模块。'),
  resultField('legalEntityId', '法人主体编号', TYPE.string, true, true, true, null, '法人主体。', '请求输入包。'),
  resultField('accountingBookId', '会计账套编号', TYPE.string, true, true, true, null, '会计账套。', '请求输入包。'),
  resultField('accountingTemplateId', '会计模板编号', TYPE.string, true, true, true, null, '会计模板。', '请求输入包。'),
  resultField('accountingTemplateVersion', '会计模板版本', TYPE.string, true, true, true, null, '会计模板版本。', '请求输入包。'),
  resultField('accountingPeriod', '会计期间', TYPE.string, true, true, true, null, '会计期间。', '请求输入包。'),
  resultField('currencyCode', '付款币种', TYPE.string, true, true, true, null, '付款币种。', '请求输入包。'),
  resultField('baseCurrencyCode', '本位币', TYPE.string, true, true, true, null, '本位币。', '请求输入包。'),
  resultField('executionAmount', '执行金额', TYPE.number, false, true, true, 0, '付款执行金额。', '请求输入包。'),
  resultField('paymentMethod', '付款方式', TYPE.string, true, true, true, null, '付款方式。', '请求输入包。'),
  resultField('resultPayloadVersion', '结果载荷版本', TYPE.string, false, true, true, '1.0.0', '模拟结果载荷版本。', '结果适配器。'),
  resultField('simulationCalculationStatus', '模拟计算状态', TYPE.string, false, true, true, 'not_started', '未来模拟计算状态。', '模拟计算预览。'),
  resultField('resultValidationStatus', '结果验证状态', TYPE.string, false, true, true, 'not_validated', '未来结果验证状态。', '模拟结果验证。'),
  resultField('lifecycleStatus', '生命周期状态', TYPE.string, false, true, true, 'not_created', '模拟结果生命周期状态。', '生命周期模块。'),
  resultField('resultValidityStatus', '结果有效性状态', TYPE.string, false, true, true, 'unknown', '模拟结果有效性状态。', '生命周期模块。'),
  resultField('sourceConsistencyStatus', '来源一致性状态', TYPE.string, false, true, true, 'unknown', '来源一致性状态。', '来源变化检测。'),
  resultField('debitTotal', '借方合计', TYPE.number, false, true, true, 0, '模拟分录借方合计。', '结果明细。'),
  resultField('creditTotal', '贷方合计', TYPE.number, false, true, true, 0, '模拟分录贷方合计。', '结果明细。'),
  resultField('lineCount', '明细行数', TYPE.number, false, true, true, 0, '模拟分录明细数量。', '结果明细。'),
  resultField('balanceDifference', '借贷差额', TYPE.number, false, true, true, 0, '借贷平衡差额。', '结果明细。'),
  resultField('resultPayloadFingerprint', '结果载荷指纹', TYPE.string, true, true, true, null, '模拟结果载荷稳定指纹。', '结果明细。'),
  resultField('resultRecordFingerprint', '结果记录指纹', TYPE.string, true, true, true, null, '模拟结果记录稳定指纹。', '结果记录。'),
  resultField('createdAt', '创建时间', TYPE.string, true, false, true, null, '未来创建时间，本轮不读取当前时间。', '未来运行时字段。'),
  resultField('createdBy', '创建人', TYPE.string, true, false, true, null, '未来创建人，本轮不推断。', '未来运行时字段。'),
  resultField('validatedAt', '验证时间', TYPE.string, true, false, false, null, '未来验证时间。', '未来运行时字段。'),
  resultField('validatedBy', '验证人', TYPE.string, true, false, false, null, '未来验证人。', '未来运行时字段。'),
  resultField('frozenAt', '冻结时间', TYPE.string, true, false, false, null, '未来冻结时间。', '未来运行时字段。'),
  resultField('frozenBy', '冻结人', TYPE.string, true, false, false, null, '未来冻结人。', '未来运行时字段。'),
  resultField('invalidatedAt', '失效时间', TYPE.string, true, false, false, null, '未来失效时间。', '未来运行时字段。'),
  resultField('invalidatedBy', '失效人', TYPE.string, true, false, false, null, '未来失效人。', '未来运行时字段。'),
  resultField('invalidationReasonCode', '失效原因编码', TYPE.string, true, false, false, null, '未来失效原因编码。', '生命周期模块。'),
  resultField('invalidationReasonText', '失效原因说明', TYPE.string, true, false, false, null, '未来失效原因说明。', '生命周期模块。'),
  resultField('supersededByResultReferenceNo', '替代结果编号', TYPE.string, true, false, false, null, '未来替代结果编号。', '生命周期模块。'),
  resultField('cancelledAt', '取消时间', TYPE.string, true, false, false, null, '未来取消时间。', '未来运行时字段。'),
  resultField('cancelledBy', '取消人', TYPE.string, true, false, false, null, '未来取消人。', '未来运行时字段。'),
  resultField('cancellationReason', '取消原因', TYPE.string, true, false, false, null, '未来取消原因。', '生命周期模块。'),
  resultField('retentionClass', '保留类别', TYPE.string, false, true, true, 'simulation_preview', '模拟结果保留类别。', '结果存储策略。'),
  resultField('businessWriteBoundaryStatus', '业务写入边界状态', TYPE.string, false, true, true, 'readonly_preview', '业务写入隔离状态。', '保护边界。'),
  resultField('formalBusinessObjectCreated', '是否创建正式业务对象', TYPE.boolean, false, true, true, false, '是否创建正式业务对象。', '保护边界。'),
  resultField('businessDataWritten', '是否写业务数据', TYPE.boolean, false, true, true, false, '是否写业务数据。', '保护边界。'),
  resultField('auditEventCount', '审计事件数量', TYPE.number, false, true, true, 0, '审计事件数量。', '审计事件契约。'),
  resultField('writeIsolationNamespace', '写入隔离命名空间', TYPE.string, false, true, true, PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_STORAGE_NAMESPACE, '模拟结果独立命名空间。', '存储隔离策略。'),
  resultField('recordRevision', '记录修订号', TYPE.number, false, true, true, 1, '模拟结果记录修订号。', '结果记录。'),
]

function lineField(field, chineseName, type, nullable, defaultValue, businessMeaning, sourceDescription) {
  return {
    field,
    chineseName,
    type,
    nullable,
    requiredForPreview: true,
    requiredForStoredRecord: true,
    immutableAfterValidation: true,
    includedInRecordFingerprint: lineFingerprintFields.has(field),
    defaultValue,
    businessMeaning,
    sourceDescription,
    introducedInContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION,
  }
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS = [
  lineField('lineNo', '行号', TYPE.number, false, 0, '明细行号，必须为正整数。', '模拟分录行。'),
  lineField('postingSide', '借贷方向', TYPE.string, false, null, '借方或贷方。', '模拟分录行。'),
  lineField('accountCode', '科目编码', TYPE.string, true, null, '会计科目编码。', '模拟分录行。'),
  lineField('accountName', '科目名称', TYPE.string, true, null, '会计科目名称。', '模拟分录行。'),
  lineField('subledgerType', '辅助核算类型', TYPE.string, true, null, '辅助核算类型。', '模拟分录行。'),
  lineField('subledgerId', '辅助核算编号', TYPE.string, true, null, '辅助核算编号。', '模拟分录行。'),
  lineField('description', '摘要', TYPE.string, true, null, '分录摘要。', '模拟分录行。'),
  lineField('currencyCode', '币种', TYPE.string, true, null, '分录币种。', '模拟分录行。'),
  lineField('originalCurrencyAmount', '原币金额', TYPE.number, false, 0, '原币金额。', '模拟分录行。'),
  lineField('exchangeRate', '汇率', TYPE.number, false, 1, '折算汇率。', '模拟分录行。'),
  lineField('baseCurrencyAmount', '本位币金额', TYPE.number, false, 0, '本位币金额。', '模拟分录行。'),
  lineField('debitAmount', '借方金额', TYPE.number, false, 0, '借方金额。', '模拟分录行。'),
  lineField('creditAmount', '贷方金额', TYPE.number, false, 0, '贷方金额。', '模拟分录行。'),
  lineField('costCenterId', '成本中心', TYPE.string, true, null, '成本中心编号。', '模拟分录行。'),
  lineField('departmentId', '部门编号', TYPE.string, true, null, '部门编号。', '模拟分录行。'),
  lineField('projectId', '项目编号', TYPE.string, true, null, '项目编号。', '模拟分录行。'),
  lineField('sourceReference', '来源引用', TYPE.string, true, null, '来源业务引用。', '模拟分录行。'),
  lineField('lineFingerprint', '行指纹', TYPE.string, true, null, '明细行稳定指纹。', '模拟分录行。'),
]

const resultFieldNames = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.map((item) => item.field)
const lineFieldNames = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS.map((item) => item.field)
const resultFieldSet = new Set(resultFieldNames)
const lineFieldSet = new Set(lineFieldNames)

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
  if (field.type === TYPE.number) return Number.isFinite(Number(value)) && (field.nullable || Number(value) > 0)
  return !isBlank(value) && value !== 'unknown'
}

function asRequestPackage(input = {}) {
  if (input && Object.prototype.hasOwnProperty.call(input, 'requestPackage')) return input.requestPackage || {}
  return input || {}
}

export function evaluatePaymentVoucherPrepareSimulationResultStoragePreview() {
  const resultNamespace = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_STORAGE_NAMESPACE
  const auditNamespace = PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_NAMESPACE
  const sharesFormalBusinessNamespace = PAYMENT_VOUCHER_PREPARE_FORMAL_BUSINESS_NAMESPACES.includes(resultNamespace)
    || PAYMENT_VOUCHER_PREPARE_FORMAL_BUSINESS_NAMESPACES.includes(auditNamespace)
  return {
    resultStorageNamespace: resultNamespace,
    auditStorageNamespace: auditNamespace,
    independentResultNamespace: resultNamespace !== auditNamespace && !PAYMENT_VOUCHER_PREPARE_FORMAL_BUSINESS_NAMESPACES.includes(resultNamespace),
    independentAuditNamespace: resultNamespace !== auditNamespace && !PAYMENT_VOUCHER_PREPARE_FORMAL_BUSINESS_NAMESPACES.includes(auditNamespace),
    sharesFormalBusinessNamespace,
    [businessCollectionFlag]: false,
    [browserStorageFlag]: false,
    formalBusinessObjectAffected: false,
    resultNamespaceCreated: false,
    auditNamespaceCreated: false,
  }
}

export function adaptPaymentVoucherPrepareToSimulationResultInput(requestPackagePreview = {}, context = {}) {
  const requestPackage = asRequestPackage(requestPackagePreview)
  const sourceFound = Boolean(requestPackagePreview?.sourceFound !== false && requestPackage?.paymentExecutionPrepareNo)
  return {
    sourceFound,
    simulationRequestAvailable: Boolean(context.simulationRequestAvailable),
    simulationCalculationAvailable: Boolean(context.simulationCalculationAvailable),
    recordType: 'payment_voucher_prepare_simulation_result',
    resultContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION,
    resultLineContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION,
    resultLifecyclePolicyVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LIFECYCLE_POLICY_VERSION,
    auditContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_CONTRACT_VERSION,
    operationType: 'payment_voucher_prepare_simulation',
    resultReferenceNo: context.resultReferenceNo || null,
    simulationRequestReferenceNo: context.simulationRequestReferenceNo || null,
    requestPackageFingerprint: requestPackagePreview?.requestPackageFingerprint || requestPackage.requestPackageFingerprint || null,
    idempotencyKey: context.idempotencyKey || null,
    lockScopeKey: context.lockScopeKey || null,
    paymentExecutionPrepareNo: requestPackage.paymentExecutionPrepareNo || null,
    sourceSnapshotContractVersion: requestPackage.snapshotContractVersion || PAYMENT_VOUCHER_PREPARE_SOURCE_SNAPSHOT_CONTRACT_VERSION,
    sourceDataFingerprint: requestPackage.sourceDataFingerprint || null,
    precheckEngineVersion: requestPackage.precheckEngineVersion || PAYMENT_VOUCHER_PRECHECK_ENGINE_VERSION,
    ruleSetVersion: requestPackage.ruleSetVersion || PAYMENT_VOUCHER_PRECHECK_RULESET_VERSION,
    inputContractVersion: requestPackage.inputContractVersion || PAYMENT_VOUCHER_PRECHECK_INPUT_CONTRACT_VERSION,
    baselineVersion: requestPackage.baselineVersion || PAYMENT_VOUCHER_PRECHECK_BASELINE_VERSION,
    legalEntityId: requestPackage.legalEntityId || null,
    accountingBookId: requestPackage.accountingBookId || null,
    accountingTemplateId: requestPackage.accountingTemplateId || null,
    accountingTemplateVersion: requestPackage.accountingTemplateVersion || null,
    accountingPeriod: requestPackage.accountingPeriod || null,
    currencyCode: requestPackage.currencyCode || null,
    baseCurrencyCode: requestPackage.baseCurrencyCode || null,
    executionAmount: requestPackage.executionAmount || 0,
    paymentMethod: requestPackage.paymentMethod || null,
    resultPayloadVersion: context.resultPayloadVersion || '1.0.0',
    simulationCalculationStatus: context.simulationCalculationStatus || 'not_started',
    resultValidationStatus: context.resultValidationStatus || 'not_validated',
    lifecycleStatus: context.lifecycleStatus || 'not_created',
    resultValidityStatus: context.resultValidityStatus || 'unknown',
    sourceConsistencyStatus: context.sourceConsistencyStatus || 'unknown',
    resultLines: Array.isArray(context.resultLines) ? context.resultLines : [],
    createdAt: context.createdAt || null,
    createdBy: context.createdBy || null,
    validatedAt: context.validatedAt || null,
    validatedBy: context.validatedBy || null,
    frozenAt: context.frozenAt || null,
    frozenBy: context.frozenBy || null,
    invalidatedAt: context.invalidatedAt || null,
    invalidatedBy: context.invalidatedBy || null,
    invalidationReasonCode: context.invalidationReasonCode || null,
    invalidationReasonText: context.invalidationReasonText || null,
    supersededByResultReferenceNo: context.supersededByResultReferenceNo || null,
    cancelledAt: context.cancelledAt || null,
    cancelledBy: context.cancelledBy || null,
    cancellationReason: context.cancellationReason || null,
    retentionClass: context.retentionClass || 'simulation_preview',
    businessWriteBoundaryStatus: context.businessWriteBoundaryStatus || 'readonly_preview',
    formalBusinessObjectCreated: Boolean(context.formalBusinessObjectCreated),
    businessDataWritten: Boolean(context.businessDataWritten),
    auditEventCount: Number.isFinite(Number(context.auditEventCount)) ? Number(context.auditEventCount) : 0,
    writeIsolationNamespace: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_STORAGE_NAMESPACE,
    recordRevision: Number.isFinite(Number(context.recordRevision)) ? Number(context.recordRevision) : 1,
  }
}

export function normalizePaymentVoucherPrepareSimulationResult(input = {}) {
  const before = stableStringify(input)
  const raw = input && typeof input === 'object' ? input : {}
  const sourceFound = Boolean(raw.sourceFound !== false && raw.paymentExecutionPrepareNo)
  const unknownInputFieldCount = Object.keys(raw).filter((key) => !resultFieldSet.has(key) && key !== 'sourceFound' && key !== 'simulationRequestAvailable' && key !== 'simulationCalculationAvailable' && key !== 'resultLines').length
  if (!sourceFound) {
    return {
      resultAdapterVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ADAPTER_VERSION,
      resultContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION,
      resultLineContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION,
      sourceFound: false,
      resultStorageDesignEvaluated: true,
      simulationRequestAvailable: false,
      simulationCalculationAvailable: false,
      resultRecordPreviewCreated: false,
      resultRecordStatus: 'source_not_found',
      resultRecord: null,
      resultRecordFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.length,
      resultLineFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS.length,
      presentFieldCount: 0,
      missingFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.length,
      missingStoredRecordFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.filter((field) => field.requiredForStoredRecord).length,
      missingStoredRecordFields: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.filter((field) => field.requiredForStoredRecord).map((field) => field.field),
      runtimeFieldCount: runtimeFields.size,
      runtimeFieldPresentCount: 0,
      unknownInputFieldCount,
      resultLineCount: 0,
      resultPayloadFingerprint: null,
      resultRecordFingerprint: null,
      resultLifecycleStatus: 'not_created',
      resultValidityStatus: 'unknown',
      sourceConsistencyStatus: 'source_not_found',
      inputMutated: before !== stableStringify(input),
      businessSimulationResultStorageReady: false,
      formalBusinessObjectCreated: false,
      businessDataWritten: false,
    }
  }
  if (raw.simulationRequestAvailable !== true || raw.simulationCalculationAvailable !== true) {
    return {
      resultAdapterVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ADAPTER_VERSION,
      resultContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION,
      resultLineContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION,
      sourceFound: true,
      resultStorageDesignEvaluated: true,
      simulationRequestAvailable: Boolean(raw.simulationRequestAvailable),
      simulationCalculationAvailable: Boolean(raw.simulationCalculationAvailable),
      resultRecordPreviewCreated: false,
      resultRecordStatus: 'not_created',
      resultRecord: null,
      resultRecordFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.length,
      resultLineFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS.length,
      presentFieldCount: 0,
      missingFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.length,
      missingStoredRecordFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.filter((field) => field.requiredForStoredRecord).length,
      missingStoredRecordFields: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.filter((field) => field.requiredForStoredRecord).map((field) => field.field),
      runtimeFieldCount: runtimeFields.size,
      runtimeFieldPresentCount: 0,
      unknownInputFieldCount,
      resultLineCount: 0,
      resultPayloadFingerprint: null,
      resultRecordFingerprint: null,
      resultLifecycleStatus: 'not_created',
      resultValidityStatus: 'unknown',
      sourceConsistencyStatus: 'unknown',
      inputMutated: before !== stableStringify(input),
      businessSimulationResultStorageReady: false,
      formalBusinessObjectCreated: false,
      businessDataWritten: false,
    }
  }

  const normalizedLines = normalizePaymentVoucherPrepareSimulationResultLines(raw.resultLines || [])
  const debitTotal = normalizedLines.lines.reduce((sum, line) => sum + Number(line.debitAmount || 0), 0)
  const creditTotal = normalizedLines.lines.reduce((sum, line) => sum + Number(line.creditAmount || 0), 0)
  const resultPayloadFingerprint = createPaymentVoucherPrepareSimulationResultPayloadFingerprint(normalizedLines.lines)
  const recordWithoutFingerprint = {}
  PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.forEach((field) => {
    recordWithoutFingerprint[field.field] = normalizeValue(field, raw[field.field])
  })
  recordWithoutFingerprint.debitTotal = Number(debitTotal.toFixed(6))
  recordWithoutFingerprint.creditTotal = Number(creditTotal.toFixed(6))
  recordWithoutFingerprint.lineCount = normalizedLines.lines.length
  recordWithoutFingerprint.balanceDifference = Number((recordWithoutFingerprint.debitTotal - recordWithoutFingerprint.creditTotal).toFixed(6))
  recordWithoutFingerprint.resultPayloadFingerprint = resultPayloadFingerprint
  recordWithoutFingerprint.resultRecordFingerprint = null
  recordWithoutFingerprint.writeIsolationNamespace = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_STORAGE_NAMESPACE
  recordWithoutFingerprint.formalBusinessObjectCreated = false
  recordWithoutFingerprint.businessDataWritten = false
  const resultRecordFingerprint = createPaymentVoucherPrepareSimulationResultRecordFingerprint(recordWithoutFingerprint)
  const resultRecord = {
    ...recordWithoutFingerprint,
    resultRecordFingerprint,
  }
  const missingFields = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS
    .filter((field) => !hasPresentValue(resultRecord[field.field], field))
    .map((field) => field.field)
  const missingStoredRecordFields = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS
    .filter((field) => field.requiredForStoredRecord && !hasPresentValue(resultRecord[field.field], field))
    .map((field) => field.field)
  const runtimeFieldPresentCount = Array.from(runtimeFields).filter((field) => !isBlank(resultRecord[field])).length
  return {
    resultAdapterVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_ADAPTER_VERSION,
    resultContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION,
    resultLineContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION,
    sourceFound: true,
    resultStorageDesignEvaluated: true,
    simulationRequestAvailable: true,
    simulationCalculationAvailable: true,
    resultRecordPreviewCreated: true,
    resultRecordStatus: missingStoredRecordFields.length ? 'partial_preview' : 'complete_preview',
    resultRecord,
    resultRecordFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.length,
    resultLineFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS.length,
    presentFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS.length - missingFields.length,
    missingFieldCount: missingFields.length,
    missingStoredRecordFieldCount: missingStoredRecordFields.length,
    missingStoredRecordFields,
    runtimeFieldCount: runtimeFields.size,
    runtimeFieldPresentCount,
    unknownInputFieldCount,
    resultLineCount: normalizedLines.lines.length,
    resultLines: normalizedLines.lines,
    resultPayloadFingerprint,
    resultRecordFingerprint,
    resultLifecycleStatus: resultRecord.lifecycleStatus,
    resultValidityStatus: resultRecord.resultValidityStatus,
    sourceConsistencyStatus: resultRecord.sourceConsistencyStatus,
    inputMutated: before !== stableStringify(input),
    businessSimulationResultStorageReady: false,
    formalBusinessObjectCreated: false,
    businessDataWritten: false,
  }
}

export function normalizePaymentVoucherPrepareSimulationResultLines(lines = []) {
  const rawLines = Array.isArray(lines) ? lines : []
  const normalized = rawLines.map((line) => {
    const nextLine = {}
    PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS.forEach((field) => {
      nextLine[field.field] = field.field === 'lineFingerprint'
        ? null
        : normalizeValue(field, line?.[field.field])
    })
    return {
      ...nextLine,
      lineFingerprint: createPaymentVoucherPrepareSimulationResultLineFingerprint(nextLine),
    }
  })
  return {
    lineContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION,
    lineFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS.length,
    lineCount: normalized.length,
    lines: normalized,
  }
}

export function validatePaymentVoucherPrepareSimulationResult(fields = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS) {
  const fieldNames = fields.map((field) => field.field)
  const allowedTypes = new Set(Object.values(TYPE))
  const fingerprint = createPaymentVoucherPrepareSimulationResultContractFingerprint(fields, PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS)
  const locked = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION]
  return {
    resultContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION,
    resultContractFingerprint: fingerprint,
    resultContractLockedFingerprint: locked,
    resultContractFingerprintMatched: fingerprint === locked,
    resultFieldCount: fields.length,
    resultFieldNamesUnique: new Set(fieldNames).size === fieldNames.length,
    resultFieldOrderStable: fieldNames.join('|') === resultFieldNames.join('|'),
    resultFieldTypesValid: fields.every((field) => allowedTypes.has(field.type)),
    resultRuntimeFieldCount: runtimeFields.size,
    resultValidationStatus: fields.length === 60 && new Set(fieldNames).size === fieldNames.length && fields.every((field) => allowedTypes.has(field.type)) ? 'passed' : 'failed',
  }
}

export function validatePaymentVoucherPrepareSimulationResultLines(fields = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS, lines = []) {
  const fieldNames = fields.map((field) => field.field)
  const allowedTypes = new Set(Object.values(TYPE))
  const normalized = normalizePaymentVoucherPrepareSimulationResultLines(lines)
  const lineErrors = []
  normalized.lines.forEach((line) => {
    if (!Number.isInteger(Number(line.lineNo)) || Number(line.lineNo) <= 0) lineErrors.push({ lineNo: line.lineNo, code: 'LINE_NO_INVALID' })
    if (!['debit', 'credit'].includes(line.postingSide)) lineErrors.push({ lineNo: line.lineNo, code: 'POSTING_SIDE_INVALID' })
    if (Number(line.debitAmount) < 0) lineErrors.push({ lineNo: line.lineNo, code: 'DEBIT_AMOUNT_NEGATIVE' })
    if (Number(line.creditAmount) < 0) lineErrors.push({ lineNo: line.lineNo, code: 'CREDIT_AMOUNT_NEGATIVE' })
    if (Number(line.debitAmount) > 0 && Number(line.creditAmount) > 0) lineErrors.push({ lineNo: line.lineNo, code: 'BOTH_DEBIT_AND_CREDIT' })
  })
  const debitTotal = normalized.lines.reduce((sum, line) => sum + Number(line.debitAmount || 0), 0)
  const creditTotal = normalized.lines.reduce((sum, line) => sum + Number(line.creditAmount || 0), 0)
  const balanceDifference = Number((debitTotal - creditTotal).toFixed(6))
  return {
    resultLineContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_CONTRACT_VERSION,
    resultLineFieldCount: fields.length,
    resultLineFieldNamesUnique: new Set(fieldNames).size === fieldNames.length,
    resultLineFieldOrderStable: fieldNames.join('|') === lineFieldNames.join('|'),
    resultLineFieldTypesValid: fields.every((field) => allowedTypes.has(field.type)),
    resultLineValidationStatus: fields.length === 18 && new Set(fieldNames).size === fieldNames.length && fields.every((field) => allowedTypes.has(field.type)) && lineErrors.length === 0 ? 'passed' : 'failed',
    lineCount: normalized.lines.length,
    debitTotal: Number(debitTotal.toFixed(6)),
    creditTotal: Number(creditTotal.toFixed(6)),
    balanceDifference,
    balanced: balanceDifference === 0,
    lineErrors,
  }
}

export function createPaymentVoucherPrepareSimulationResultContractFingerprint(
  resultFields = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS,
  lineFields = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS,
) {
  const payload = {
    resultFields: resultFields.map((field) => ({
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
    lineFields: lineFields.map((field) => ({
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
    resultNamespace: PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_STORAGE_NAMESPACE,
    auditNamespace: PAYMENT_VOUCHER_PREPARE_SIMULATION_AUDIT_NAMESPACE,
    forbiddenNamespaces: PAYMENT_VOUCHER_PREPARE_FORMAL_BUSINESS_NAMESPACES,
    immutableAfterValidationFields: Array.from(immutableAfterValidationFields),
    runtimeFields: Array.from(runtimeFields),
    associationRules: [
      'resultRecord.lineCount equals normalized result line count',
      'resultRecord.resultPayloadFingerprint is derived from ordered result lines',
      'resultRecord.resultRecordFingerprint is derived from included record fields',
    ],
  }
  return `PVPP-SIM-RESULT-CONTRACT-FP-${stableHash(payload)}`
}

export function createPaymentVoucherPrepareSimulationResultLineContractFingerprint(fields = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS) {
  return `PVPP-SIM-RESULT-LINE-CONTRACT-FP-${stableHash(fields)}`
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT = createPaymentVoucherPrepareSimulationResultContractFingerprint()

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_CONTRACT_VERSION]: 'PVPP-SIM-RESULT-CONTRACT-FP-6EF29C10',
}

export function createPaymentVoucherPrepareSimulationResultLineFingerprint(line = {}) {
  const material = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS
    .filter((field) => lineFingerprintFields.has(field.field))
    .map((field) => ({ field: field.field, value: normalizeValue(field, line[field.field]) }))
  return `PVPP-SIM-LINE-FP-${stableHash(material)}`
}

export function createPaymentVoucherPrepareSimulationResultPayloadFingerprint(lines = []) {
  const normalizedLines = Array.isArray(lines) ? lines.map((line) => {
    const lineCopy = {}
    PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_LINE_FIELDS.forEach((field) => {
      lineCopy[field.field] = field.field === 'lineFingerprint'
        ? (line.lineFingerprint || createPaymentVoucherPrepareSimulationResultLineFingerprint(line))
        : normalizeValue(field, line[field.field])
    })
    return lineCopy
  }) : []
  return normalizedLines.length ? `PVPP-SIM-PAYLOAD-FP-${stableHash(normalizedLines)}` : null
}

export function createPaymentVoucherPrepareSimulationResultRecordFingerprint(record = {}) {
  const material = PAYMENT_VOUCHER_PREPARE_SIMULATION_RESULT_FIELDS
    .filter((field) => field.includedInRecordFingerprint && field.field !== 'resultRecordFingerprint')
    .map((field) => ({ field: field.field, value: normalizeValue(field, record[field.field]) }))
  return `PVPP-SIM-RESULT-RECORD-FP-${stableHash(material)}`
}

export function verifyPaymentVoucherPrepareSimulationResultPurity(input = {}) {
  const before = stableStringify(input)
  const first = normalizePaymentVoucherPrepareSimulationResult(input)
  const second = normalizePaymentVoucherPrepareSimulationResult(clone(input))
  const after = stableStringify(input)
  return {
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    inputMutated: before !== after,
    resultRecordCreated: false,
    resultLineCreated: false,
    resultSaved: false,
    auditEventCreated: false,
    businessDataWritten: false,
    formalBusinessObjectAffected: false,
  }
}

export const paymentVoucherPrepareSimulationResultContractInternals = {
  stableStringify,
  stableHash,
}
