export const PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION = 'PVPP-SIM-PERMISSION-1.0.0'
export const PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_REQUIRED_CODE = 'finance.paymentVoucherPrepare.simulation.execute'

const TYPE = {
  string: 'string',
  boolean: 'boolean',
  stringList: 'string_list',
}

const fingerprintFields = new Set([
  'contextType',
  'operationType',
  'requiredPermissionCode',
  'actorId',
  'actorStatus',
  'authenticated',
  'mfaVerified',
  'permissionCodes',
  'roleCodes',
  'organizationId',
  'legalEntityId',
  'accountingBookId',
  'dataScopeType',
  'dataScopeValues',
  'delegationReferenceNo',
  'delegationActive',
  'runtimeContextAvailable',
  'paymentExecutionPrepareNo',
  'sourceFound',
])

function field(fieldName, chineseName, type, nullable, requiredForGrantedPreview, defaultValue, businessMeaning, sourceDescription) {
  return {
    field: fieldName,
    chineseName,
    type,
    nullable,
    requiredForPolicyPreview: true,
    requiredForGrantedPreview,
    includedInDecisionFingerprint: fingerprintFields.has(fieldName),
    defaultValue,
    businessMeaning,
    sourceDescription,
    introducedInPermissionVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION,
  }
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS = [
  field('contextType', '权限上下文类型', TYPE.string, false, false, 'payment_voucher_prepare_simulation_permission', '标识权限上下文用途。', '固定设计字段。'),
  field('operationType', '操作类型', TYPE.string, false, false, 'payment_voucher_prepare_simulation', '标识模拟执行权限动作。', '固定设计字段。'),
  field('requiredPermissionCode', '所需权限点', TYPE.string, false, true, PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_REQUIRED_CODE, '本动作要求的权限点。', '固定策略字段。'),
  field('actorId', '操作人', TYPE.string, true, true, null, '未来身份运行时提供，本轮不推断。', '未来正式权限运行时。'),
  field('actorStatus', '操作人状态', TYPE.string, true, true, null, '未来身份运行时提供。', '未来正式权限运行时。'),
  field('authenticated', '是否已认证', TYPE.boolean, false, true, false, '未来认证运行时提供。', '未来正式权限运行时。'),
  field('mfaVerified', '是否通过 MFA', TYPE.boolean, false, true, false, '未来 MFA 运行时提供。', '未来正式权限运行时。'),
  field('permissionCodes', '权限点列表', TYPE.stringList, false, true, [], '未来权限运行时提供。', '未来正式权限运行时。'),
  field('roleCodes', '角色列表', TYPE.stringList, false, true, [], '未来角色运行时提供。', '未来正式权限运行时。'),
  field('organizationId', '组织编号', TYPE.string, true, true, null, '未来数据范围判断使用。', '未来正式权限运行时。'),
  field('legalEntityId', '法人主体', TYPE.string, true, true, null, '当前来源法人主体。', '来源对象。'),
  field('accountingBookId', '账套编号', TYPE.string, true, true, null, '当前来源账套。', '来源对象。'),
  field('dataScopeType', '数据范围类型', TYPE.string, true, true, null, '未来数据权限范围类型。', '未来正式权限运行时。'),
  field('dataScopeValues', '数据范围值', TYPE.stringList, false, true, [], '未来数据权限范围值。', '未来正式权限运行时。'),
  field('delegationReferenceNo', '委托授权编号', TYPE.string, true, false, null, '未来委托授权编号。', '未来正式权限运行时。'),
  field('delegationActive', '委托是否有效', TYPE.boolean, false, false, false, '未来委托授权有效性。', '未来正式权限运行时。'),
  field('sessionReferenceNo', '会话编号', TYPE.string, true, true, null, '未来认证会话编号，本轮不生成。', '未来正式权限运行时。'),
  field('runtimeContextAvailable', '运行时上下文是否可用', TYPE.boolean, false, true, false, '是否存在正式身份权限运行时。', '未来正式权限运行时。'),
  field('paymentExecutionPrepareNo', '付款执行准备单号', TYPE.string, true, true, null, '当前路由来源单号。', '页面当前路由。'),
  field('sourceFound', '来源是否存在', TYPE.boolean, false, true, false, '付款执行准备来源是否存在。', '页面当前路由。'),
]

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_MANIFEST = [
  { priority: 1, status: 'source_not_found', rule: 'sourceFound=false 时优先阻断。' },
  { priority: 2, status: 'no_runtime_context', rule: '未接入正式身份权限运行时时阻断。' },
  { priority: 3, status: 'unauthenticated', rule: '未认证时阻断。' },
  { priority: 4, status: 'actor_inactive', rule: '操作人非 active 时阻断。' },
  { priority: 5, status: 'mfa_required', rule: '未通过 MFA 时阻断。' },
  { priority: 6, status: 'permission_missing', rule: '缺少指定权限点时阻断。' },
  { priority: 7, status: 'data_scope_mismatch', rule: '法人或账套不在数据范围时阻断。' },
  { priority: 8, status: 'delegation_invalid', rule: '存在委托编号但委托无效时阻断。' },
  { priority: 9, status: 'granted_preview', rule: '全部满足时仅返回授权预览。' },
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

const defaultByField = Object.fromEntries(PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS.map((item) => [item.field, clone(item.defaultValue)]))

export function normalizePaymentVoucherPrepareSimulationPermissionContext(input = {}) {
  return PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS.reduce((acc, item) => {
    const provided = Object.prototype.hasOwnProperty.call(input, item.field) ? input[item.field] : clone(item.defaultValue)
    if (item.type === TYPE.boolean) acc[item.field] = Boolean(provided)
    else if (item.type === TYPE.stringList) acc[item.field] = Array.isArray(provided) ? provided.map((value) => String(value)) : []
    else acc[item.field] = provided === undefined ? clone(defaultByField[item.field]) : provided
    return acc
  }, {})
}

export function validatePaymentVoucherPrepareSimulationPermissionContext(input = {}) {
  const normalized = normalizePaymentVoucherPrepareSimulationPermissionContext(input)
  const missingRequiredFields = PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS
    .filter((item) => item.requiredForPolicyPreview && !item.nullable && normalized[item.field] === null)
    .map((item) => item.field)
  return {
    permissionVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION,
    permissionContextFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS.length,
    valid: missingRequiredFields.length === 0,
    missingRequiredFields,
    normalized,
  }
}

export function createPaymentVoucherPrepareSimulationPermissionPolicyFingerprint() {
  return hash({
    version: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION,
    requiredPermissionCode: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_REQUIRED_CODE,
    fields: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS,
    manifest: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_MANIFEST,
  }, 'PVPP-SIM-PERMISSION-POLICY-FP')
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT = createPaymentVoucherPrepareSimulationPermissionPolicyFingerprint()
export const PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION]: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT,
}

export function createPaymentVoucherPrepareSimulationPermissionDecisionFingerprint(context = {}, status = 'invalid') {
  const normalized = normalizePaymentVoucherPrepareSimulationPermissionContext(context)
  const material = PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_CONTEXT_FIELDS
    .filter((item) => item.includedInDecisionFingerprint)
    .reduce((acc, item) => {
      acc[item.field] = normalized[item.field]
      return acc
    }, { permissionDecisionStatus: status })
  return hash(material, 'PVPP-SIM-PERMISSION-DECISION-FP')
}

function dataScopeMatched(context) {
  if (context.dataScopeType === 'all') return true
  if (context.dataScopeType === 'legal_entity') return Boolean(context.legalEntityId && context.dataScopeValues.includes(context.legalEntityId))
  if (context.dataScopeType === 'accounting_book') return Boolean(context.accountingBookId && context.dataScopeValues.includes(context.accountingBookId))
  return false
}

export function evaluatePaymentVoucherPrepareSimulationPermissionPreview(input = {}) {
  const original = clone(input)
  const context = normalizePaymentVoucherPrepareSimulationPermissionContext(input)
  let status = 'granted_preview'
  if (!context.sourceFound) status = 'source_not_found'
  else if (!context.runtimeContextAvailable) status = 'no_runtime_context'
  else if (!context.authenticated) status = 'unauthenticated'
  else if (context.actorStatus !== 'active') status = 'actor_inactive'
  else if (!context.mfaVerified) status = 'mfa_required'
  else if (!context.permissionCodes.includes(PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_REQUIRED_CODE)) status = 'permission_missing'
  else if (!dataScopeMatched(context)) status = 'data_scope_mismatch'
  else if (context.delegationReferenceNo && !context.delegationActive) status = 'delegation_invalid'

  const granted = status === 'granted_preview'
  return {
    permissionVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION,
    permissionPolicyFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT,
    permissionPolicyLockedFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION],
    permissionPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_VERSION],
    sourceFound: context.sourceFound,
    permissionEvaluationExecuted: true,
    runtimeContextAvailable: context.runtimeContextAvailable,
    requiredPermissionCode: context.requiredPermissionCode,
    actorId: context.actorId,
    authenticationEvaluated: context.runtimeContextAvailable,
    authenticated: context.authenticated,
    actorStatusEvaluated: context.runtimeContextAvailable && context.authenticated,
    actorActive: context.actorStatus === 'active',
    mfaEvaluated: context.runtimeContextAvailable && context.authenticated,
    mfaVerified: context.mfaVerified,
    permissionCodeMatched: context.permissionCodes.includes(PAYMENT_VOUCHER_PREPARE_SIMULATION_PERMISSION_REQUIRED_CODE),
    dataScopeEvaluated: context.runtimeContextAvailable && context.authenticated,
    dataScopeMatched: dataScopeMatched(context),
    delegationEvaluated: Boolean(context.delegationReferenceNo),
    delegationValid: !context.delegationReferenceNo || context.delegationActive,
    permissionDecisionStatus: status,
    permissionGrantedPreview: granted,
    permissionDecisionFingerprintPreviewGenerated: granted,
    permissionDecisionFingerprint: granted ? createPaymentVoucherPrepareSimulationPermissionDecisionFingerprint(context, status) : null,
    actualPermissionGranted: false,
    businessPermissionMechanismReady: false,
    inputMutated: stableStringify(original) !== stableStringify(input),
  }
}

export function verifyPaymentVoucherPrepareSimulationPermissionPurity(input = {}) {
  const before = clone(input)
  const first = evaluatePaymentVoucherPrepareSimulationPermissionPreview(input)
  const second = evaluatePaymentVoucherPrepareSimulationPermissionPreview(input)
  return {
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    inputMutated: stableStringify(before) !== stableStringify(input),
  }
}
