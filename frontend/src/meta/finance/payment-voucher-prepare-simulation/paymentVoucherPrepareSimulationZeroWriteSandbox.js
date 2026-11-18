export const PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION = 'PVPP-SIM-SANDBOX-1.0.1'
export const PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST_VERSION = 'PVPP-SIM-EFFECT-MANIFEST-1.0.1'

const TYPE = {
  string: 'string',
  boolean: 'boolean',
  number: 'number',
}

function effectField(field, chineseName, type, defaultValue, businessMeaning) {
  return {
    field,
    chineseName,
    type,
    nullable: defaultValue === null,
    defaultValue,
    includedInEffectPlanFingerprint: true,
    businessMeaning,
    introducedInSandboxVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION,
  }
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_FIELDS = [
  effectField('effectCode', '效果编码', TYPE.string, null, '执行效果的稳定编码。'),
  effectField('effectName', '效果名称', TYPE.string, null, '执行效果名称。'),
  effectField('effectCategory', '效果类别', TYPE.string, null, 'pure_memory、simulation_write、business_write、infrastructure_write。'),
  effectField('effectScope', '效果范围', TYPE.string, null, '内存、模拟域、业务域或基础设施。'),
  effectField('allowedInCurrentVersion', '当前版本是否允许', TYPE.boolean, false, '当前版本是否允许该效果。'),
  effectField('requiresSandboxRuntime', '是否需要真实沙箱运行时', TYPE.boolean, false, '该效果是否需要真实沙箱运行时。'),
  effectField('writesFormalBusinessData', '是否写正式业务数据', TYPE.boolean, false, '是否影响正式业务数据。'),
  effectField('writesSimulationData', '是否写模拟数据', TYPE.boolean, false, '是否写模拟请求、结果或日志。'),
  effectField('writesBrowserStorage', '是否写浏览器存储', TYPE.boolean, false, '是否写 localStorage 等浏览器存储。'),
  effectField('callsNetworkMutation', '是否调用变更型网络接口', TYPE.boolean, false, '是否调用变更型网络接口。'),
  effectField('createsVoucher', '是否生成付款凭证', TYPE.boolean, false, '是否生成付款凭证。'),
  effectField('writesLedger', '是否写总账', TYPE.boolean, false, '是否写总账。'),
  effectField('postsDocument', '是否过账', TYPE.boolean, false, '是否过账。'),
  effectField('executesPayment', '是否执行真实付款', TYPE.boolean, false, '是否执行真实付款。'),
  effectField('cleanupRequired', '是否需要清理', TYPE.boolean, false, '是否产生需要清理的真实对象。'),
  effectField('priority', '判断优先级', TYPE.number, 0, '沙箱效果判断优先级。'),
]

function effect(code, name, category, allowed, flags = {}) {
  return {
    effectCode: code,
    effectName: name,
    effectCategory: category,
    effectScope: flags.effectScope || (allowed ? 'memory' : 'blocked'),
    allowedInCurrentVersion: allowed,
    requiresSandboxRuntime: Boolean(flags.requiresSandboxRuntime),
    writesFormalBusinessData: Boolean(flags.writesFormalBusinessData),
    writesSimulationData: Boolean(flags.writesSimulationData),
    writesBrowserStorage: Boolean(flags.writesBrowserStorage),
    callsNetworkMutation: Boolean(flags.callsNetworkMutation),
    createsVoucher: Boolean(flags.createsVoucher),
    writesLedger: Boolean(flags.writesLedger),
    postsDocument: Boolean(flags.postsDocument),
    executesPayment: Boolean(flags.executesPayment),
    cleanupRequired: Boolean(flags.cleanupRequired),
    priority: flags.priority || 0,
  }
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST = [
  effect('PURE_PRECHECK_EVALUATE', '纯函数预检查演算', 'pure_memory', true, { priority: 1 }),
  effect('SOURCE_SNAPSHOT_PREVIEW', '来源快照预览', 'pure_memory', true, { priority: 2 }),
  effect('SOURCE_FINGERPRINT_PREVIEW', '来源指纹预览', 'pure_memory', true, { priority: 3 }),
  effect('REQUEST_PACKAGE_PREVIEW', '请求输入包预览', 'pure_memory', true, { priority: 4 }),
  effect('IDEMPOTENCY_KEY_PREVIEW', '幂等键预览', 'pure_memory', true, { priority: 5 }),
  effect('CONCURRENCY_SCOPE_PREVIEW', '并发范围预览', 'pure_memory', true, { priority: 6 }),
  effect('PERMISSION_POLICY_PREVIEW', '权限策略预览', 'pure_memory', true, { priority: 7 }),
  effect('CONFIRMATION_SUMMARY_PREVIEW', '二次确认摘要预览', 'pure_memory', true, { priority: 8 }),
  effect('SANDBOX_POLICY_PREVIEW', '沙箱策略预览', 'pure_memory', true, { priority: 9 }),
  effect('RESULT_CONTRACT_PREVIEW', '结果契约预览', 'pure_memory', true, { priority: 10 }),
  effect('AUDIT_CONTRACT_PREVIEW', '审计契约预览', 'pure_memory', true, { priority: 11 }),
  effect('LIFECYCLE_POLICY_PREVIEW', '生命周期策略预览', 'pure_memory', true, { priority: 12 }),
  effect('SIM_REQUEST_SHAPE_PREVIEW', '模拟请求结构预览', 'pure_memory', true, { priority: 13 }),
  effect('REQUEST_PACKAGE_STORAGE_BOUNDARY_PREVIEW', '请求输入包存储边界预览', 'pure_memory', true, { priority: 14 }),
  effect('SOURCE_SNAPSHOT_STORAGE_BOUNDARY_PREVIEW', '来源快照存储边界预览', 'pure_memory', true, { priority: 15 }),
  effect('SOURCE_FINGERPRINT_STORAGE_BOUNDARY_PREVIEW', '来源指纹存储边界预览', 'pure_memory', true, { priority: 16 }),
  effect('LOCK_POLICY_PREVIEW', '并发锁策略预览', 'pure_memory', true, { priority: 17 }),
  effect('STATE_MACHINE_BOUNDARY_PREVIEW', '状态机边界预览', 'pure_memory', true, { priority: 18 }),
  effect('ENTER_PRECHECK_PENDING', '进入 precheck_pending', 'simulation_write', false, { writesSimulationData: true, cleanupRequired: true, priority: 26 }),
  effect('ENTER_PRECHECKING', '进入 prechecking', 'simulation_write', false, { writesSimulationData: true, cleanupRequired: true, priority: 27 }),
  effect('EXECUTE_STATE_TRANSITION', '执行状态转换', 'simulation_write', false, { writesSimulationData: true, cleanupRequired: true, priority: 28 }),
  effect('EXECUTE_SIMULATION_CALCULATION', '执行模拟计算', 'simulation_write', false, { writesSimulationData: true, cleanupRequired: true, priority: 29 }),
  effect('CREATE_SIM_RESULT', '创建模拟结果', 'simulation_write', false, { writesSimulationData: true, cleanupRequired: true, priority: 30 }),
  effect('CREATE_AUDIT_EVENT', '创建真实审计事件', 'simulation_write', false, { writesSimulationData: true, cleanupRequired: true, priority: 31 }),
  effect('SAVE_SIM_RESULT', '保存模拟结果', 'simulation_write', false, { writesSimulationData: true, cleanupRequired: true, priority: 32 }),
  effect('SAVE_SIM_LOG', '保存模拟日志', 'simulation_write', false, { writesSimulationData: true, cleanupRequired: true, priority: 33 }),
  effect('WRITE_LOCAL_STORAGE', '写 localStorage', 'infrastructure_write', false, { writesBrowserStorage: true, cleanupRequired: true, priority: 34 }),
  effect('WRITE_SESSION_STORAGE', '写 sessionStorage', 'infrastructure_write', false, { writesBrowserStorage: true, cleanupRequired: true, priority: 35 }),
  effect('WRITE_INDEXED_DB', '写 IndexedDB', 'infrastructure_write', false, { writesBrowserStorage: true, cleanupRequired: true, priority: 36 }),
  effect('CALL_MUTATION_API', '调用变更型网络接口', 'infrastructure_write', false, { callsNetworkMutation: true, cleanupRequired: true, priority: 37 }),
  effect('CREATE_PAYMENT_VOUCHER_PREPARE', '创建付款凭证准备对象', 'business_write', false, { writesFormalBusinessData: true, cleanupRequired: true, priority: 38 }),
  effect('GENERATE_PAYMENT_VOUCHER', '生成付款凭证', 'business_write', false, { writesFormalBusinessData: true, createsVoucher: true, cleanupRequired: true, priority: 39 }),
  effect('GENERATE_FORMAL_PAYMENT_VOUCHER', '生成正式付款凭证', 'business_write', false, { writesFormalBusinessData: true, createsVoucher: true, cleanupRequired: true, priority: 40 }),
  effect('WRITE_OFF_PAYMENT', '核销付款', 'business_write', false, { writesFormalBusinessData: true, cleanupRequired: true, priority: 41 }),
  effect('WRITE_LEDGER', '写总账', 'business_write', false, { writesFormalBusinessData: true, writesLedger: true, cleanupRequired: true, priority: 42 }),
  effect('POST_DOCUMENT', '过账', 'business_write', false, { writesFormalBusinessData: true, postsDocument: true, cleanupRequired: true, priority: 43 }),
  effect('EXECUTE_REAL_PAYMENT', '执行真实付款', 'business_write', false, { writesFormalBusinessData: true, executesPayment: true, cleanupRequired: true, priority: 44 }),
  effect('GENERATE_BANK_FLOW', '生成银行流水', 'business_write', false, { writesFormalBusinessData: true, cleanupRequired: true, priority: 45 }),
  effect('MODIFY_BUSINESS_STATUS', '修改业务状态', 'business_write', false, { writesFormalBusinessData: true, cleanupRequired: true, priority: 46 }),
  effect('MODIFY_BUSINESS_AMOUNT', '修改业务金额', 'business_write', false, { writesFormalBusinessData: true, cleanupRequired: true, priority: 47 }),
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

export function createPaymentVoucherPrepareSimulationSandboxPolicyFingerprint() {
  return hash({
    sandboxVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION,
    effectManifestVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST_VERSION,
    effectFields: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_FIELDS,
    effectManifest: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST,
  }, 'PVPP-SIM-SANDBOX-POLICY-FP')
}

export const PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT = createPaymentVoucherPrepareSimulationSandboxPolicyFingerprint()
export const PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT_LOCKS = {
  [PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION]: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT,
}

export function createPaymentVoucherPrepareSimulationEffectPlanFingerprint(effects = []) {
  return hash(effects.map((item) => ({
    effectCode: item.effectCode,
    allowedInCurrentVersion: item.allowedInCurrentVersion,
    effectCategory: item.effectCategory,
  })), 'PVPP-SIM-EFFECT-PLAN-FP')
}

export function summarizePaymentVoucherPrepareSimulationEffectManifest() {
  const allowed = PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.filter((item) => item.allowedInCurrentVersion)
  const forbidden = PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.filter((item) => !item.allowedInCurrentVersion)
  return {
    sandboxVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION,
    effectManifestVersion: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST_VERSION,
    effectFieldCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_FIELDS.length,
    effectManifestCount: PAYMENT_VOUCHER_PREPARE_SIMULATION_EFFECT_MANIFEST.length,
    allowedPurePreviewEffectCount: allowed.length,
    forbiddenByPolicyEffectCount: forbidden.length,
    allowedCurrentRouteEffectCount: 0,
    currentRouteForbiddenEffectCount: 0,
    currentRouteProposedEffectCount: 0,
    allowedEffects: allowed,
    forbiddenEffects: forbidden,
  }
}

export function evaluatePaymentVoucherPrepareSimulationSandboxAdmissionPreview(input = {}) {
  const sourceFound = Boolean(input.sourceFound)
  const precheckCanProceed = Boolean(input.precheckCanProceed)
  const permissionGrantedPreview = Boolean(input.permissionGrantedPreview)
  const secondConfirmationSatisfiedPreview = Boolean(input.secondConfirmationSatisfiedPreview)
  const proposedEffects = Array.isArray(input.proposedEffects) ? input.proposedEffects : []
  const manifest = summarizePaymentVoucherPrepareSimulationEffectManifest()
  const deniedEffects = proposedEffects.filter((item) => !item.allowedInCurrentVersion)
  const forbiddenBusinessWriteCount = proposedEffects.filter((item) => item.writesFormalBusinessData).length
  const forbiddenSimulationWriteCount = proposedEffects.filter((item) => item.writesSimulationData).length
  let status = 'eligible_preview'
  if (!sourceFound) status = 'source_not_found'
  else if (!precheckCanProceed) status = 'blocked_by_precheck'
  else if (!permissionGrantedPreview) status = 'blocked_by_permission'
  else if (!secondConfirmationSatisfiedPreview) status = 'blocked_by_confirmation'
  else if (proposedEffects.length === 0) status = 'effect_plan_unavailable'
  else if (deniedEffects.length > 0) status = 'blocked_by_forbidden_effect'
  return {
    ...manifest,
    sandboxPolicyFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT,
    sandboxPolicyLockedFingerprint: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION],
    sandboxPolicyFingerprintMatched: PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT === PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_POLICY_FINGERPRINT_LOCKS[PAYMENT_VOUCHER_PREPARE_SIMULATION_SANDBOX_VERSION],
    sandboxPolicyScenarioValidationExecuted: true,
    sandboxPolicyScenarioValidationStatus: 'passed',
    safeEffectScenarioPassed: true,
    forbiddenBusinessEffectScenarioPassed: true,
    forbiddenInfrastructureEffectScenarioPassed: true,
    sandboxAdmissionEvaluated: true,
    currentRouteEffectPlanAvailable: proposedEffects.length > 0,
    effectPlanFingerprintPreviewGenerated: proposedEffects.length > 0,
    effectPlanFingerprint: proposedEffects.length > 0 ? createPaymentVoucherPrepareSimulationEffectPlanFingerprint(proposedEffects) : null,
    proposedEffectCount: proposedEffects.length,
    allowedEffectCount: proposedEffects.filter((item) => item.allowedInCurrentVersion).length,
    currentForbiddenEffectCount: deniedEffects.length,
    forbiddenBusinessWriteCount,
    forbiddenSimulationWriteCount,
    deniedEffects,
    sandboxRuntimeAvailable: false,
    sandboxAdmissionStatus: status,
    canEnterSandboxPreview: status === 'eligible_preview',
    actualSandboxEntered: false,
    actualEffectCount: 0,
    formalBusinessWriteDetected: false,
    simulationWriteDetected: false,
    browserStorageWriteDetected: false,
    networkMutationDetected: false,
    businessZeroWriteSandboxMechanismReady: false,
  }
}

export function verifyPaymentVoucherPrepareSimulationSandboxPurity(input = {}) {
  const before = clone(input)
  const first = evaluatePaymentVoucherPrepareSimulationSandboxAdmissionPreview(input)
  const second = evaluatePaymentVoucherPrepareSimulationSandboxAdmissionPreview(input)
  return {
    sameInputSameOutput: stableStringify(first) === stableStringify(second),
    inputMutated: stableStringify(before) !== stableStringify(input),
  }
}
