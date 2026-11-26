import request from './request'

export const paymentRiskReviewApi = {
  list(params = {}) {
    return request({ method: 'GET', url: '/api/finance/payment-risk-reviews/', params, meta: { module: 'finance' } })
  },
  detail(id) {
    return request({ method: 'GET', url: `/api/finance/payment-risk-reviews/${encodeURIComponent(id)}`, meta: { module: 'finance' } })
  },
  execute(id, data) {
    return request({ method: 'POST', url: `/api/finance/payment-risk-reviews/${encodeURIComponent(id)}/execute`, data, meta: { module: 'finance' } })
  },
  eligibility(id) {
    return request({ method: 'GET', url: `/api/finance/payment-risk-reviews/${encodeURIComponent(id)}/eligibility`, meta: { module: 'finance' } })
  },
}

