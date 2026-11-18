import request from './request.js'

export const paymentRequestApi = Object.freeze({
  list(params = {}) {
    return request({ method: 'GET', url: '/api/finance/payment-requests/', params, meta: { module: 'finance', factLoad: true } })
  },
  detail(id) {
    return request({ method: 'GET', url: `/api/finance/payment-requests/${encodeURIComponent(id)}`, meta: { module: 'finance' } })
  },
  bySource(id) {
    return request({ method: 'GET', url: `/api/finance/payment-requests/by-source/${encodeURIComponent(id)}`, meta: { module: 'finance' } })
  },
  generate(data) {
    return request({ method: 'POST', url: '/api/finance/payment-requests/generate', data, meta: { module: 'finance' } })
  },
  submit(id, data) {
    return request({ method: 'POST', url: `/api/finance/payment-requests/${encodeURIComponent(id)}/submit`, data, meta: { module: 'finance' } })
  },
  approve(id, taskId, data) {
    return request({ method: 'POST', url: `/api/finance/payment-requests/${encodeURIComponent(id)}/tasks/${encodeURIComponent(taskId)}/approve`, data, meta: { module: 'finance' } })
  },
  reject(id, taskId, data) {
    return request({ method: 'POST', url: `/api/finance/payment-requests/${encodeURIComponent(id)}/tasks/${encodeURIComponent(taskId)}/reject`, data, meta: { module: 'finance' } })
  },
  approvalRoute(id) {
    return request({ method: 'GET', url: `/api/finance/payment-requests/${encodeURIComponent(id)}/approval-route`, meta: { module: 'finance' } })
  },
  approvalTasks(id) {
    return request({ method: 'GET', url: `/api/finance/payment-requests/${encodeURIComponent(id)}/approval-tasks`, meta: { module: 'finance' } })
  },
  approvalHistory(id) {
    return request({ method: 'GET', url: `/api/finance/payment-requests/${encodeURIComponent(id)}/approval-history`, meta: { module: 'finance' } })
  },
  eligibility(id) {
    return request({ method: 'GET', url: `/api/finance/payment-requests/${encodeURIComponent(id)}/payment-instruction-prepare-eligibility`, meta: { module: 'finance' } })
  },
  generationResult(key) {
    return request({ method: 'GET', url: `/api/finance/payment-requests/generation-results/${encodeURIComponent(key)}`, meta: { module: 'finance' } })
  },
  submissionResult(key) {
    return request({ method: 'GET', url: `/api/finance/payment-requests/submission-results/${encodeURIComponent(key)}`, meta: { module: 'finance' } })
  },
  approvalResult(key) {
    return request({ method: 'GET', url: `/api/finance/payment-requests/approval-results/${encodeURIComponent(key)}`, meta: { module: 'finance' } })
  },
})
