import request from './request.js'

export const purchaseAccountsPayableDraftApi = Object.freeze({
  list(params = {}) {
    return request({
      method: 'GET',
      url: '/api/scm/purchase-accounts-payable-drafts/',
      params,
      meta: { module: 'scm' },
    })
  },
  detail(id) {
    return request({
      method: 'GET',
      url: `/api/scm/purchase-accounts-payable-drafts/${encodeURIComponent(id)}`,
      meta: { module: 'scm' },
    })
  },
  bySource(purchaseInvoicePrepareId) {
    return request({
      method: 'GET',
      url: `/api/scm/purchase-accounts-payable-drafts/by-source/${encodeURIComponent(purchaseInvoicePrepareId)}`,
      meta: { module: 'scm' },
    })
  },
  generate(payload) {
    return request({
      method: 'POST',
      url: '/api/scm/purchase-accounts-payable-drafts/generate',
      data: payload,
      meta: { module: 'scm' },
    })
  },
  generationResult(idempotencyKey) {
    return request({
      method: 'GET',
      url: `/api/scm/purchase-accounts-payable-drafts/generation-results/${encodeURIComponent(idempotencyKey)}`,
      meta: { module: 'scm' },
    })
  },
})
