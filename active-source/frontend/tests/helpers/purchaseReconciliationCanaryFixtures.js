import { buildPurchaseReconciliationSourceKey } from '../../src/meta/scm/purchaseReconciliationCandidate.js'

function digitsFor(batchId) {
  return String(batchId).replace(/\D/g, '').padEnd(14, '0').slice(0, 14)
}

function source(batchId, code, overrides = {}) {
  const digits = digitsFor(batchId)
  const suffix = String(code.charCodeAt(0)).slice(-2)
  const settlementNo = `SET${digits}${suffix}`
  return {
    id: `canary-settlement-${batchId}-${code}`, settlementNo,
    supplierId: `CANARY-SUPPLIER-${code}`, supplierName: `金丝雀供应商${code}`,
    legalEntityId: 'LE-CANARY-001', legalEntityName: '金丝雀法人', ledgerBookId: 'LEDGER-CANARY-001', ledgerBookName: '金丝雀账套',
    businessUnitId: 'BU-CANARY-001', businessUnitName: '金丝雀业务单元', currency: 'CNY', exchangeRate: 1,
    settlementQuantity: 1, unit: '米', settlementAmount: 66, settlementStatus: 'reconciling',
    sourcePayableCheckNo: `PC${digits}${suffix}`, sourcePayablePrepareNo: `PP${digits}${suffix}`,
    sourcePurchaseOrderNo: `PO${digits}${suffix}`, sourcePriceApprovalNo: `PA${digits}${suffix}`,
    sourceReceiveNo: `PRV${digits}${suffix}`, sourceInspectionNo: `IQC${digits}${suffix}`,
    sourceWarehouseTaskNo: `WT${digits}${suffix}`, sourceInventoryTransactionNos: [`TXN${digits}${suffix}`],
    ...overrides,
  }
}

function scenario(batchId, scenarioCode, sourceSettlement, overrides = {}) {
  return {
    origin: 'canary', canaryBatchId: batchId, scenarioCode, sourceType: 'supplier_settlement',
    sourceSupplierSettlementNo: sourceSettlement?.settlementNo || '', sourcePayableCheckNo: sourceSettlement?.sourcePayableCheckNo || '',
    contextState: sourceSettlement ? 'existing_settlement' : 'invalid_source', sourceSettlement,
    upstreamEvidence: sourceSettlement ? { supplierId: sourceSettlement.supplierId, currency: sourceSettlement.currency, amount: 66 } : {},
    targetEvidence: [], writeMetrics: { purchaseReconciliationWrites: 0, supplierSettlementStatusWrites: 0, paymentObjectWrites: 0, formalNumberAllocations: 0, localStorageWrites: 0, networkWriteRequests: 0 },
    expectedRuntimeExecutionAllowed: false, ...overrides,
  }
}

export function buildPurchaseReconciliationCanaryScenarios(batchId) {
  const aSource = source(batchId, 'A')
  const a = scenario(batchId, 'CANARY_A', aSource, { expectedEvidenceStatus: 'complete', expectedBusinessEligibility: 'eligible', expectedTargetExistenceStatus: 'not_found' })
  const key = buildPurchaseReconciliationSourceKey(a)
  const bSource = source(batchId, 'B')
  const bKey = buildPurchaseReconciliationSourceKey({ sourceSettlement: bSource })
  const cSource = source(batchId, 'C')
  const cKey = buildPurchaseReconciliationSourceKey({ sourceSettlement: cSource })
  const dSource = source(batchId, 'D')
  const eSource = source(batchId, 'E', { exchangeRate: 0 })
  const fSource = source(batchId, 'F', { settlementAmount: 67 })
  const gSource = source(batchId, 'G', { sourcePriceApprovalNo: '' })
  const iSource = { ...aSource, settlementNo: `  ${aSource.settlementNo.toLowerCase()}  ` }
  return [
    a,
    scenario(batchId, 'CANARY_B', bSource, { targetEvidence: [{ sourceKey: bKey, targetNo: `PRC${digitsFor(batchId)}21`, evidenceOnly: true }], expectedEvidenceStatus: 'complete', expectedBusinessEligibility: 'already_exists', expectedTargetExistenceStatus: 'single_target' }),
    scenario(batchId, 'CANARY_C', cSource, { targetEvidence: [{ sourceKey: cKey, targetNo: `PRC${digitsFor(batchId)}31`, evidenceOnly: true }, { sourceKey: cKey, targetNo: `PRC${digitsFor(batchId)}32`, evidenceOnly: true }], expectedEvidenceStatus: 'conflict', expectedBusinessEligibility: 'conflict', expectedTargetExistenceStatus: 'multiple_targets' }),
    scenario(batchId, 'CANARY_D', dSource, { upstreamEvidence: { supplierId: 'CANARY-SUPPLIER-OTHER', currency: 'CNY', amount: 66 }, expectedEvidenceStatus: 'conflict', expectedBusinessEligibility: 'blocked', expectedTargetExistenceStatus: 'not_found', expectedBlockingCode: 'PRC_SUPPLIER_CONSISTENT' }),
    scenario(batchId, 'CANARY_E', eSource, { expectedEvidenceStatus: 'complete', expectedBusinessEligibility: 'blocked', expectedTargetExistenceStatus: 'not_found', expectedBlockingCode: 'PRC_EXCHANGE_RATE_VALID' }),
    scenario(batchId, 'CANARY_F', fSource, { upstreamEvidence: { supplierId: fSource.supplierId, currency: 'CNY', amount: 66 }, expectedEvidenceStatus: 'conflict', expectedBusinessEligibility: 'blocked', expectedTargetExistenceStatus: 'not_found', expectedBlockingCode: 'PRC_AMOUNT_CONSISTENT' }),
    scenario(batchId, 'CANARY_G', gSource, { expectedEvidenceStatus: 'incomplete', expectedBusinessEligibility: 'blocked', expectedTargetExistenceStatus: 'not_found', expectedBlockingCode: 'PRC_PRICE_APPROVAL_RELATION_PRESENT' }),
    scenario(batchId, 'CANARY_H', null, { expectedEvidenceStatus: 'read_failed', expectedBusinessEligibility: 'invalid_source', expectedTargetExistenceStatus: 'not_found', expectedBlockingCode: 'PRC_SOURCE_EXISTS' }),
    scenario(batchId, 'CANARY_I', iSource, { normalizationPeerSourceKey: key, expectedEvidenceStatus: 'complete', expectedBusinessEligibility: 'eligible', expectedTargetExistenceStatus: 'not_found' }),
    scenario(batchId, 'CANARY_J', aSource, { expectedEvidenceStatus: 'complete', expectedBusinessEligibility: 'eligible', expectedTargetExistenceStatus: 'not_found', reentryOf: 'CANARY_A' }),
  ]
}
