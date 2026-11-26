export const SUPPLIER_PURCHASE_DRAFT_MODEL_VERSION_V11428427114 = 'V1.14.2.8.4.27.1.4'
export const SUPPLIER_PURCHASE_DRAFT_REAL_SPLIT_VERSION_V114284271143 =
  'V1.14.2.8.4.27.1.4.3'
export const SUPPLIER_PURCHASE_DRAFT_OBJECT_TYPE_V11428427114 = 'SupplierPurchaseDraft'

const text = value => String(value ?? '').trim()
const number = value => Number.isFinite(Number(value)) ? Number(value) : 0
const clone = value => JSON.parse(JSON.stringify(value))
const safeId = value => text(value).replace(/[^A-Za-z0-9_-]/g, '-')

function isIncluded(line = {}) {
  return line.itemDraftStatus === 'included'
    || number(line.confirmedQuantity ?? line.quantity) > 0
}

function isValidPurchaseItem(line = {}) {
  return isIncluded(line) && number(line.requestedQuantity) > 0
}

function isCompositeSupplierName(value) {
  return /[、，,；;]/.test(text(value))
}

export function buildSupplierPurchaseDraftsV11428427114({
  draft = {}, previousSupplierDrafts = draft.supplierPurchaseDrafts || draft.supplierDrafts || [],
} = {}) {
  const previousBySupplier = new Map((previousSupplierDrafts || []).map(group =>
    [text(group.supplierId), group]))
  const groups = new Map()
  for (const line of (draft.materialItems || []).filter(isValidPurchaseItem)) {
    const supplierId = text(line.supplierId)
    const supplierName = text(line.supplierName)
    const key = supplierId || `UNKNOWN-${text(line.materialCode)}`
    if (!groups.has(key)) {
      const previous = previousBySupplier.get(supplierId) || {}
      groups.set(key, {
        objectType: SUPPLIER_PURCHASE_DRAFT_OBJECT_TYPE_V11428427114,
        supplierPurchaseDraftId: previous.supplierPurchaseDraftId
          || `${text(draft.draftId) || 'PO-DRAFT'}-SUP-${safeId(key)}`,
        supplierId,
        supplierName: text(supplierName || previous.supplierName),
        deliveryDate: text(previous.deliveryDate || line.confirmedDeliveryDate
          || (!previousSupplierDrafts.length ? draft.plannedDeliveryDate : '')),
        supplierRemark: text(previous.supplierRemark
          || (!previousSupplierDrafts.length ? draft.remark : '')),
        approvalRemark: text(previous.approvalRemark
          || (!previousSupplierDrafts.length ? draft.approvalOpinion : '')),
        items: [],
      })
    }
    const group = groups.get(key)
    if (!group.supplierName && supplierName) group.supplierName = supplierName
    group.items.push({
      lineNo: number(line.lineNo),
      materialId: text(line.materialId),
      materialCode: text(line.materialCode),
      materialName: text(line.materialName),
      supplierId,
      supplierName,
      confirmedQuantity: number(line.confirmedQuantity ?? line.quantity),
      confirmedPrice: number(line.confirmedPrice ?? line.unitPrice),
    })
  }
  return clone([...groups.values()].sort((left, right) =>
    left.supplierId.localeCompare(right.supplierId, 'zh-CN')))
}

export function synchronizeSupplierPurchaseDraftsV11428427114(draft = {}) {
  const supplierPurchaseDrafts = buildSupplierPurchaseDraftsV11428427114({ draft })
  const groupBySupplier = new Map(supplierPurchaseDrafts.map(group => [group.supplierId, group]))
  const materialItems = (draft.materialItems || []).map(line => {
    if (!isValidPurchaseItem(line)) return clone(line)
    const group = groupBySupplier.get(text(line.supplierId))
    return clone({ ...line,
      confirmedDeliveryDate: text(group?.deliveryDate || line.confirmedDeliveryDate),
    })
  })
  return clone({ ...draft, supplierPurchaseDrafts, supplierDrafts: supplierPurchaseDrafts,
    materialItems, supplierCount: supplierPurchaseDrafts.length,
    includedMaterialCount: supplierPurchaseDrafts.reduce((sum, group) =>
      sum + group.items.length, 0) })
}

export function evaluateSupplierPurchaseDraftsV11428427114(draft = {}) {
  const supplierPurchaseDrafts = buildSupplierPurchaseDraftsV11428427114({ draft })
  const missingFields = []
  const materialSuppliers = new Map()
  for (const group of supplierPurchaseDrafts) {
    if (!group.supplierId || !group.supplierName) missingFields.push('供应商身份未完成')
    if (isCompositeSupplierName(group.supplierName)) {
      missingFields.push(`${group.supplierId || '未知供应商'}名称包含多个供应商，必须逐供应商拆分`)
    }
    if (!group.deliveryDate) missingFields.push(`${group.supplierName || group.supplierId || '供应商'}交货日期未完成`)
    if (!group.approvalRemark) missingFields.push(`${group.supplierName || group.supplierId || '供应商'}审批意见未完成`)
    for (const item of group.items) {
      if (!item.supplierId || item.supplierId !== group.supplierId) {
        missingFields.push(`物料${item.materialCode}供应商归属不一致`)
      }
      if (!item.supplierName || item.supplierName !== group.supplierName) {
        missingFields.push(`物料${item.materialCode}供应商名称与供应商草稿不一致`)
      }
      const prior = materialSuppliers.get(item.materialCode)
      if (prior && prior !== group.supplierId) {
        missingFields.push(`物料${item.materialCode}同时分配给多个供应商`)
      }
      materialSuppliers.set(item.materialCode, group.supplierId)
    }
  }
  return Object.freeze({
    objectType: 'SupplierPurchaseDraftEvaluation',
    supplierCount: supplierPurchaseDrafts.length,
    itemCount: supplierPurchaseDrafts.reduce((sum, group) => sum + group.items.length, 0),
    supplierPurchaseDrafts: Object.freeze(clone(supplierPurchaseDrafts)),
    missingFields: Object.freeze([...new Set(missingFields)]),
    result: missingFields.length ? 'BLOCKED' : 'PASS',
  })
}
