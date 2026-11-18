function text(value) {
  return String(value ?? '').trim()
}

export function buildSupplierSettlementDetailRoute(record = {}, sourceQuery = {}) {
  return {
    path: '/scm/supplier-settlements',
    query: {
      ...sourceQuery,
      settlementNo: text(record.settlementNo),
    },
  }
}

export function buildPurchaseReconciliationRoute(record = {}) {
  return {
    path: '/scm/purchase-reconciliations',
    query: {
      sourceSettlementId: text(record.id),
      sourceSettlementNo: text(record.settlementNo),
      sourcePayableCheckNo: text(record.sourcePayableCheckNo || record.sourceObjectNo),
    },
  }
}
