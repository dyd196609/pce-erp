import request from './request'


export const pdeApi = {
  testEngineeringRoutingBindings() { return request({method:'GET',url:'/api/pde/routings/test-engineering-binding/',params:{all:'1'},meta:{module:'pde'}}) },
  testBusinessBomHandoff() { return request({method:'GET',url:'/api/pde/test-business-bom-handoff/',meta:{module:'pde'}}) },
  deriveTestBom(data) { return request({method:'POST',url:'/api/pde/test-business-bom-handoff/',data,meta:{module:'pde'}}) },
  designRevisionApprovals(revisionId) { return request({method:'GET',url:'/api/pde/design-revision-approvals/',params:{revisionId},meta:{module:'pde'}}) },
  designRevisionApprovalAction(data,key) { return request({method:'POST',url:'/api/pde/design-revision-approvals/',data,headers:{'Idempotency-Key':key},meta:{module:'pde'}}) },
  orderEngineeringIntake(salesOrderItemId) {
    return request({method:'GET',url:'/api/pde/engineering-readiness/order-engineering-intake/',params:{salesOrderItemId},meta:{module:'pde'}})
  },
  confirmOrderEngineeringIntake(payload,idempotencyKey) {
    return request({method:'POST',url:'/api/pde/engineering-readiness/order-engineering-intake/',data:payload,headers:{'Idempotency-Key':idempotencyKey},meta:{module:'pde'}})
  },
  productionFeasibilityReview(sourceRecord, context = {}) {
    return request({ method: 'GET', url: '/api/pde/production-feasibility-reviews/', params: { ...context, ...(sourceRecord ? { sourceRecord } : {}) }, meta: { module: 'pde' } })
  },
  saveProductionFeasibilityReview(payload, idempotencyKey) {
    return request({ method: 'POST', url: '/api/pde/production-feasibility-reviews/', data: payload, headers: { 'Idempotency-Key': idempotencyKey }, meta: { module: 'pde' } })
  },
  productionFeasibilityReviewAction(payload, idempotencyKey) {
    return request({ method: 'POST', url: '/api/pde/production-feasibility-reviews/', data: payload, headers: { 'Idempotency-Key': idempotencyKey }, meta: { module: 'pde' } })
  },
  calculationBatchCatalog(params = {}) {
    return request({ method: 'GET', url: '/api/pde/a1-engineering/calculations/batch-reuse/', params, meta: { module: 'pde' } })
  },
  calculateSourceBatch(sourceKeys, context = {}) {
    return request({ method: 'POST', url: '/api/pde/a1-engineering/calculations/batch-reuse/', data: { sourceKeys, ...context }, meta: { module: 'pde' } })
  },
  engineeringDrafts(orderEngineeringInstanceId) {
    return request({ method: 'GET', url: '/api/pde/a1-engineering/calculations/batch-reuse/', params: { action: 'draftCatalog', orderEngineeringInstanceId }, timeout: 60000, meta: { module: 'pde' } })
  },
  engineeringDesignCalculationContext(sourceRecordId = '', { includeWorkloadSummary = true, workbookSourceRecordId = '' } = {}) {
    return request({ method: 'GET', url: '/api/pde/a1-engineering/calculations/batch-reuse/', params: { action: 'designCalculationContext', ...(sourceRecordId ? { sourceRecordId } : {}), ...(workbookSourceRecordId !== '' && workbookSourceRecordId != null ? { workbookSourceRecordId } : {}), ...(includeWorkloadSummary === false ? { includeWorkloadSummary: false } : {}) }, ...(includeWorkloadSummary !== false ? { timeout: 90000 } : {}), meta: { module: 'pde' } })
  },
  saveEngineeringDraft(payload) {
    return request({ method: 'POST', url: '/api/pde/a1-engineering/calculations/batch-reuse/', data: { action: 'saveDraft', ...payload }, meta: { module: 'pde' } })
  },
  saveRegisteredEngineeringSource(payload = {}) {
    return request({ method: 'POST', url: '/api/pde/a1-engineering/calculations/batch-reuse/', data: { action: 'saveRegisteredSourceDraft', ...payload }, meta: { module: 'pde' } })
  },
  facts(resource, params = {}) {
    return request({
      method: 'GET',
      url: `/api/pde/${resource}/`,
      params,
      meta: { module: 'pde' },
    })
  },
  generateManufacturingOutput(payload, idempotencyKey) {
    return request({ method: 'POST', url: '/api/pde/manufacturing-outputs/generate/',
      data: payload, headers: { 'Idempotency-Key': idempotencyKey }, meta: { module: 'pde' } })
  },
  releaseManufacturingOutput(outputId, payload, idempotencyKey) {
    return request({ method: 'POST', url: `/api/pde/manufacturing-outputs/${outputId}/release/`,
      data: payload, headers: { 'Idempotency-Key': idempotencyKey }, meta: { module: 'pde' } })
  },
  createRoutingVersionSuccessor(versionId, payload) {
    return request({
      method: 'POST',
      url: `/api/pde/routing-versions/${versionId}/successor/`,
      data: payload,
      meta: { module: 'pde' },
    })
  },
  reviewRoutingVersion(versionId, payload, idempotencyKey) {
    return request({
      method: 'POST',
      url: `/api/pde/routing-versions/${versionId}/review/`,
      data: payload,
      headers: { 'Idempotency-Key': idempotencyKey },
      meta: { module: 'pde' },
    })
  },
  releaseRoutingVersion(versionId, payload, idempotencyKey) {
    return request({
      method: 'POST',
      url: `/api/pde/routing-versions/${versionId}/release/`,
      data: payload,
      headers: { 'Idempotency-Key': idempotencyKey },
      meta: { module: 'pde' },
    })
  },
  reviewEngineeringDocumentVersion(versionId, payload, idempotencyKey) {
    return request({
      method: 'POST',
      url: `/api/pde/engineering-document-versions/${versionId}/review/`,
      data: payload,
      headers: { 'Idempotency-Key': idempotencyKey },
      meta: { module: 'pde' },
    })
  },
  releaseEngineeringDocumentVersion(versionId, payload, idempotencyKey) {
    return request({
      method: 'POST',
      url: `/api/pde/engineering-document-versions/${versionId}/release/`,
      data: payload,
      headers: { 'Idempotency-Key': idempotencyKey },
      meta: { module: 'pde' },
    })
  },
  saveRoutingStepApplicability(stepId, payload) {
    return request({
      method: 'POST',
      url: `/api/pde/routing-steps/${stepId}/applicability/`,
      data: payload,
      meta: { module: 'pde' },
    })
  },
  saveRoutingManualApplicability(versionId, payload) {
    return request({
      method: 'POST',
      url: `/api/pde/routing-versions/${versionId}/manual-applicability/`,
      data: payload,
      meta: { module: 'pde' },
    })
  },
  productVersionManagementAction(payload, idempotencyKey) {
    return request({
      method: 'POST',
      url: '/api/pde/product-version-management/',
      data: payload,
      headers: { 'Idempotency-Key': idempotencyKey },
      meta: { module: 'pde' },
    })
  },
  saveProductDesignDraft(payload, idempotencyKey) {
    return request({
      method: 'POST',
      url: '/api/pde/product-definitions/',
      data: payload,
      headers: { 'Idempotency-Key': idempotencyKey },
      meta: { module: 'pde' },
    })
  },
  productDesignAction(payload, idempotencyKey) {
    return request({
      method: 'POST',
      url: '/api/pde/product-definitions/',
      data: payload,
      headers: { 'Idempotency-Key': idempotencyKey },
      meta: { module: 'pde' },
    })
  },
  productDesignImportTemplate() {
    return request({ method: 'GET', url: '/api/pde/product-definitions/import-template/', responseType: 'blob', meta: { module: 'pde' } })
  },
  exportProductDesign(payload) {
    return request({ method: 'POST', url: '/api/pde/product-definitions/export/', data: payload, responseType: 'blob', meta: { module: 'pde' } })
  },
  previewProductDesignImport(file) {
    const data = new FormData()
    data.append('file', file)
    return request({ method: 'POST', url: '/api/pde/product-definitions/import-preview/', data, meta: { module: 'pde' } })
  },
  commitProductDesignImport(file, previewFingerprint, idempotencyKey) {
    const data = new FormData()
    data.append('file', file)
    data.append('previewFingerprint', previewFingerprint)
    data.append('idempotencyKey', idempotencyKey)
    data.append('confirmed', 'true')
    return request({ method: 'POST', url: '/api/pde/product-definitions/import-commit/', data, meta: { module: 'pde' } })
  },
  orderRoutingExecution(params={}) { return request({method:'GET',url:'/api/pde/order-routing-execution/',params,timeout:!params.action || ['test-schedules','test-work-order-reception','saved-order-work-orders','test-workshop-tasks','test-operation-starts'].includes(params.action)?90000:params.action==='date-preview'?60000:30000,meta:{module:'pde'}}) },
  foundationRoutingInitial(id,data) {return request({method:'POST',url:`/api/pde/a1-foundation/routings/${id}/initial-version/`,data,meta:{module:'pde'}})},
  saveOrderRoutingExecution(data) { return request({method:'POST',url:'/api/pde/order-routing-execution/',data,timeout:['save-test-schedule','cancel-test-schedule','generate-test-work-order','release-test-work-order','receive-test-workshop','dispatch-test-workshop-tasks','start-test-operation'].includes(data.action)?90000:30000,meta:{module:'pde'}}) },
  foundationRoutingVersions(id) { return request({method:'GET',url:`/api/pde/a1-foundation/routings/${id}/versions/`,meta:{module:'pde'}}) },
  foundationRoutingAction(id,action,data) { return request({method:'POST',url:`/api/pde/a1-foundation/routing-versions/${id}/${action}/`,data,meta:{module:'pde'}}) },
  productionFoundationA1(entity = '', params = {}) {
    return request({
      method: 'GET',
      url: `/api/pde/a1-foundation/${entity ? `${entity}/` : ''}`,
      params,
      meta: { module: 'pde' },
    })
  },
  wave2ManufacturingFoundation() {
    return request({
      method: 'GET',
      url: '/api/pde/wave2-manufacturing-foundation/',
      meta: { module: 'pde' },
    })
  },
  saveProductionFoundation(entity, payload, objectId = null) {
    return request({
      method: objectId ? 'PATCH' : 'POST',
      url: `/api/pde/a1-foundation/${entity}/${objectId ? `${objectId}/` : ''}`,
      data: payload,
      meta: { module: 'pde' },
    })
  },
  previewSourceFormat(payload) {
    return request({
      method: 'POST', url: '/api/pde/a1-foundation/engineering-source-records/',
      data: { action: 'sourceFormatPreview', sourcePayload: payload }, meta: { module: 'pde' },
    })
  },
  uploadSourceWorkbook(file) {
    const data = new FormData()
    data.append('action', 'upload-workbook')
    data.append('file', file)
    return request({ method:'POST',url:'/api/pde/a1-foundation/engineering-source-records/',data,meta:{ module:'pde' } })
  },
  getOperationWorkloadSources(params = {}) {
    return request({
      method: 'GET', url: '/api/pde/a1-foundation/operations/',
      params: { ...params, action: 'operationWorkloadSources' }, meta: { module: 'pde' },
    })
  },
  previewPlanStepVersionHandoff(payload) {
    return request({ method: 'POST', url: '/api/pde/plan-step-version-handoffs/',
      data: { ...payload, action: 'preview' }, meta: { module: 'pde' } })
  },
  activatePlanStepVersionHandoff(payload) {
    return request({ method: 'POST', url: '/api/pde/plan-step-version-handoffs/',
      data: { ...payload, action: 'activate' }, meta: { module: 'pde' } })
  },
  saveOperationWorkloadSource(payload) {
    return request({
      method: 'POST', url: '/api/pde/a1-foundation/operations/',
      data: { ...payload, action: 'configureOperationWorkloadSource' }, meta: { module: 'pde' },
    })
  },
  previewOperationWorkloadSourceConfiguration(operationId, configuration, context = {}) {
    return request({
      method: 'POST', url: '/api/pde/a1-foundation/operations/',
      data: {
        action: 'previewOperationWorkloadSourceConfiguration', operationId, configuration,
        companyId: context.companyId, productionPlanId: context.planId,
        routingStepId: context.routingStepId,
      },
      meta: { module: 'pde' },
    })
  },
  previewFoundationImport(file) {
    const data = new FormData()
    data.append('file', file)
    return request({
      method: 'POST',
      url: '/api/pde/foundation-import-preview/',
      data,
      meta: { module: 'pde' },
    })
  },
  formalImportTemplate(entity) {
    return request({ method: 'GET', url: `/api/pde/formal-import/${entity}/template/`, responseType: 'blob', meta: { module: 'pde' } })
  },
  previewFormalImport(entity, file) {
    const data = new FormData()
    data.append('file', file)
    return request({ method: 'POST', url: `/api/pde/formal-import/${entity}/preview/`, data, meta: { module: 'pde' } })
  },
  commitFormalImport(entity, file, previewFingerprint, idempotencyKey, previewActorBinding) {
    const data = new FormData()
    data.append('file', file)
    data.append('previewFingerprint', previewFingerprint)
    data.append('idempotencyKey', idempotencyKey)
    data.append('confirmed', 'true')
    data.append('previewActorBinding', JSON.stringify(previewActorBinding || {}))
    return request({ method: 'POST', url: `/api/pde/formal-import/${entity}/commit/`, data, meta: { module: 'pde' } })
  },
  transitionEngineering(entity, objectId, targetStatus, reason = '', idempotencyKey = '', action = '') {
    return request({
      method: 'POST',
      url: `/api/pde/a1-engineering/${entity}/${objectId}/transition/`,
      data: { targetStatus, reason, ...(action ? { action } : {}) },
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {},
      meta: { module: 'pde' },
    })
  },
  correctEngineeringRuleEffectivity(objectId, payload) {
    return request({
      method: 'POST',
      url: `/api/pde/a1-engineering/rules/${objectId}/correct-effectivity/`,
      data: payload,
      meta: { module: 'pde' },
    })
  },
  engineeringCalculations(params = {}) {
    return request({
      method: 'GET',
      url: '/api/pde/a1-engineering/calculations/',
      params,
      meta: { module: 'pde' },
    })
  },
  engineeringCalculationReadiness(params = {}) {
    return request({
      method: 'GET',
      url: '/api/pde/a1-engineering/calculations/readiness/',
      params,
      meta: { module: 'pde' },
    })
  },
  engineeringCalculation(objectId) {
    return request({
      method: 'GET',
      url: `/api/pde/a1-engineering/calculations/${objectId}/`,
      timeout: 60000,
      meta: { module: 'pde' },
    })
  },
  executeEngineeringCalculation(payload) {
    return request({
      method: 'POST',
      url: '/api/pde/a1-engineering/calculations/execute/',
      data: payload,
      meta: { module: 'pde' },
    })
  },
  testCalculationPreview(params) {
    return request({method:'GET',url:'/api/pde/a1-engineering/calculations/test-preview/',params,meta:{module:'pde'}})
  },
  testCalculationRecords(params) {
    return request({method:'GET',url:'/api/pde/a1-engineering/calculations/test-records/',params,meta:{module:'pde'}})
  },
  saveTestCalculation(data,key) {
    return request({method:'POST',url:'/api/pde/a1-engineering/calculations/test-records/',data,headers:{'Idempotency-Key':key},meta:{module:'pde'}})
  },
  formalEngineeringContinuation(orderNo = '', context = {}) {
    return request({
      method: 'GET',
      url: '/api/pde/a1-engineering/calculations/formal-continuation/',
      params: { ...(orderNo ? { orderNo } : {}), ...context },
      meta: { module: 'pde' },
    })
  },
  formalEngineeringContinuationAction(payload) {
    return request({
      method: 'POST',
      url: '/api/pde/a1-engineering/calculations/formal-continuation/',
      data: payload,
      meta: { module: 'pde' },
    })
  },
  previewEngineeringCalculationVersionContinuation(payload) {
    return request({
      method: 'POST',
      url: '/api/pde/a1-engineering/calculations/version-continuation/preview/',
      data: payload,
      meta: { module: 'pde' },
    })
  },
  executeEngineeringCalculationVersionContinuation(payload) {
    return request({
      method: 'POST',
      url: '/api/pde/a1-engineering/calculations/version-continuation/execute/',
      data: payload,
      meta: { module: 'pde' },
    })
  },
  preflightOrderEngineeringCalculation(params) {
    return request({
      method: 'GET',
      url: '/api/pde/a1-engineering/order-calculation/condition-preflight/',
      params,
      meta: { module: 'pde' },
    })
  },
  validateOrderEngineeringCalculation(payload) {
    return request({
      method: 'POST',
      url: '/api/pde/a1-engineering/order-calculation/validate/',
      data: payload,
      meta: { module: 'pde' },
    })
  },
  trialEngineeringMethods(payload) {
    return request({
      method: 'POST',
      url: '/api/pde/a1-engineering/order-calculation/method-trial/',
      data: payload,
      meta: { module: 'pde' },
    })
  },
  previewOrderBom(calculationId) {
    return request({
      method: 'GET',
      url: `/api/pde/a1-engineering/calculations/${calculationId}/bom-preview/`,
      meta: { module: 'pde' },
    })
  },
  orderBomHandoff(params = {}) {
    return request({
      method: 'GET',
      url: '/api/pde/product-boms/',
      params: { handoff: 1, ...params },
      meta: { module: 'pde' },
    })
  },
  generateOrderBom(calculationId, payload) {
    return request({
      method: 'POST',
      url: `/api/pde/a1-engineering/calculations/${calculationId}/bom-generate/`,
      data: payload,
      meta: { module: 'pde' },
    })
  },
}
