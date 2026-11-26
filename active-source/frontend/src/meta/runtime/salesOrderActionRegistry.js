export const SALES_ORDER_ACTION_REGISTRY_VERSION = 'ORDER-OPERATING-SYSTEM-V1'

const definitions = Object.freeze([
  ['submit', '提交审核', 'primary', 'sales.order.submit', ['draft']],
  ['approve', '批准', 'success', 'sales.order.approve', ['submitted']],
  ['start-engineering', '进入工程', 'primary', 'sales.order.engineering.start', ['approved', 'confirmed']],
  ['complete-engineering', '工程准备完成', 'success', 'sales.order.engineering.complete', ['engineering']],
  ['start-execution', '开始执行', 'primary', 'sales.order.execution.start', ['manufacturing_ready']],
  ['start-delivery', '开始交付', 'primary', 'sales.order.delivery.start', ['in_progress']],
  ['complete', '完成', 'success', 'sales.order.complete', ['in_progress', 'delivering']],
  ['close', '关闭', 'primary', 'sales.order.close', ['completed']],
  ['cancel', '取消', 'danger', 'sales.order.cancel', ['draft', 'submitted', 'approved', 'confirmed', 'engineering', 'manufacturing_ready']],
].map(([code, label, type, permission, states]) => Object.freeze({
  code, label, type, permission, states: Object.freeze(states),
})))

export function resolveSalesOrderActions(status, capabilities = {}) {
  return definitions.filter(action => (
    action.states.includes(status) && capabilities[action.permission] === true
  ))
}
