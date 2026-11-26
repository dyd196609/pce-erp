export const SUPPLIER_MATERIAL_PRICE_RUNTIME_VERSION = 'V1.14.2.8.4.27.2.46-Batch2.1'

export const SUPPLIER_MATERIAL_PRICE_RUNTIME_DIAGNOSTICS = Object.freeze({
  dataSource: 'SupplierMaterialPriceRuntime',
  schema: 'SupplierMaterialPriceSchema',
  provider: 'SupplierMaterialPriceRuntimeProvider',
  runtime: 'SupplierMaterialPriceRuntime',
  maintenanceMode: 'APPROVAL_WORKFLOW_MANAGED',
})

export const SUPPLIER_MATERIAL_PRICE_REFERENCE_CHAIN = Object.freeze([
  'SupplierPriceFactRuntime',
  'PurchasePriceReviewAssistant',
  'PurchaseOrderPriceSourceReference',
])

const REQUIRED_FIELDS = Object.freeze([
  'priceId', 'priceNo', 'supplierId', 'supplierCode', 'supplierName', 'supplierDisplay',
  'materialId', 'materialCode', 'materialName', 'materialDisplay', 'minOrderQty', 'minPurchaseQty',
  'specification', 'unit',
  'unitPrice', 'taxRate', 'taxRateSource', 'currency', 'deliveryPeriod', 'effectiveDate',
  'expiryDate', 'status', 'statusLabel', 'sourceType', 'sourceTypeLabel', 'sourceReference',
  'sourceId', 'approvalStatus', 'approvalStatusLabel', 'maintenanceMode', 'source',
  'confirmedBy', 'confirmedAt', 'createdAt', 'priceApprovalResultId', 'originalSourceType',
  'originalSourceTypeLabel', 'originalSourceReference', 'approvedBy', 'approvedAt', 'factOrigin', 'persisted',
  'overlappingPriceNos', 'overlapStatus', 'overlapClassification', 'effectiveIdentityStatus',
  'scopeKey', 'scopeStatus', 'scopeDimensions', 'versionNo', 'versionStatus',
  'versionStatusLabel', 'isCurrentApplicable', 'previousPriceNo', 'nextPriceNo',
  'taxModifiedBy', 'taxModifiedAt', 'oldTaxRate', 'taxModificationReason', 'modificationAuditCount',
])

function normalizeRow(row = {}) {
  for (const field of REQUIRED_FIELDS) {
    if (!Object.prototype.hasOwnProperty.call(row, field)) {
      throw new Error(`SupplierMaterialPrice Runtime field unavailable: ${field}`)
    }
  }
  if (row.source !== 'SupplierMaterialPriceRuntime'
    || row.maintenanceMode !== 'APPROVAL_WORKFLOW_MANAGED'
    || !(Number(row.unitPrice) > 0)
    || !row.sourceReference
    || !row.effectiveDate || row.persisted !== true) {
    throw new Error('SupplierMaterialPrice governed contract unavailable')
  }
  return Object.freeze({ ...row })
}

export function buildSupplierMaterialPriceRuntime(payload = {}) {
  if (payload?.factLoadFacts?.factLoadStatus !== 'success'
    || payload?.runtimeCode !== 'SupplierMaterialPriceRuntime'
    || payload?.runtimeModelType !== 'SupplierMaterialPriceRuntimeModel'
    || !Array.isArray(payload?.rows)) {
    throw new Error('SupplierMaterialPrice Runtime facts unavailable')
  }
  const rows = Object.freeze(payload.rows.map(normalizeRow))
  if (rows.length !== Number(payload.formalPriceCount)
    || payload.maintenanceMode !== 'APPROVAL_WORKFLOW_MANAGED'
    || payload.autoGenerationEnabled !== false
    || Number(payload.businessProgressWriteCount) !== 0) {
    throw new Error('SupplierMaterialPrice Runtime governance mismatch')
  }
  const referenceChain = Object.freeze([...(payload.referenceChain || [])])
  if (SUPPLIER_MATERIAL_PRICE_REFERENCE_CHAIN.some(item => !referenceChain.includes(item))) {
    throw new Error('SupplierMaterialPrice reference chain unavailable')
  }
  return Object.freeze({
    rows,
    formalPriceCount: Number(payload.formalPriceCount),
    migrationCandidateCount: Number(payload.migrationCandidateCount),
    rejectedCandidateCount: Number(payload.rejectedCandidateCount),
    migrationCandidates: Object.freeze((payload.migrationCandidates || []).map(item => Object.freeze({
      ...item,
      missingFields: Object.freeze([...(item.missingFields || [])]),
    }))),
    migrationStatus: payload.migrationStatus,
    sessionConfirmedPriceCount: Number(payload.sessionConfirmedPriceCount),
    persistedPriceCount: Number(payload.persistedPriceCount),
    priceApprovalResultCount: Number(payload.priceApprovalResultCount),
    archiveEligibleResultCount: Number(payload.archiveEligibleResultCount),
    priceApprovalResults: Object.freeze((payload.priceApprovalResults || []).map(item => Object.freeze({ ...item }))),
    lastBatchArchiveResult: Object.freeze({ ...(payload.lastBatchArchiveResult || {}) }),
    sessionPersistence: payload.sessionPersistence,
    confirmationResults: Object.freeze([...(payload.confirmationResults || [])]),
    enterpriseProcurementDefaultTaxRate: payload.enterpriseProcurementDefaultTaxRate,
    enterpriseProcurementDefaultTaxRateSource: payload.enterpriseProcurementDefaultTaxRateSource,
    standardTaxRateOptions: Object.freeze([...(payload.standardTaxRateOptions || [])]),
    taxMaintenanceAudit: Object.freeze((payload.taxMaintenanceAudit || []).map(item => Object.freeze({ ...item }))),
    effectiveDateReconciliation: Object.freeze((payload.effectiveDateReconciliation || []).map(item => Object.freeze({ ...item }))),
    maintenanceMode: payload.maintenanceMode,
    referenceChain,
    approvalChain: Object.freeze([...(payload.approvalChain || [])]),
    allowedSourceTypes: Object.freeze([...(payload.allowedSourceTypes || [])]),
    autoGenerationEnabled: false,
    diagnostics: SUPPLIER_MATERIAL_PRICE_RUNTIME_DIAGNOSTICS,
    // These rows live only in the historical browser fixture and remain isolated.
    isolatedLegacySource: 'manufacturing-foundation-state-v1',
    isolatedLegacyCount: 3,
    strictFacts: Object.freeze({ ...(payload.strictFacts || {}) }),
    acceptanceFacts: Object.freeze({ ...(payload.acceptanceFacts || {}) }),
    factLoadFacts: Object.freeze({ ...(payload.factLoadFacts || {}) }),
    runtimeCode: payload.runtimeCode,
    runtimeVersion: payload.pageVersion,
    businessProgressWriteCount: 0,
    overlappingEffectivePriceCount: Number(payload.overlappingEffectivePriceCount || 0),
  })
}
