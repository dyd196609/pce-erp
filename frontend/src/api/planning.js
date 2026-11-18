import request from './request'

export const planningApi = {
  productionBatchFoundationPreview() {
    return request({ method: 'GET', url: '/api/planning/production-batch-foundation/preview/', meta: { module: 'plan' } })
  },
  facts(params = {}) {
    return request({ method: 'GET', url: '/api/planning/facts/', params, meta: { module: 'plan' } })
  },
  getProductionPlanStartDate(planId) {
    return request({ method: 'GET', url: `/api/planning/production-plans/${encodeURIComponent(planId)}/start-date/`, meta: { module: 'plan', readOnly: true } })
  },
  saveProductionPlanStartDate(planId, data) {
    return request({ method: 'PATCH', url: `/api/planning/production-plans/${encodeURIComponent(planId)}/start-date/`, data, meta: { module: 'plan', explicitBusinessAction: true } })
  },
  getProductionPlanFormalScheduling(planId) {
    return request({ method: 'GET', url: `/api/planning/production-plans/${encodeURIComponent(planId)}/formal-scheduling/`, meta: { module: 'plan', readOnly: true } })
  },
  getProductionPlanWorkOrderReception(planId, params = {}) {
    return request({ method: 'GET', url: `/api/planning/production-plans/${encodeURIComponent(planId)}/work-order-reception/`, params, meta: { module: 'plan', readOnly: true } })
  },
  generateProductionPlanWorkOrder(planId, data) {
    return request({ method: 'POST', url: `/api/planning/production-plans/${encodeURIComponent(planId)}/work-order/generate/`, data, meta: { module: 'plan', explicitBusinessAction: true } })
  },
  releaseProductionPlanWorkOrder(planId, data) {
    return request({ method: 'POST', url: `/api/planning/production-plans/${encodeURIComponent(planId)}/work-order/release/`, data, meta: { module: 'plan', explicitBusinessAction: true } })
  },
  getWorkOrderWorkshopReception(params = {}) {
    return request({ method: 'GET', url: '/api/planning/work-order-workshop-reception/', params: { ...params, responseMode: 'selected-detail' }, meta: { module: 'MES', readOnly: true } })
  },
  receiveWorkOrderWorkshop(workOrderId, workshopId, data) {
    return request({ method: 'POST', url: `/api/planning/work-orders/${encodeURIComponent(workOrderId)}/workshops/${encodeURIComponent(workshopId)}/receive/`, data, meta: { module: 'MES', explicitBusinessAction: true } })
  },
  validateProductionPlanFormalScheduling(planId) {
    return request({ method: 'GET', url: `/api/planning/production-plans/${encodeURIComponent(planId)}/formal-scheduling/admission/`, meta: { module: 'plan', readOnly: true } })
  },
  saveProductionPlanFormalScheduling(planId, data) {
    return request({ method: 'POST', url: `/api/planning/production-plans/${encodeURIComponent(planId)}/formal-scheduling/`, data, meta: { module: 'plan', explicitBusinessAction: true } })
  },
  authorizeProductionPlanSchedulingScope(planId, data) {
    return request({ method: 'POST', url: `/api/planning/production-plans/${encodeURIComponent(planId)}/formal-scheduling/capacity-scope/`, data, meta: { module: 'plan', explicitBusinessAction: true } })
  },
  cancelProductionPlanFormalSchedule(planId, scheduleId, data) {
    return request({ method: 'POST', url: `/api/planning/production-plans/${encodeURIComponent(planId)}/formal-schedules/${encodeURIComponent(scheduleId)}/cancel/`, data, meta: { module: 'plan', explicitBusinessAction: true } })
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
