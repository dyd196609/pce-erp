import { calculatePurchaseOrderQuantityV11428427112 } from
  './purchaseOrderQuantityModelV11428427112.js'
import { evaluateSupplierPurchaseDraftsV11428427114 } from
  './supplierPurchaseDraftModelV11428427114.js'
import { evaluatePurchaseOrderMaterialEligibilityV114284271144 } from
  '../guard/purchaseOrderMaterialEligibilityGuardV114284271144.js'

export const PURCHASE_ORDER_CREATION_FINAL_CHECK_VERSION_V114284271146 =
  'V1.14.2.8.4.27.1.4.6'
export const PURCHASE_ORDER_CREATION_FINAL_CHECK_CODE_V114284271146 =
  'PurchaseOrderCreationFinalCheck'
export const PURCHASE_ORDER_QUANTITY_STATUSES_V114284271146 = Object.freeze([
  'normal', 'need_reason', 'abnormal', 'pending_inventory_check',
])
export const CONFIRM_PURCHASE_ORDER_INVENTORY_ACTION_V114284271146 =
  'CONFIRM_PURCHASE_ORDER_INVENTORY'

const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const frozen = value => freeze(clone(value))

export function resolvePurchaseOrderQuantityStatusV114284271146(item = {}) {
  const calculation = calculatePurchaseOrderQuantityV11428427112(item)
  const inventoryConfirmation = item.inventoryConfirmation || {}
  const inventoryConfirmationRequired = calculation.availableInventoryStatus === 'NOT_CONNECTED'
  const inventoryConfirmed = !inventoryConfirmationRequired
    || (inventoryConfirmation.confirmed === true
      && Boolean(text(inventoryConfirmation.confirmedBy))
      && Boolean(text(inventoryConfirmation.confirmedAt))
      && Boolean(text(inventoryConfirmation.confirmationRemark)))
  let statusCode = 'normal'
  let statusLabel = '正常'
  let result = 'PASS'
  let reason = '确认采购数量未超过建议采购数量。'
  let handled = true

  if (calculation.severeQuantityAnomaly) {
    statusCode = 'abnormal'
    statusLabel = '严重异常'
    result = 'FAIL'
    reason = '确认采购数量超过建议采购数量10倍，属于严重异常，需要重新确认。'
    handled = false
  } else if (calculation.quantityIncreasedByHuman) {
    statusCode = 'need_reason'
    statusLabel = calculation.adjustmentEvidenceComplete ? '需填写原因（已处理）' : '需填写原因'
    result = calculation.adjustmentEvidenceComplete ? 'PASS' : 'FAIL'
    reason = calculation.adjustmentEvidenceComplete
      ? '确认采购数量超过建议采购数量，调整原因已填写。'
      : '确认采购数量超过建议采购数量，必须填写调整原因。'
    handled = calculation.adjustmentEvidenceComplete
  } else if (inventoryConfirmationRequired && !inventoryConfirmed) {
    statusCode = 'pending_inventory_check'
    statusLabel = '库存待人工确认'
    result = 'FAIL'
    reason = '可用库存未接入，必须由采购人员人工核对并确认。'
    handled = false
  }

  return freeze({ objectType: 'PurchaseOrderQuantityStatus', statusCode, statusLabel,
    result, reason, handled, calculation, inventoryConfirmationRequired,
    inventoryConfirmed, automaticInventoryMutation: false })
}

function check(checkCode, checkName, currentValue, result, reason) {
  return freeze({ checkCode, checkName, currentValue, result, reason })
}

