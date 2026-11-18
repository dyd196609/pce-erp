import request from './request.js'

export function generatePurchaseReconciliation(payload) {
  return request({ method: 'POST', url: '/api/scm/purchase-reconciliations/generate', data: payload, meta: { module: 'scm' } })
}

export function getPurchaseReconciliationGenerationResult(idempotencyKey) {
  return request({ method: 'GET', url: `/api/scm/purchase-reconciliations/generation-results/${encodeURIComponent(idempotencyKey)}`, meta: { module: 'scm' } })
}

export function getPurchaseReconciliationBySource(sourceKey) {
  return request({ method: 'GET', url: `/api/scm/purchase-reconciliations/by-source/${encodeURIComponent(sourceKey)}`, meta: { module: 'scm' } })
}

export function listPurchaseReconciliations(params = {}) {
  return request({ method: 'GET', url: '/api/scm/purchase-reconciliations/', params, meta: { module: 'scm' } })
}

export function getPurchaseReconciliation(id) {
  return request({ method: 'GET', url: `/api/scm/purchase-reconciliations/${encodeURIComponent(id)}`, meta: { module: 'scm' } })
}

export function listPurchaseReconciliationDifferences(id) {
  return request({ method: 'GET', url: `/api/scm/purchase-reconciliations/${encodeURIComponent(id)}/differences`, meta: { module: 'scm' } })
}

export function getPurchaseReconciliationInvoicePrepareEligibility(id) {
  return request({ method: 'GET', url: `/api/scm/purchase-reconciliations/${encodeURIComponent(id)}/invoice-prepare-eligibility`, meta: { module: 'scm' } })
}

export function completePurchaseReconciliationCheck(id, payload) {
  return request({ method: 'POST', url: `/api/scm/purchase-reconciliations/${encodeURIComponent(id)}/complete-check`, data: payload, meta: { module: 'scm' } })
}
