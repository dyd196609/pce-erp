export const SUPPLIER_SETTLEMENT_CONTEXT_RESOLVER_VERSION = 'V1.14.2.8.4.7'

function text(value) {
  return String(value ?? '').trim()
}

function sourcePayableCheckNo(record = {}) {
  return text(record.payableCheckNo || record.sourcePayableCheckNo || record.sourceObjectNo)
}

function sourcePurchaseOrderNo(record = {}) {
  return text(record.sourcePurchaseOrderNo || record.purchaseOrderNo)
}

function normalizeQuery(query = {}) {
  return {
    sourcePayableCheckNo: text(query.sourcePayableCheckNo),
    sourcePayablePrepareNo: text(query.sourcePayablePrepareNo),
    purchaseOrderNo: text(query.purchaseOrderNo),
    supplierId: text(query.supplierId),
    supplierName: text(query.supplierName),
    sourceStatus: text(query.sourceStatus),
  }
}

function mismatch(field, expected, actual) {
  return { field, expected: text(expected), actual: text(actual) }
}

function compareProvided(mismatches, field, expected, actual) {
  if (text(expected) && text(expected) !== text(actual)) mismatches.push(mismatch(field, expected, actual))
}

function requiredSourceRelationMismatches(source = {}) {
  const requirements = [
    ['sourcePayablePrepareNo', source.sourcePayablePrepareNo],
    ['sourceInventoryTransactionNos', source.sourceInventoryTransactionNos?.length ? source.sourceInventoryTransactionNos.join(',') : ''],
    ['sourceWarehouseTaskNo', source.sourceWarehouseTaskNo],
    ['sourceInspectionNo', source.sourceInspectionNo],
    ['sourceReceiveNo', source.sourceReceiveNo],
    ['sourcePurchaseOrderNo', sourcePurchaseOrderNo(source)],
    ['sourcePriceApprovalNo', source.sourcePriceApprovalNo],
  ]
  return requirements.filter(([, value]) => !text(value)).map(([field]) => mismatch(field, '必须存在', '来源关系缺失'))
}

function buildPendingRow(source = {}) {
  const line = source.lines?.[0] || {}
  return {
    id: `pending-source-${sourcePayableCheckNo(source)}`,
    isPendingSource: true,
    settlementNo: '',
    sourcePayableCheckNo: sourcePayableCheckNo(source),
    sourcePayablePrepareNo: text(source.sourcePayablePrepareNo),
    purchaseOrderNo: sourcePurchaseOrderNo(source),
    supplierId: text(source.supplierId),
    supplierName: text(source.supplierName),
    sourceStatus: text(source.checkStatus || source.status),
    sourcePayableCheckId: text(source.id),
    sourcePayablePrepareId: text(source.sourcePayablePrepareId),
    sourceInventoryTransactionNos: [...(source.sourceInventoryTransactionNos || [])],
    sourceWarehouseTaskNo: text(source.sourceWarehouseTaskNo),
    sourceInspectionNo: text(source.sourceInspectionNo),
    sourceReceiveNo: text(source.sourceReceiveNo),
    sourcePriceApprovalNo: text(source.sourcePriceApprovalNo),
    materialCode: text(line.materialCode),
    materialName: text(line.materialName),
    settlementQuantity: Number(source.totalCheckedQty || 0),
    unit: text(line.unit),
    unitPrice: Number(line.checkedPrice || line.payablePrice || 0),
    payableAmount: Number(source.totalPayableAmount || 0),
    checkedAmount: Number(source.totalCheckedAmount || 0),
    settlementAmount: Number(source.totalCheckedAmount || 0),
    differenceAmount: Number(source.amountDifference || 0),
    reconciliationStatus: 'pending_source',
    settlementStatus: 'pending_source',
    nextStepReadiness: 'not_ready',
  }
}

