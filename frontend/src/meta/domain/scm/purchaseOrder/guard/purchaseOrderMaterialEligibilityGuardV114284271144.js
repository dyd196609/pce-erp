export const PURCHASE_ORDER_MATERIAL_ELIGIBILITY_GUARD_VERSION_V114284271144 =
  'V1.14.2.8.4.27.1.4.4'

const text = value => String(value ?? '').trim()
const number = value => Number.isFinite(Number(value)) ? Number(value) : 0
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const frozen = value => freeze(clone(value))

export function evaluatePurchaseOrderMaterialItemEligibilityV114284271144(item = {}, index = 0) {
  const requestedQuantity = number(item.requestedQuantity)
  const confirmedQuantity = number(item.confirmedQuantity ?? item.quantity)
  const supplierId = text(item.supplierId)
  let result = 'NOT_SELECTED'
  let reasonCode = 'RECOMMENDATION_EVIDENCE_ONLY'
  let reason = '推荐物料尚未形成有效采购确认。'
  if (requestedQuantity === 0 && confirmedQuantity > 0) {
    result = 'FAIL'
    reasonCode = 'PURCHASE_DEMAND_NOT_EXISTS'
    reason = '无采购需求，不能形成采购订单物料。'
  } else if (confirmedQuantity > 0 && !supplierId) {
    result = 'FAIL'
    reasonCode = 'PURCHASE_ORDER_ITEM_SUPPLIER_REQUIRED'
    reason = '确认采购数量大于0，但没有供应商分配。'
  } else if (requestedQuantity > 0 && confirmedQuantity > 0 && supplierId) {
    result = 'PASS'
    reasonCode = 'PURCHASE_MATERIAL_ELIGIBLE'
    reason = '采购需求、确认数量和供应商分配完整。'
  }
  return freeze({
    objectType: 'PurchaseOrderMaterialEligibilityCheck',
    lineNo: number(item.lineNo) || index + 1,
    materialCode: text(item.materialCode),
    requestedQuantity,
    confirmedQuantity,
    supplierId,
    result,
    eligible: result === 'PASS',
    reasonCode,
    reason,
  })
}

export function evaluatePurchaseOrderMaterialEligibilityV114284271144(items = []) {
  const sourceItems = Array.isArray(items) ? items : []
  const checks = sourceItems.map(evaluatePurchaseOrderMaterialItemEligibilityV114284271144)
  const eligibleItems = sourceItems.filter((_item, index) => checks[index].result === 'PASS')
  const invalidItems = sourceItems.filter((_item, index) => checks[index].result === 'FAIL')
  const recommendationEvidenceItems = sourceItems.filter((_item, index) =>
    checks[index].result !== 'PASS')
  return freeze({
    objectType: 'PurchaseOrderMaterialEligibilityGuard',
    result: invalidItems.length ? 'FAIL' : 'PASS',
    totalRecommendationItemCount: sourceItems.length,
    validMaterialCount: eligibleItems.length,
    invalidMaterialCount: invalidItems.length,
    evidenceOnlyCount: recommendationEvidenceItems.length,
    checks: frozen(checks),
    eligibleItems: frozen(eligibleItems),
    invalidItems: frozen(invalidItems),
    recommendationEvidenceItems: frozen(recommendationEvidenceItems),
    automaticPurchaseOrderItemCreation: false,
    businessWriteCount: 0,
  })
}

export function assertPurchaseOrderMaterialEligibilityV114284271144(items = []) {
  const evaluation = evaluatePurchaseOrderMaterialEligibilityV114284271144(items)
  if (!evaluation.validMaterialCount) return freeze({ success: false,
    error: 'PURCHASE_ORDER_VALID_MATERIAL_REQUIRED', evaluation })
  return freeze({ success: true, evaluation })
}
