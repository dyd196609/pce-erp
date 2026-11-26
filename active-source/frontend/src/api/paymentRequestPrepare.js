import request from './request.js'

export const paymentRequestPrepareApi = Object.freeze({
  list(params = {}) {
    return request({
      method: 'GET',
      url: '/api/finance/payment-request-prepares/',
      params,
      meta: { module: 'finance' },
    })
  },
  detail(id) {
    return request({
      method: 'GET',
      url: `/api/finance/payment-request-prepares/${encodeURIComponent(id)}`,
      meta: { module: 'finance' },
    })
  },
  bySource(sourceId) {
    return request({
      method: 'GET',
      url: `/api/finance/payment-request-prepares/by-source/${encodeURIComponent(sourceId)}`,
      meta: { module: 'finance' },
    })
  },
  generate(payload) {
    return request({
      method: 'POST',
      url: '/api/finance/payment-request-prepares/generate',
      data: payload,
      meta: { module: 'finance' },
    })
  },
  savePaymentData(id, payload) {
    return request({
      method: 'PUT',
      url: `/api/finance/payment-request-prepares/${encodeURIComponent(id)}/payment-data`,
      data: payload,
      meta: { module: 'finance' },
    })
  },
  validate(id, payload) {
    return request({
      method: 'POST',
      url: `/api/finance/payment-request-prepares/${encodeURIComponent(id)}/validate`,
      data: payload,
      meta: { module: 'finance' },
    })
  },
  validationIssues(id) {
    return request({
      method: 'GET',
      url: `/api/finance/payment-request-prepares/${encodeURIComponent(id)}/validation-issues`,
      meta: { module: 'finance' },
    })
  },
  eligibility(id) {
    return request({
      method: 'GET',
      url: `/api/finance/payment-request-prepares/${encodeURIComponent(id)}/payment-request-eligibility`,
      meta: { module: 'finance' },
    })
  },
  generationResult(idempotencyKey) {
    return request({
      method: 'GET',
      url: `/api/finance/payment-request-prepares/generation-results/${encodeURIComponent(idempotencyKey)}`,
      meta: { module: 'finance' },
    })
  },
  validationResult(idempotencyKey) {
    return request({
      method: 'GET',
      url: `/api/finance/payment-request-prepares/validation-results/${encodeURIComponent(idempotencyKey)}`,
      meta: { module: 'finance' },
    })
  },
})
