export const SCM_INBOUND_QUANTITY_RULE_VERSION = 'V1.14.2.8.4.12'

export function evaluateScmInboundQuantity(input = {}) {
  const warehousePlanQuantity = Number(input.warehousePlanQuantity || 0)
  const completedQuantity = Number(input.completedQuantity || 0)
  const qualifiedQuantity = Number(input.qualifiedQuantity || 0)
  const remainingPlanQuantity = warehousePlanQuantity - completedQuantity
  const remainingQualifiedQuantity = qualifiedQuantity - completedQuantity
  const reasons = []
  if (warehousePlanQuantity <= 0) reasons.push('warehousePlanQuantity必须大于0。')
  if (completedQuantity < 0) reasons.push('completedQuantity不能小于0。')
  if (completedQuantity > warehousePlanQuantity) reasons.push('completedQuantity不能大于warehousePlanQuantity。')
  if (completedQuantity > qualifiedQuantity) reasons.push('completedQuantity不能大于qualifiedQuantity。')
  if (remainingPlanQuantity <= 0) reasons.push('当前任务没有剩余可入库数量。')
  if (remainingPlanQuantity > remainingQualifiedQuantity) reasons.push('剩余计划入库数量不能大于剩余检验合格数量。')
  return Object.freeze({
    allowed: reasons.length === 0,
    result: reasons.length ? 'FAIL' : 'PASS',
    warehousePlanQuantity,
    completedQuantity,
    qualifiedQuantity,
    remainingPlanQuantity,
    remainingQualifiedQuantity,
    reasons: Object.freeze(reasons),
  })
}

