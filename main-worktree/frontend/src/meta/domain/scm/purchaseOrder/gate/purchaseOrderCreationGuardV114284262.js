export const PURCHASE_ORDER_CREATION_GUARD_VERSION_V114284262 = 'V1.14.2.8.4.26.2'
export const PURCHASE_ORDER_CREATION_GUARD_CODE_V114284262 = 'PURCHASE_ORDER_CREATION_GUARD_V114284262'

const text = value => String(value ?? '').trim()
const list = value => Array.isArray(value) ? value : []
const freeze = value => Object.freeze(value)

function check(checkCode, checkName, currentValue, passed, blockedReason) {
  return freeze({ checkCode, checkName, currentValue, passed: Boolean(passed),
    result: passed ? 'PASS' : 'FAIL', reason: passed ? '条件满足' : blockedReason,
    blockedReason: passed ? '' : blockedReason })
}

export function evaluatePurchaseOrderCreationGuardV114284262({
  gate = {}, admissionResult = {}, creationEntry = {},
} = {}) {
  const admissionChecks = list(admissionResult.checks)
  const checks = freeze([
    check('PURCHASE_ORDER_GATE_EXISTS', '存在采购订单准入Gate',
      `${gate.objectType || 'missing'}:${gate.gateId || 'missing'}`,
      gate.objectType === 'SupplierRecommendationGate' && text(gate.gateId),
      '未找到有效的PurchaseOrderGate，禁止进入采购订单创建'),
    check('PURCHASE_ORDER_GATE_READY', 'Gate状态允许创建采购订单',
      text(gate.status) || 'missing',
      gate.status === 'READY_FOR_PURCHASE_ORDER'
        && gate.purchaseOrderCreationAllowed === true
        && gate.purchaseOrderCreationEntryReady === true
        && gate.purchaseOrderCreated === false,
      'Gate尚未达到READY_FOR_PURCHASE_ORDER'),
    check('PURCHASE_ORDER_GATE_MANUALLY_CONFIRMED', 'Gate已完成人工确认',
      `${text(gate.confirmedBy) || 'missing'}@${text(gate.confirmedAt) || 'missing'}`,
      Boolean(text(gate.confirmedBy) && text(gate.confirmedAt)),
      'Gate缺少确认人或确认时间'),
    check('PURCHASE_ORDER_ADMISSION_PASSED', '采购订单准入检查通过',
      `${admissionResult.status || 'missing'};checks=${admissionChecks.length}`,
      admissionResult.objectType === 'PurchaseOrderAdmissionResult'
        && admissionResult.gateId === gate.gateId
        && admissionResult.sourceSignature === gate.sourceSignature
        && admissionResult.status === 'READY_FOR_PURCHASE_ORDER'
        && admissionResult.purchaseOrderCreationAllowed === true
        && admissionResult.purchaseOrderCreated === false
        && admissionChecks.length > 0
        && admissionChecks.every(item => item.result === 'PASS' && item.passed === true),
      'PurchaseOrderAdmissionGuard未通过或准入证据与当前Gate不一致'),
    check('PURCHASE_ORDER_CREATION_ENTRY_MATCHED', '创建入口与准入结果一致',
      `${creationEntry.objectType || 'missing'}:${creationEntry.gateId || 'missing'}`,
      creationEntry.objectType === 'PurchaseOrderCreationEntry'
        && creationEntry.gateId === gate.gateId
        && creationEntry.sourceObjectId === admissionResult.admissionResultId
        && creationEntry.createActionExecuted === false
        && creationEntry.purchaseOrderCreated === false,
      'PurchaseOrderCreationEntry不存在或与当前准入结果不一致'),
  ])
  const blockedReasons = freeze(checks.filter(item => !item.passed)
    .map(item => item.blockedReason))
  const passed = blockedReasons.length === 0
  return freeze({
    objectType: 'PurchaseOrderCreationGuardResult',
    guardCode: PURCHASE_ORDER_CREATION_GUARD_CODE_V114284262,
    result: passed ? 'PASS' : 'FAIL',
    decision: passed ? 'allow' : 'block',
    checks,
    blockedReasons,
    gateId: text(gate.gateId),
    admissionResultId: text(admissionResult.admissionResultId),
    sourceSignature: text(gate.sourceSignature),
    purchaseOrderCreationAllowed: passed,
    purchaseOrderCreated: false,
    automaticPurchaseOrderCreation: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function assertPurchaseOrderCreationGuardV114284262(context = {}) {
  const result = evaluatePurchaseOrderCreationGuardV114284262(context)
  if (result.result !== 'PASS') {
    return freeze({ success: false, result: 'BLOCKED',
      error: 'PURCHASE_ORDER_GATE_REQUIRED', reason: result.blockedReasons.join('；'),
      guard: result, businessWriteCount: 0, productionDataWritten: false,
      purchaseOrderCreated: false })
  }
  return freeze({ success: true, result: 'PASS', guard: result,
    businessWriteCount: 0, productionDataWritten: false, purchaseOrderCreated: false })
}
