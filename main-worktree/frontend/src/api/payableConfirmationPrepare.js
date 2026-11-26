import request from './request.js'

export const payableConfirmationPrepareApi = Object.freeze({
  list(params = {}) {
    return request({
      method: 'GET',
      url: '/api/finance/payable-confirmation-prepares/',
      params,
      meta: { module: 'finance' },
    })
  },
  detail(id) {
    return request({
      method: 'GET',
      url: `/api/finance/payable-confirmation-prepares/${encodeURIComponent(id)}`,
      meta: { module: 'finance' },
    })
  },
  bySource(purchaseAccountsPayableDraftId) {
    return request({
      method: 'GET',
      url: `/api/finance/payable-confirmation-prepares/by-source/${encodeURIComponent(purchaseAccountsPayableDraftId)}`,
      meta: { module: 'finance' },
    })
  },
  validate(payload) {
    return request({
      method: 'POST',
      url: '/api/finance/payable-confirmation-prepares/validate',
      data: payload,
      meta: { module: 'finance' },
    })
  },
  generate(payload) {
    return request({
      method: 'POST',
      url: '/api/finance/payable-confirmation-prepares/generate',
      data: payload,
      meta: { module: 'finance' },
    })
  },
  generationResult(idempotencyKey) {
    return request({
      method: 'GET',
      url: `/api/finance/payable-confirmation-prepares/generation-results/${encodeURIComponent(idempotencyKey)}`,
      meta: { module: 'finance' },
    })
  },
})
