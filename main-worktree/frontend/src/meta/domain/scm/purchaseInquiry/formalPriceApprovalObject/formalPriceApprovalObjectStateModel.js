export const FORMAL_PRICE_APPROVAL_OBJECT_STATE_MODEL_VERSION = 'V1.14.2.8.6.6'

export const FORMAL_PRICE_APPROVAL_OBJECT_STATE_DEFINITIONS = Object.freeze([
  Object.freeze({ code: 'definition_only', label: '仅模型定义', currentAllowed: true }),
  Object.freeze({ code: 'ready_for_creation', label: '具备未来创建条件', currentAllowed: true }),
  Object.freeze({ code: 'created', label: '已创建', currentAllowed: false }),
  Object.freeze({ code: 'pending_approval', label: '等待审批', currentAllowed: false }),
  Object.freeze({ code: 'approved', label: '已批准', currentAllowed: false }),
  Object.freeze({ code: 'rejected', label: '已驳回', currentAllowed: false }),
  Object.freeze({ code: 'cancelled', label: '已取消', currentAllowed: false }),
])

export const FORMAL_PRICE_APPROVAL_OBJECT_LIFECYCLE = Object.freeze(FORMAL_PRICE_APPROVAL_OBJECT_STATE_DEFINITIONS.map((item) => item.code))
export const FORMAL_PRICE_APPROVAL_OBJECT_CURRENT_ALLOWED_STATES = Object.freeze(
  FORMAL_PRICE_APPROVAL_OBJECT_STATE_DEFINITIONS.filter((item) => item.currentAllowed).map((item) => item.code),
)

export const FORMAL_PRICE_APPROVAL_OBJECT_FUTURE_TRANSITIONS = Object.freeze([
  Object.freeze({ from: 'definition_only', to: 'ready_for_creation', enabled: true }),
  Object.freeze({ from: 'ready_for_creation', to: 'created', enabled: false }),
  Object.freeze({ from: 'created', to: 'pending_approval', enabled: false }),
  Object.freeze({ from: 'pending_approval', to: 'approved', enabled: false }),
  Object.freeze({ from: 'pending_approval', to: 'rejected', enabled: false }),
  Object.freeze({ from: 'created', to: 'cancelled', enabled: false }),
])

export function evaluateFormalPriceApprovalObjectStateAccess(status = '') {
  const known = FORMAL_PRICE_APPROVAL_OBJECT_LIFECYCLE.includes(status)
  const allowed = FORMAL_PRICE_APPROVAL_OBJECT_CURRENT_ALLOWED_STATES.includes(status)
  return Object.freeze({ result: known && allowed ? 'PASS' : known ? 'FAIL' : 'UNKNOWN', decision: allowed ? 'allow' : 'deny' })
}
