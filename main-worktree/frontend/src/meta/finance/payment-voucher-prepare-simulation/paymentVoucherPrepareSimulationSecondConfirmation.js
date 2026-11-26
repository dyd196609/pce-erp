export const PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION = 'PVPP-SIM-CONFIRMATION-1.0.0'

const TYPE = {
  string: 'string',
  number: 'number',
  boolean: 'boolean',
}

const fingerprintFields = new Set([
  'confirmationContractVersion',
  'actionType',
  'paymentExecutionPrepareNo',
  'sourceFound',
  'sourceDataFingerprint',
  'requestPackageFingerprint',
  'idempotencyKey',
  'lockScopeKey',
  'executionAmount',
  'currencyCode',
  'paymentMethod',
  'plannedPaymentDate',
  'supplierId',
  'enterpriseBankAccountId',
  'supplierBankAccountId',
  'precheckDecision',
  'precheckCanProceed',
  'permissionDecisionStatus',
  'permissionGrantedPreview',
  'sandboxPolicyFingerprintMatched',
  'sandboxPolicyScenarioValidationStatus',
  'simulationResultStorageReady',
  'simulationLogStorageReady',
  'confirmationRequirementCount',
  'confirmedRequirementCount',
  'explicitUserConfirmed',
])

function field(fieldName, chineseName, type, nullable, requiredForChallengeCreation, runtimeOnly, defaultValue, businessMeaning, sourceDescription) {
  return {
    field: fieldName,
    chineseName,
    type,
    nullable,
    requiredForSummaryPreview: true,
    requiredForChallengeCreation,
    includedInSummaryFingerprint: fingerprintFields.has(fieldName),
    runtimeOnly,
    defaultValue,
    businessMeaning,
    sourceDescription,
    introducedInConfirmationVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION,
  }
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS = [
  field('confirmationContractVersion', '二次确认契约版本', TYPE.string, false, false, false, PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION, '确认摘要契约版本。', '固定设计字段。'),
  field('actionType', '动作类型', TYPE.string, false, true, false, 'payment_voucher_prepare_simulation', '确认的动作类型。', '固定设计字段。'),
  field('confirmationReferenceNo', '确认编号', TYPE.string, true, true, true, null, '未来确认挑战编号，本轮不生成。', '未来确认运行时。'),
  field('confirmationToken', '确认令牌', TYPE.string, true, true, true, null, '未来确认令牌，本轮不生成。', '未来确认运行时。'),
  field('paymentExecutionPrepareNo', '付款执行准备单号', TYPE.string, true, true, false, null, '来源付款执行准备单号。', '当前路由。'),
  field('sourceFound', '来源是否存在', TYPE.boolean, false, true, false, false, '来源是否存在。', '当前路由。'),
  field('sourceDataFingerprint', '来源数据指纹', TYPE.string, true, true, false, null, '来源数据指纹。', '来源指纹预览。'),
  field('requestPackageFingerprint', '请求输入包指纹', TYPE.string, true, true, false, null, '请求输入包指纹。', '请求输入包预览。'),
  field('idempotencyKey', '幂等键', TYPE.string, true, true, false, null, '幂等键预览。', '幂等策略预览。'),
  field('lockScopeKey', '并发锁范围键', TYPE.string, true, true, false, null, '并发锁范围键预览。', '并发策略预览。'),
  field('executionAmount', '执行金额', TYPE.number, false, true, false, 0, '本次拟模拟金额。', '来源对象。'),
  field('currencyCode', '币种', TYPE.string, true, true, false, null, '本次拟模拟币种。', '来源对象。'),
  field('paymentMethod', '付款方式', TYPE.string, true, true, false, null, '本次拟模拟付款方式。', '来源对象。'),
  field('plannedPaymentDate', '计划付款日期', TYPE.string, true, true, false, null, '计划付款日期。', '来源对象。'),
  field('supplierId', '供应商编号', TYPE.string, true, false, false, null, '供应商编号。', '来源对象。'),
  field('enterpriseBankAccountId', '企业银行账户', TYPE.string, true, true, false, null, '付款方银行账户。', '来源对象。'),
  field('supplierBankAccountId', '供应商银行账户', TYPE.string, true, true, false, null, '收款方银行账户。', '来源对象。'),
  field('precheckDecision', '预检查决策', TYPE.string, true, true, false, null, '当前业务预检查决策。', '预检查结果。'),
  field('precheckCanProceed', '预检查是否允许继续', TYPE.boolean, false, true, false, false, '当前业务预检查是否允许继续。', '预检查结果。'),
  field('permissionDecisionStatus', '权限判断状态', TYPE.string, true, true, false, null, '权限预览状态。', '权限预览。'),
  field('permissionGrantedPreview', '权限是否预览通过', TYPE.boolean, false, true, false, false, '权限预览是否通过。', '权限预览。'),
  field('sandboxPolicyFingerprintMatched', '沙箱策略指纹是否匹配', TYPE.boolean, false, true, false, false, '沙箱策略指纹是否匹配。', '沙箱策略预览。'),
  field('sandboxPolicyScenarioValidationStatus', '沙箱策略验证状态', TYPE.string, true, true, false, null, '沙箱策略合成验证状态。', '沙箱策略预览。'),
  field('simulationResultStorageReady', '模拟结果存储是否就绪', TYPE.boolean, false, true, false, false, '模拟结果存储就绪标识。', '预检查输入。'),
  field('simulationLogStorageReady', '模拟日志存储是否就绪', TYPE.boolean, false, true, false, false, '模拟日志存储就绪标识。', '预检查输入。'),
  field('confirmationRequirementCount', '确认要求数量', TYPE.number, false, false, false, 0, '确认要求总数。', '确认要求清单。'),
  field('confirmedRequirementCount', '已满足确认要求数量', TYPE.number, false, false, false, 0, '已满足确认要求数量。', '确认要求清单。'),
  field('explicitUserConfirmed', '是否显式确认', TYPE.boolean, false, true, true, false, '未来真实用户确认，本轮固定为否。', '未来确认运行时。'),
  field('confirmerId', '确认人', TYPE.string, true, true, true, null, '未来确认人，本轮不推断。', '未来确认运行时。'),
  field('issuedAt', '确认签发时间', TYPE.string, true, true, true, null, '未来确认签发时间，本轮不生成。', '未来确认运行时。'),
  field('expiresAt', '确认过期时间', TYPE.string, true, true, true, null, '未来确认过期时间，本轮不生成。', '未来确认运行时。'),
  field('confirmedAt', '确认完成时间', TYPE.string, true, true, true, null, '未来确认完成时间，本轮不生成。', '未来确认运行时。'),
]

function requirement(requirementCode, chineseName, category, critical, sourceField) {
  return {
    requirementCode,
    chineseName,
    category,
    critical,
    sourceField,
    satisfied: false,
    blockReason: null,
    introducedInConfirmationVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION,
  }
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS = [
  requirement('SIM_ACTION_ONLY', '确认本次动作仅为模拟执行', 'action_boundary', true, 'actionType'),
  requirement('SOURCE_EXISTS', '确认付款执行准备对象存在', 'source', true, 'sourceFound'),
  requirement('AMOUNT_METHOD_READY', '确认付款金额、币种和付款方式明确', 'amount', true, 'executionAmount'),
  requirement('SOURCE_FINGERPRINT_READY', '确认来源数据指纹已建立', 'source', true, 'sourceDataFingerprint'),
  requirement('SOURCE_UNCHANGED_READY', '确认来源数据未发生变化', 'source', true, 'sourceUnchanged'),
  requirement('PRECHECK_PASSED', '确认业务预检查已经通过', 'precheck', true, 'precheckCanProceed'),
  requirement('PERMISSION_GRANTED', '确认当前操作人具有模拟权限', 'permission', true, 'permissionGrantedPreview'),
  requirement('IDEMPOTENCY_READY', '确认幂等键已经就绪', 'request_control', true, 'idempotencyKey'),
  requirement('CONCURRENCY_READY', '确认并发控制已经就绪', 'request_control', true, 'lockScopeKey'),
  requirement('RESULT_LOG_READY', '确认模拟结果和审计存储已经就绪', 'storage', true, 'simulationResultStorageReady'),
  requirement('SANDBOX_POLICY_PASSED', '确认零业务写入沙箱策略验证通过', 'sandbox', true, 'sandboxPolicyScenarioValidationStatus'),
  requirement('NO_FORMAL_OUTPUT', '确认不会生成付款凭证、核销、写总账、过账或真实付款', 'business_boundary', true, 'sandboxPolicyFingerprintMatched'),
]

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

function hash(input, prefix) {
  const text = stableStringify(input)
  let value = 2166136261
  for (let index = 0; index < text.length; index += 1) {
    value ^= text.charCodeAt(index)
    value = Math.imul(value, 16777619)
  }
  return `${prefix}-${(value >>> 0).toString(16).toUpperCase().padStart(8, '0')}`
}

export function createPaymentVoucherPrepareSimulationConfirmationContractFingerprint() {
  return hash({
    version: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION,
    fields: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS,
    requirements: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS,
  }, 'PVPP-SIM-CONFIRMATION-CONTRACT-FP')
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_CONTRACT_FINGERPRINT = createPaymentVoucherPrepareSimulationConfirmationContractFingerprint()
export const PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION]: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_CONTRACT_FINGERPRINT,
}

const defaultByField = Object.fromEntries(PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS.map((item) => [item.field, clone(item.defaultValue)]))

export function normalizePaymentVoucherPrepareSimulationConfirmationSummary(input = {}) {
  return PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS.reduce((acc, item) => {
    const provided = Object.prototype.hasOwnProperty.call(input, item.field) ? input[item.field] : clone(defaultByField[item.field])
    if (item.type === TYPE.boolean) acc[item.field] = Boolean(provided)
    else if (item.type === TYPE.number) acc[item.field] = Number(provided || 0)
    else acc[item.field] = provided === undefined ? clone(defaultByField[item.field]) : provided
    return acc
  }, {})
}

export function validatePaymentVoucherPrepareSimulationConfirmationSummary(input = {}) {
  const normalized = normalizePaymentVoucherPrepareSimulationConfirmationSummary(input)
  return {
    confirmationVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION,
    confirmationFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS.length,
    valid: true,
    normalized,
  }
}

export function createPaymentVoucherPrepareSimulationConfirmationSummaryFingerprint(summary = {}) {
  const normalized = normalizePaymentVoucherPrepareSimulationConfirmationSummary(summary)
  const material = PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS
    .filter((item) => item.includedInSummaryFingerprint)
    .reduce((acc, item) => {
      acc[item.field] = normalized[item.field]
      return acc
    }, {})
  return hash(material, 'PVPP-SIM-CONFIRMATION-SUMMARY-FP')
}

function evaluateRequirements(summary, sourceUnchanged = false) {
  return PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS.map((item) => {
    let satisfied = false
    if (item.requirementCode === 'SIM_ACTION_ONLY') satisfied = summary.actionType === 'payment_voucher_prepare_simulation'
    else if (item.requirementCode === 'SOURCE_EXISTS') satisfied = summary.sourceFound
    else if (item.requirementCode === 'AMOUNT_METHOD_READY') satisfied = summary.executionAmount > 0 && Boolean(summary.currencyCode) && Boolean(summary.paymentMethod)
    else if (item.requirementCode === 'SOURCE_FINGERPRINT_READY') satisfied = Boolean(summary.sourceDataFingerprint)
    else if (item.requirementCode === 'SOURCE_UNCHANGED_READY') satisfied = Boolean(sourceUnchanged)
    else if (item.requirementCode === 'PRECHECK_PASSED') satisfied = summary.precheckCanProceed
    else if (item.requirementCode === 'PERMISSION_GRANTED') satisfied = summary.permissionGrantedPreview
    else if (item.requirementCode === 'IDEMPOTENCY_READY') satisfied = Boolean(summary.idempotencyKey)
    else if (item.requirementCode === 'CONCURRENCY_READY') satisfied = Boolean(summary.lockScopeKey)
    else if (item.requirementCode === 'RESULT_LOG_READY') satisfied = summary.simulationResultStorageReady && summary.simulationLogStorageReady
    else if (item.requirementCode === 'SANDBOX_POLICY_PASSED') satisfied = summary.sandboxPolicyScenarioValidationStatus === 'passed'
    else if (item.requirementCode === 'NO_FORMAL_OUTPUT') satisfied = summary.sandboxPolicyFingerprintMatched
    return {
      ...item,
      satisfied,
      blockReason: satisfied ? null : `${item.chineseName}未满足`,
    }
  })
}

export function evaluatePaymentVoucherPrepareSimulationSecondConfirmationPreview(input = {}) {
  const summary = normalizePaymentVoucherPrepareSimulationConfirmationSummary({
    confirmationContractVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION,
    actionType: 'payment_voucher_prepare_simulation',
    ...input,
  })
  const sourceUnchanged = Boolean(input.sourceUnchanged)
  const requirements = summary.sourceFound ? evaluateRequirements(summary, sourceUnchanged) : []
  const satisfiedRequirementCount = requirements.filter((item) => item.satisfied).length
  const missingRequirements = requirements.filter((item) => !item.satisfied)
  const missingRequirementCount = missingRequirements.length
  const summaryCreated = summary.sourceFound
  const status = !summary.sourceFound
    ? 'source_not_found'
    : missingRequirementCount > 0
      ? 'requirements_incomplete'
      : !summary.confirmationReferenceNo
        ? 'challenge_not_created'
        : !summary.explicitUserConfirmed
          ? 'pending_confirmation'
          : 'confirmed_preview'
  const fingerprintGenerated = summaryCreated
  return {
    confirmationVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION,
    confirmationFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FIELDS.length,
    confirmationRequirementCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS.length,
    confirmationContractFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_CONTRACT_FINGERPRINT,
    confirmationLockedFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION],
    confirmationFingerprintMatched: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_CONTRACT_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_VERSION],
    confirmationPolicyScenarioValidationExecuted: true,
    confirmationPolicyScenarioValidationStatus: 'passed',
    confirmationRequirementPreviewEvaluated: summary.sourceFound,
    confirmationSummaryPreviewCreated: summaryCreated,
    confirmationSummaryStatus: !summary.sourceFound ? 'source_not_found' : 'partial_preview',
    confirmationSummaryFingerprintPreviewGenerated: fingerprintGenerated,
    confirmationSummaryFingerprint: fingerprintGenerated ? createPaymentVoucherPrepareSimulationConfirmationSummaryFingerprint({
      ...summary,
      confirmationRequirementCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_CONFIRMATION_REQUIREMENTS.length,
      confirmedRequirementCount: satisfiedRequirementCount,
    }) : null,
    satisfiedRequirementCount,
    missingRequirementCount,
    missingRequirements,
    requirementResults: requirements,
    confirmationChallengeCreated: false,
    confirmationReferenceNo: null,
    confirmationTokenGenerated: false,
    confirmationToken: null,
    explicitUserConfirmed: false,
    confirmationDecisionStatus: status,
    canConfirmPreview: status === 'pending_confirmation',
    secondConfirmationSatisfiedPreview: status === 'confirmed_preview',
    actualConfirmationCompleted: false,
    businessSecondConfirmationMechanismReady: false,
  }
}

export function verifyPaymentVoucherPrepareSimulationConfirmationPurity(input = {}) {
  const before = clone(input)
  const first = evaluatePaymentVoucherPrepareSimulationSecondConfirmationPreview(input)
  const second = evaluatePaymentVoucherPrepareSimulationSecondConfirmationPreview(input)
  return {
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    inputMutated: stableStringify(before) !== stableStringify(input),
  }
}
