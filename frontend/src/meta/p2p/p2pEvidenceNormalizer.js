function splitEvidenceNos(value) {
  if (Array.isArray(value)) return value.flatMap((item) => splitEvidenceNos(item))
  if (value === null || value === undefined) return []
  return String(value)
    .split(/[、,\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => item !== '-')
}

export function normalizeEvidenceItem(sourceType, sourceNo, fallbackText = '') {
  const nos = splitEvidenceNos(sourceNo)
  if (!nos.length && !fallbackText) return null
  const uniqueNos = Array.from(new Set(nos))
  return {
    sourceType,
    sourceNo: uniqueNos.join('、') || '',
    uniqueSourceNo: uniqueNos,
    evidenceText: fallbackText || uniqueNos.join('、') || '',
  }
}

export function normalizeEvidenceList(items = []) {
  const evidenceMap = new Map()
  items
    .filter(Boolean)
    .forEach((item) => {
      const normalized = normalizeEvidenceItem(item.sourceType, item.sourceNo, item.evidenceText)
      if (!normalized) return
      const key = [normalized.sourceType, normalized.sourceNo || normalized.evidenceText].join('::')
      if (!evidenceMap.has(key)) evidenceMap.set(key, normalized)
    })
  return Array.from(evidenceMap.values())
}

export function normalizeTraceTarget(traceTarget = {}) {
  const normalized = {
    purchaseOrder: splitEvidenceNos(traceTarget.purchaseOrder).join('、'),
    receipt: splitEvidenceNos(traceTarget.receipt).join('、'),
    inspection: splitEvidenceNos(traceTarget.inspection).join('、'),
    warehouseEntry: splitEvidenceNos(traceTarget.warehouseEntry).join('、'),
    inventoryTransaction: splitEvidenceNos(traceTarget.inventoryTransaction).join('、'),
    payable: splitEvidenceNos(traceTarget.payable).join('、'),
    paymentVoucher: splitEvidenceNos(traceTarget.paymentVoucher).join('、'),
    breakPoint: traceTarget.breakPoint || '',
    riskType: traceTarget.riskType || '',
    riskDescription: traceTarget.riskDescription || '',
  }

  if (!normalized.warehouseEntry && normalized.inventoryTransaction) {
    normalized.warehouseEntry = '库存流水代表入库完成：' + normalized.inventoryTransaction
  }

  return normalized
}

export function normalizeRiskEvidence(event = {}) {
  const traceTarget = normalizeTraceTarget(event.traceTarget || {})
  return normalizeEvidenceList([
    { sourceType: 'purchaseOrder', sourceNo: traceTarget.purchaseOrder },
    { sourceType: 'receipt', sourceNo: traceTarget.receipt },
    { sourceType: 'inspection', sourceNo: traceTarget.inspection },
    { sourceType: 'warehouseEntry', sourceNo: traceTarget.warehouseEntry },
    { sourceType: 'inventoryTransaction', sourceNo: traceTarget.inventoryTransaction },
    { sourceType: 'payable', sourceNo: traceTarget.payable },
    { sourceType: 'paymentVoucher', sourceNo: traceTarget.paymentVoucher },
    { sourceType: 'riskEvidence', sourceNo: event.riskEvidence?.basis, evidenceText: event.riskEvidence?.reason },
    { sourceType: 'traceResolver', sourceNo: event.traceResolverEvidence?.matchedInventoryTransaction, evidenceText: event.traceResolverEvidence?.decision },
    { sourceType: 'inventoryDecision', sourceNo: event.inventoryChainDecision?.inventoryTransactionNos, evidenceText: event.inventoryChainDecision?.reason },
  ])
}

export function normalizeRiskEvent(event = {}) {
  const traceTarget = normalizeTraceTarget(event.traceTarget || {})
  return {
    ...event,
    traceTarget,
    normalizedEvidence: normalizeRiskEvidence({ ...event, traceTarget }),
  }
}

export function normalizeRiskEventCenter(center = {}) {
  const riskEvents = (center.riskEvents || []).map((event) => normalizeRiskEvent(event))
  return {
    ...center,
    riskEvents,
  }
}

export function normalizeDiagnosticEvidence(payload = {}) {
  return {
    ...payload,
    riskEventCenter: normalizeRiskEventCenter(payload.riskEventCenter || {}),
    riskEventCenterView: payload.riskEventCenterView
      ? {
          ...payload.riskEventCenterView,
          displayEvents: (payload.riskEventCenterView.displayEvents || []).map((event) => normalizeRiskEvent(event)),
        }
      : payload.riskEventCenterView,
  }
}
