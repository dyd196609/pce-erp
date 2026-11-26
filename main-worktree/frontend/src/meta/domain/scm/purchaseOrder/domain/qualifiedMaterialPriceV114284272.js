export const QUALIFIED_MATERIAL_PRICE_VERSION_V114284272 = 'V1.14.2.8.4.27.2'
export const QUALIFIED_MATERIAL_PRICE_CODE_V114284272 = 'SCM_QUALIFIED_MATERIAL_PRICE'

const freeze = value => Object.freeze(value)
const text = value => String(value ?? '').trim()
const number = value => Number.isFinite(Number(value)) ? Number(value) : 0
const clone = value => JSON.parse(JSON.stringify(value))

export const QUALIFIED_MATERIAL_PRICE_MODEL_V114284272 = freeze({
  objectCode: QUALIFIED_MATERIAL_PRICE_CODE_V114284272,
  objectName: '合格物料价格',
  businessObject: 'QualifiedMaterialPrice',
  fields: freeze([
    'materialId', 'materialCode', 'supplierId', 'qualifiedPrice', 'currency',
    'effectiveDate', 'sourcePurchaseOrderId', 'approvalStatus',
    'sourceSupplierId', 'sourceApprovalRecord',
  ]),
  historyMode: 'append_only',
  persistenceMode: 'projection_only',
  materialMasterAutoUpdate: false,
  overwritesHistoricalPrice: false,
  automaticPriceQualification: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

function blocked(reason, input = {}) {
  return freeze({
    result: 'FAIL',
    eligibilityStatus: 'not_qualified',
    reason,
    sourcePurchaseOrderId: text(input.sourcePurchaseOrderId),
    materialMasterAutoUpdate: false,
    qualifiedMaterialPriceCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function evaluateQualifiedMaterialPriceV114284272(input = {}) {
  if (!['approved', 'issued'].includes(text(input.purchaseOrderStatus))) {
    return blocked('PURCHASE_ORDER_STATUS_NOT_PRICE_QUALIFIED', input)
  }
  if (input.priceHumanConfirmed !== true || !text(input.priceConfirmedBy)
    || !text(input.priceConfirmedAt)) {
    return blocked('QUALIFIED_PRICE_HUMAN_CONFIRMATION_REQUIRED', input)
  }
  const approvalRecord = input.sourceApprovalRecord
  if (!text(input.sourcePurchaseOrderId) || !text(input.sourceSupplierId)
    || !text(approvalRecord?.recordId) || approvalRecord?.result !== 'approved') {
    return blocked('QUALIFIED_PRICE_SOURCE_TRACE_INCOMPLETE', input)
  }
  if (!text(input.materialId) || !text(input.materialCode) || !text(input.supplierId)
    || number(input.qualifiedPrice) <= 0 || !text(input.currency)
    || !text(input.effectiveDate)) {
    return blocked('QUALIFIED_PRICE_REQUIRED_FIELD_INCOMPLETE', input)
  }
  return freeze({
    result: 'PASS',
    eligibilityStatus: 'qualified',
    reason: '',
    qualifiedMaterialPrice: freeze({
      objectType: 'QualifiedMaterialPrice',
      qualifiedMaterialPriceId: text(input.qualifiedMaterialPriceId)
        || `QMP-${text(input.sourcePurchaseOrderId)}-${text(input.materialCode)}-${text(input.supplierId)}`,
      materialId: text(input.materialId),
      materialCode: text(input.materialCode),
      supplierId: text(input.supplierId),
      qualifiedPrice: number(input.qualifiedPrice),
      currency: text(input.currency),
      effectiveDate: text(input.effectiveDate),
      sourcePurchaseOrderId: text(input.sourcePurchaseOrderId),
      approvalStatus: 'qualified',
      sourceSupplierId: text(input.sourceSupplierId),
      sourceApprovalRecord: freeze(clone(approvalRecord)),
      priceConfirmedBy: text(input.priceConfirmedBy),
      priceConfirmedAt: text(input.priceConfirmedAt),
      historyMode: 'append_only',
    }),
    materialMasterAutoUpdate: false,
    qualifiedMaterialPriceCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}

export function proposeMaterialMasterPriceHistoryV114284272({
  existingHistory = [], qualifiedMaterialPrices = [],
} = {}) {
  const existing = clone(Array.isArray(existingHistory) ? existingHistory : [])
  const candidates = clone(Array.isArray(qualifiedMaterialPrices)
    ? qualifiedMaterialPrices : [])
  const keys = new Set(existing.map(item => text(item.qualifiedMaterialPriceId)
    || [item.sourcePurchaseOrderId, item.materialCode, item.supplierId,
      item.effectiveDate].map(text).join('|')))
  const appendCandidates = candidates.filter(item => {
    const key = text(item.qualifiedMaterialPriceId)
      || [item.sourcePurchaseOrderId, item.materialCode, item.supplierId,
        item.effectiveDate].map(text).join('|')
    if (!key || keys.has(key)) return false
    keys.add(key)
    return true
  })
  return freeze({
    result: 'PASS',
    existingHistory: freeze(existing.map(item => freeze(item))),
    appendCandidates: freeze(appendCandidates.map(item => freeze(item))),
    projectedHistory: freeze([...existing, ...appendCandidates].map(item => freeze(item))),
    historicalPriceOverwritten: false,
    materialMasterAutoUpdate: false,
    persistenceExecuted: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
