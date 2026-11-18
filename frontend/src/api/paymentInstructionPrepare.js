import request from './request.js'

export const paymentInstructionPrepareApi = Object.freeze({
  list(params = {}) {
    return request({ method: 'GET', url: '/api/finance/payment-instruction-prepares/', params, meta: { module: 'finance', factLoad: true } })
  },
  detail(id) {
    return request({ method: 'GET', url: `/api/finance/payment-instruction-prepares/${encodeURIComponent(id)}`, meta: { module: 'finance' } })
  },
  bySource(id) {
    return request({ method: 'GET', url: `/api/finance/payment-instruction-prepares/by-source/${encodeURIComponent(id)}`, meta: { module: 'finance' } })
  },
  generate(data) {
    return request({ method: 'POST', url: '/api/finance/payment-instruction-prepares/generate', data, meta: { module: 'finance' } })
  },
  saveInstructionData(id, data) {
    return request({ method: 'PUT', url: `/api/finance/payment-instruction-prepares/${encodeURIComponent(id)}/instruction-data`, data, meta: { module: 'finance' } })
  },
  validate(id, data) {
    return request({ method: 'POST', url: `/api/finance/payment-instruction-prepares/${encodeURIComponent(id)}/validate`, data, meta: { module: 'finance' } })
  },
  eligibility(id) {
    return request({ method: 'GET', url: `/api/finance/payment-instruction-prepares/${encodeURIComponent(id)}/payment-order-prepare-eligibility`, meta: { module: 'finance' } })
  },
  validationIssues(id) {
    return request({ method: 'GET', url: `/api/finance/payment-instruction-prepares/${encodeURIComponent(id)}/validation-issues`, meta: { module: 'finance' } })
  },
  generationResult(key) {
    return request({ method: 'GET', url: `/api/finance/payment-instruction-prepares/generation-results/${encodeURIComponent(key)}`, meta: { module: 'finance' } })
  },
  instructionDataResult(key) {
    return request({ method: 'GET', url: `/api/finance/payment-instruction-prepares/instruction-data-results/${encodeURIComponent(key)}`, meta: { module: 'finance' } })
  },
  validationResult(key) {
    return request({ method: 'GET', url: `/api/finance/payment-instruction-prepares/validation-results/${encodeURIComponent(key)}`, meta: { module: 'finance' } })
  },
})
