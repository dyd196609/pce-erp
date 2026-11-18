import request from './request.js'

export const purchaseInvoicePrepareApi = Object.freeze({
  list(params = {}) {
    return request({ method: 'GET', url: '/api/scm/purchase-invoice-prepares/', params, meta: { module: 'scm' } })
  },
  detail(id) {
    return request({ method: 'GET', url: `/api/scm/purchase-invoice-prepares/${encodeURIComponent(id)}`, meta: { module: 'scm' } })
  },
  bySource(reconciliationId) {
    return request({ method: 'GET', url: `/api/scm/purchase-invoice-prepares/by-source/${encodeURIComponent(reconciliationId)}`, meta: { module: 'scm' } })
  },
  generate(payload) {
    return request({ method: 'POST', url: '/api/scm/purchase-invoice-prepares/generate', data: payload, meta: { module: 'scm' } })
  },
  generationResult(idempotencyKey) {
    return request({ method: 'GET', url: `/api/scm/purchase-invoice-prepares/generation-results/${encodeURIComponent(idempotencyKey)}`, meta: { module: 'scm' } })
  },
  invoiceData(id) {
    return request({ method: 'GET', url: `/api/scm/purchase-invoice-prepares/${encodeURIComponent(id)}/invoice-data`, meta: { module: 'scm' } })
  },
  validationIssues(id) {
    return request({ method: 'GET', url: `/api/scm/purchase-invoice-prepares/${encodeURIComponent(id)}/validation-issues`, meta: { module: 'scm' } })
  },
  accountsPayableDraftEligibility(id) {
    return request({ method: 'GET', url: `/api/scm/purchase-invoice-prepares/${encodeURIComponent(id)}/accounts-payable-draft-eligibility`, meta: { module: 'scm' } })
  },
  saveInvoiceData(id, payload) {
    return request({ method: 'PUT', url: `/api/scm/purchase-invoice-prepares/${encodeURIComponent(id)}/invoice-data`, data: payload, meta: { module: 'scm' } })
  },
  validateInvoiceData(id, payload) {
    return request({ method: 'POST', url: `/api/scm/purchase-invoice-prepares/${encodeURIComponent(id)}/validate`, data: payload, meta: { module: 'scm' } })
  },
  validationResult(idempotencyKey) {
    return request({ method: 'GET', url: `/api/scm/purchase-invoice-prepares/validation-results/${encodeURIComponent(idempotencyKey)}`, meta: { module: 'scm' } })
  },
})
