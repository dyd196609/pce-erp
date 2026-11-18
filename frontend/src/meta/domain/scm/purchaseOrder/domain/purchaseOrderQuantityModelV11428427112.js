export const PURCHASE_ORDER_QUANTITY_MODEL_VERSION_V11428427112 =
  'V1.14.2.8.4.27.1.2'

const number = value => Number.isFinite(Number(value)) ? Number(value) : 0
const text = value => String(value ?? '').trim()
const freeze = value => Object.freeze(value)

export const PURCHASE_ORDER_QUANTITY_FORMULA_V11428427112 =
  '建议采购数量 = 需求数量 - 可用库存 - 已采购未入库数量'
export const PURCHASE_ORDER_ITEM_DRAFT_STATUSES_V114284271131 = Object.freeze([
  'included', 'excluded',
])

export function calculatePurchaseOrderQuantityV11428427112(item = {}) {
  const demandQuantity = number(item.requestedQuantity)
  const inventoryKnown = item.availableQuantity !== null
    && item.availableQuantity !== undefined && item.availableQuantity !== ''
  const availableInventory = inventoryKnown ? number(item.availableQuantity) : null
  const inTransitKnown = item.orderedQuantity !== null
    && item.orderedQuantity !== undefined && item.orderedQuantity !== ''
  const purchasedNotReceivedQuantity = inTransitKnown ? number(item.orderedQuantity) : null
  const knownInventory = availableInventory ?? 0
  const knownInTransit = purchasedNotReceivedQuantity ?? 0
  const netDemandQuantity = Math.max(demandQuantity - knownInventory - knownInTransit, 0)
  const suggestedPurchaseQuantity = netDemandQuantity
  const confirmedPurchaseQuantity = number(item.confirmedQuantity ?? item.quantity)
  const itemDraftStatus = confirmedPurchaseQuantity > 0 ? 'included' : 'excluded'
  const itemDraftStatusLabel = itemDraftStatus === 'included'
    ? '纳入采购订单' : '不纳入采购订单'
  const quantityConsistencyStatus = demandQuantity <= 0 && confirmedPurchaseQuantity > 0
    ? 'invalid_demand'
    : (demandQuantity > 0 && confirmedPurchaseQuantity === 0
      ? 'pending_confirmation'
      : (itemDraftStatus === 'included' ? 'confirmed' : 'excluded'))
  const quantityConsistencyStatusLabel = ({ invalid_demand: '采购需求不存在',
    pending_confirmation: '待确认', confirmed: '已确认', excluded: '不纳入采购订单' }
    [quantityConsistencyStatus])
  const originalSuggestedQuantity = number(item.originalSuggestedQuantity
    ?? item.suggestedQuantity ?? suggestedPurchaseQuantity)
  const quantityChangedByHuman = confirmedPurchaseQuantity > 0
    && confirmedPurchaseQuantity !== originalSuggestedQuantity
  const quantityIncreasedByHuman = confirmedPurchaseQuantity > suggestedPurchaseQuantity
  const quantityReducedByHuman = confirmedPurchaseQuantity > 0
    && confirmedPurchaseQuantity < suggestedPurchaseQuantity
  const adjustmentReason = text(item.quantityAdjustmentReason)
  const exceedsDemand = confirmedPurchaseQuantity > demandQuantity
  const severeQuantityAnomaly = itemDraftStatus === 'included'
    && (suggestedPurchaseQuantity <= 0
      ? confirmedPurchaseQuantity > 0
      : confirmedPurchaseQuantity > suggestedPurchaseQuantity * 10)
  const adjustmentEvidenceComplete = !quantityIncreasedByHuman || Boolean(adjustmentReason)
  const blockingReasons = []
  if (itemDraftStatus === 'included' && demandQuantity <= 0) {
    blockingReasons.push('需求数量为0但确认采购数量大于0，无法形成有效采购依据。')
  }
  if (itemDraftStatus === 'included' && quantityIncreasedByHuman && !adjustmentReason) {
    blockingReasons.push('确认采购数量超过建议采购数量，必须填写调整原因。')
  }
  if (severeQuantityAnomaly) {
    blockingReasons.push('确认采购数量超过建议采购数量10倍，属于严重异常数量，请重新确认。')
  }
  return freeze({
    objectType: 'PurchaseOrderQuantityCalculation',
    formula: PURCHASE_ORDER_QUANTITY_FORMULA_V11428427112,
    demandQuantity,
    availableInventory,
    availableInventoryStatus: inventoryKnown ? 'KNOWN' : 'NOT_CONNECTED',
    purchasedNotReceivedQuantity,
    purchasedNotReceivedStatus: inTransitKnown ? 'KNOWN' : 'UNKNOWN',
    netDemandQuantity,
    suggestedPurchaseQuantity,
    confirmedPurchaseQuantity,
    itemDraftStatus,
    itemDraftStatusLabel,
    quantityConsistencyStatus,
    quantityConsistencyStatusLabel,
    originalSuggestedQuantity,
    quantityChangedByHuman,
    quantityIncreasedByHuman,
    quantityReducedByHuman,
    adjustmentReason,
    adjustmentEvidenceComplete,
    exceedsDemand,
    severeQuantityAnomaly,
    calculationStatus: inventoryKnown && inTransitKnown ? 'COMPLETE' : 'PARTIAL',
    result: blockingReasons.length ? 'BLOCKED' : 'PASS',
    blockingReasons: freeze(blockingReasons),
    automaticQuantityAdjustment: false,
  })
}
