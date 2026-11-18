import request from './request'

export const formalPaymentOrderApi = {
  list(params = {}) {
    return request({ method: 'GET', url: '/api/finance/formal-payment-orders/', params, meta: { module: 'finance', factLoad: true } })
  },
  detail(id) {
    return request({ method: 'GET', url: `/api/finance/formal-payment-orders/${encodeURIComponent(id)}`, meta: { module: 'finance' } })
  },
  bySource(sourceId) {
    return request({ method: 'GET', url: `/api/finance/formal-payment-orders/by-source/${encodeURIComponent(sourceId)}`, meta: { module: 'finance' } })
  },
  generate(data) {
    return request({ method: 'POST', url: '/api/finance/formal-payment-orders/generate', data, meta: { module: 'finance' } })
  },
  generationResult(idempotencyKey) {
    return request({ method: 'GET', url: `/api/finance/formal-payment-orders/generation-results/${encodeURIComponent(idempotencyKey)}`, meta: { module: 'finance' } })
  },
  submit(id, data) {
    return request({ method: 'POST', url: `/api/finance/formal-payment-orders/${encodeURIComponent(id)}/submit`, data, meta: { module: 'finance' } })
  },
  approve(id, data) {
    return request({ method: 'POST', url: `/api/finance/formal-payment-orders/${encodeURIComponent(id)}/approve`, data, meta: { module: 'finance' } })
  },
  freeze(id, data) {
    return request({ method: 'POST', url: `/api/finance/formal-payment-orders/${encodeURIComponent(id)}/freeze`, data, meta: { module: 'finance' } })
  },
  approvalHistory(id) {
    return request({ method: 'GET', url: `/api/finance/formal-payment-orders/${encodeURIComponent(id)}/approval-history`, meta: { module: 'finance' } })
  },
}