export function resolveSupplierSettlementContext({
  query = {},
  payableChecks = [],
  supplierSettlements = [],
} = {}) {
  const normalizedQuery = normalizeQuery(query)
  const contextualMode = Object.values(normalizedQuery).some(Boolean)
  if (!contextualMode) {
    return {
      status: 'all_settlements',
      contextualMode: false,
      query: normalizedQuery,
      sourceRecord: null,
      settlementRecords: [...supplierSettlements],
      displayRows: [...supplierSettlements],
      mismatchFields: [],
    }
  }

  if (!normalizedQuery.sourcePayableCheckNo) {
    return {
      status: 'invalid_source',
      contextualMode: true,
      query: normalizedQuery,
      sourceRecord: null,
      settlementRecords: [],
      displayRows: [],
      mismatchFields: [mismatch('sourcePayableCheckNo', '必须提供', '')],
    }
  }

  const sourceRecord = payableChecks.find((record) => sourcePayableCheckNo(record) === normalizedQuery.sourcePayableCheckNo) || null
  if (!sourceRecord) {
    return {
      status: 'invalid_source',
      contextualMode: true,
      query: normalizedQuery,
      sourceRecord: null,
      settlementRecords: [],
      displayRows: [],
      mismatchFields: [mismatch('sourcePayableCheckNo', normalizedQuery.sourcePayableCheckNo, '未找到来源记录')],
    }
  }

  const sourceMismatches = []
  compareProvided(sourceMismatches, 'sourcePayablePrepareNo', normalizedQuery.sourcePayablePrepareNo, sourceRecord.sourcePayablePrepareNo)
  compareProvided(sourceMismatches, 'purchaseOrderNo', normalizedQuery.purchaseOrderNo, sourcePurchaseOrderNo(sourceRecord))
  compareProvided(sourceMismatches, 'supplierId', normalizedQuery.supplierId, sourceRecord.supplierId)
  compareProvided(sourceMismatches, 'supplierName', normalizedQuery.supplierName, sourceRecord.supplierName)
  compareProvided(sourceMismatches, 'sourceStatus', normalizedQuery.sourceStatus, sourceRecord.checkStatus || sourceRecord.status)
  if (sourceMismatches.length) {
    return {
      status: 'invalid_source',
      contextualMode: true,
      query: normalizedQuery,
      sourceRecord,
      settlementRecords: [],
      displayRows: [],
      mismatchFields: sourceMismatches,
    }
  }

  const relationMismatches = requiredSourceRelationMismatches(sourceRecord)
  if (relationMismatches.length) {
    return {
      status: 'incomplete_source',
      contextualMode: true,
      query: normalizedQuery,
      sourceRecord,
      settlementRecords: [],
      displayRows: [],
      mismatchFields: relationMismatches,
    }
  }

  const candidates = supplierSettlements.filter((record) => sourcePayableCheckNo(record) === normalizedQuery.sourcePayableCheckNo)
  const matchingSettlements = candidates.filter((record) => {
    if (text(record.purchaseOrderNo) && sourcePurchaseOrderNo(sourceRecord) && text(record.purchaseOrderNo) !== sourcePurchaseOrderNo(sourceRecord)) return false
    if (text(record.supplierId) && text(sourceRecord.supplierId) && text(record.supplierId) !== text(sourceRecord.supplierId)) return false
    if (text(record.supplierName) && text(sourceRecord.supplierName) && text(record.supplierName) !== text(sourceRecord.supplierName)) return false
    return true
  })

  if (matchingSettlements.length) {
    return {
      status: 'existing_settlement',
      contextualMode: true,
      query: normalizedQuery,
      sourceRecord,
      settlementRecords: matchingSettlements,
      displayRows: matchingSettlements,
      mismatchFields: [],
    }
  }

  if (candidates.length) {
    const candidate = candidates[0]
    const targetMismatches = []
    compareProvided(targetMismatches, 'settlement.purchaseOrderNo', sourcePurchaseOrderNo(sourceRecord), candidate.purchaseOrderNo)
    compareProvided(targetMismatches, 'settlement.supplierId', sourceRecord.supplierId, candidate.supplierId)
    compareProvided(targetMismatches, 'settlement.supplierName', sourceRecord.supplierName, candidate.supplierName)
    return {
      status: 'invalid_source',
      contextualMode: true,
      query: normalizedQuery,
      sourceRecord,
      settlementRecords: [],
      displayRows: [],
      mismatchFields: targetMismatches.length ? targetMismatches : [mismatch('supplierSettlement', '来源字段一致', '目标字段冲突')],
    }
  }

  return {
    status: 'pending_source',
    contextualMode: true,
    query: normalizedQuery,
    sourceRecord,
    settlementRecords: [],
    displayRows: [buildPendingRow(sourceRecord)],
    mismatchFields: [],
  }
}
