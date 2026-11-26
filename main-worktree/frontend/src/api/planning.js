import request from './request'

export const planningApi = {
  productionBatchFoundationPreview() {
    return request({ method: 'GET', url: '/api/planning/production-batch-foundation/preview/', meta: { module: 'plan' } })
  },
  facts(params = {}) {
    return request({ method: 'GET', url: '/api/planning/facts/', params, meta: { module: 'plan' } })
  },
  createDemand(data) {
    return request({ method: 'POST', url: '/api/planning/demands/', data, meta: { module: 'plan' } })
  },
  generateMps(data) {
    return request({ method: 'POST', url: '/api/planning/mps/runs/', data, meta: { module: 'plan' } })
  },
  generateMrp(mpsRunId, data) {
    return request({ method: 'POST', url: `/api/planning/mps/runs/${encodeURIComponent(mpsRunId)}/mrp/`, data, meta: { module: 'plan' } })
  },
  calculateDemand(demandId) {
    return request({ method: 'POST', url: `/api/planning/demands/${encodeURIComponent(demandId)}/calculate/`, meta: { module: 'plan' } })
  },
  confirmPlan(requirementId) {
    return request({ method: 'POST', url: `/api/planning/requirements/${encodeURIComponent(requirementId)}/confirm-plan/`, meta: { module: 'plan' } })
  },
  convertPurchasePlan(purchasePlanId) {
    return request({ method: 'POST', url: `/api/planning/purchase-plans/${encodeURIComponent(purchasePlanId)}/convert-to-purchase-request/`, meta: { module: 'plan' } })
  },
  validate(requirementId) {
    return request({ method: 'GET', url: `/api/planning/requirements/${encodeURIComponent(requirementId)}/validate/`, meta: { module: 'plan' } })
  },
  trace(reference) {
    return request({ method: 'GET', url: '/api/planning/trace/', params: { reference }, meta: { module: 'plan' } })
  },
}