export function evaluatePurchaseOrderCreationFinalCheckV114284271146({
  gate = {}, creationContext = {}, draft = {}, entryGuard = {},
} = {}) {
  const materialItems = Array.isArray(draft.materialItems) ? draft.materialItems : []
  const materialCheck = evaluatePurchaseOrderMaterialEligibilityV114284271144(materialItems)
  const eligibleDraft = { ...draft, materialItems: materialCheck.eligibleItems }
  const supplierCheck = evaluateSupplierPurchaseDraftsV11428427114(eligibleDraft)
  const quantityStatuses = materialItems.map(resolvePurchaseOrderQuantityStatusV114284271146)
  const includedIndexes = materialItems.map((item, index) => ({ item, index }))
    .filter(({ item, index }) => Number(item.confirmedQuantity ?? item.quantity) > 0
      && materialCheck.checks[index]?.result === 'PASS')
  const includedQuantityStatuses = includedIndexes.map(({ index }) => quantityStatuses[index])
  const inventoryRequiredItems = includedIndexes.filter(({ index }) =>
    quantityStatuses[index].inventoryConfirmationRequired)
  const inventoryConfirmedItems = inventoryRequiredItems.filter(({ index }) =>
    quantityStatuses[index].inventoryConfirmed)
  const humanConfirmations = inventoryConfirmedItems.map(({ item }) => ({
    materialCode: text(item.materialCode),
    confirmedBy: text(item.inventoryConfirmation?.confirmedBy),
    confirmedAt: text(item.inventoryConfirmation?.confirmedAt),
    confirmationRemark: text(item.inventoryConfirmation?.confirmationRemark),
  }))
  const quantityFailures = includedQuantityStatuses.filter(status =>
    status.statusCode === 'abnormal'
      || (status.statusCode === 'need_reason' && status.result !== 'PASS'))
  const gatePass = entryGuard.result === 'PASS'
  const sourcePass = Array.isArray(creationContext.purchaseRequestIds)
    && creationContext.purchaseRequestIds.length > 0
  const materialPass = materialCheck.validMaterialCount > 0
  const supplierPass = supplierCheck.result === 'PASS' && supplierCheck.supplierCount > 0
  const quantityPass = includedQuantityStatuses.length > 0 && quantityFailures.length === 0
  const inventoryPass = inventoryRequiredItems.length === inventoryConfirmedItems.length
  const checks = [
    check('GATE_STATUS', 'Gate状态', text(gate.statusLabel || gate.status || 'UNKNOWN'),
      gatePass ? 'PASS' : 'FAIL', gatePass ? 'Gate与创建入口准入有效。' : 'Gate失效或创建入口准入未通过。'),
    check('PURCHASE_REQUEST_SOURCE', '采购申请来源',
      sourcePass ? creationContext.purchaseRequestIds.join('、') : 'UNKNOWN',
      sourcePass ? 'PASS' : 'FAIL', sourcePass ? '采购申请来源完整。' : '缺少采购申请来源。'),
    check('SUPPLIER_ASSIGNMENT', '供应商分配', `${supplierCheck.supplierCount} 个供应商草稿`,
      supplierPass ? 'PASS' : 'FAIL', supplierPass ? '供应商分配完整。'
        : supplierCheck.missingFields.join('；') || '物料无供应商。'),
    check('MATERIAL_ELIGIBILITY', '物料有效性',
      `${materialCheck.validMaterialCount} 项有效 / ${materialCheck.invalidMaterialCount} 项异常`,
      materialPass ? 'PASS' : 'FAIL', materialPass ? '采购物料准入通过。'
        : materialCheck.checks.filter(value => value.result === 'FAIL').map(value => value.reason).join('；')
          || '没有有效采购物料。'),
    check('QUANTITY_STATUS', '数量状态',
      quantityFailures.length ? `${quantityFailures.length} 项未处理异常` : `${includedQuantityStatuses.length} 项已检查`,
      quantityPass ? 'PASS' : 'FAIL', quantityPass ? '数量异常均已处理。'
        : quantityFailures.map(value => value.reason).join('；') || '没有有效确认采购数量。'),
    check('INVENTORY_CONFIRMATION', '库存确认',
      `${inventoryConfirmedItems.length}/${inventoryRequiredItems.length} 项已人工确认`,
      inventoryPass ? 'PASS' : 'FAIL', inventoryPass ? '库存确认要求已满足。'
        : '库存未接入物料尚未完成人工确认。'),
  ]
  const result = checks.every(value => value.result === 'PASS') ? 'PASS' : 'FAIL'
  return freeze({
    objectType: PURCHASE_ORDER_CREATION_FINAL_CHECK_CODE_V114284271146,
    version: PURCHASE_ORDER_CREATION_FINAL_CHECK_VERSION_V114284271146,
    checkId: `POFC-${text(draft.draftId || gate.gateId) || 'UNKNOWN'}`,
    gateId: text(gate.gateId || draft.gateId),
    creationContextId: text(creationContext.creationContextId),
    quantityCheck: frozen({ result: quantityPass ? 'PASS' : 'FAIL', statuses: quantityStatuses }),
    materialCheck: frozen(materialCheck), supplierCheck: frozen(supplierCheck),
    inventoryCheck: frozen({ result: inventoryPass ? 'PASS' : 'FAIL',
      requiredCount: inventoryRequiredItems.length,
      confirmedCount: inventoryConfirmedItems.length }),
    humanConfirmations: frozen(humanConfirmations), checks: frozen(checks), result,
    createAllowed: result === 'PASS', automaticPurchaseOrderCreation: false,
    businessWriteCount: 0, productionDataWritten: false,
  })
}
