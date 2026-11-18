import request from './request.js'
import { executeOrganizationWriteRequest } from './organizationRequestIdentity.js'

export const accessControlApi = {
  foundation() {
    return request({
      method: 'GET',
      url: '/api/access-control/foundation/',
      meta: { module: 'SYSTEM', factLoad: true, readOnly: true },
    })
  },
  profile() {
    return request({
      method: 'GET',
      url: '/api/access-control/profile/',
      meta: { module: 'SYSTEM', factLoad: true, readOnly: true },
    })
  },
  scopedEmployees(params = {}) {
    return request({
      method: 'GET',
      url: '/api/pfm/employees/',
      params: { view: 'all', ...params },
      meta: { module: 'PFM', factLoad: true, readOnly: true },
    })
  },
  authorize(payload) {
    return request({
      method: 'POST',
      url: '/api/access-control/decisions/',
      data: payload,
      meta: { module: 'SYSTEM', readOnly: true, authorizationDecision: true },
    })
  },
  actions() {
    return request({
      method: 'GET',
      url: '/api/access-control/actions/',
      meta: { module: 'SYSTEM', factLoad: true, readOnly: true },
    })
  },
  organizationDirectory() {
    return request({
      method: 'GET',
      url: '/api/access-control/organization-directory/',
      meta: { module: 'SYSTEM', factLoad: true, readOnly: true },
    })
  },
  enterpriseOrganizationModel() {
    return request({
      method: 'GET',
      url: '/api/access-control/enterprise-organization-model/',
      meta: { module: 'SYSTEM', factLoad: true, readOnly: true },
    })
  },
  masterDataExecutorPreview() {
    return request({
      method: 'GET',
      url: '/api/access-control/master-data-executor-preview/',
      meta: { module: 'SYSTEM', factLoad: true, readOnly: true },
    })
  },
  responsibilities(params = {}) {
    return request({
      method: 'GET',
      url: '/api/access-control/responsibilities/',
      params,
      meta: { module: 'SYSTEM', factLoad: true, readOnly: true },
    })
  },
  saveEnterpriseOrganizationModel(action, payload) {
    return executeOrganizationWriteRequest({
      action,
      payload,
      send: (requestIdentity) => request({
        method: 'POST',
        url: '/api/access-control/enterprise-organization-model/',
        data: { action, payload },
        headers: requestIdentity
          ? { 'Idempotency-Key': requestIdentity }
          : undefined,
        meta: { module: 'SYSTEM', explicitBusinessAction: true },
      }),
    })
  },
  action(action, payload) {
    return request({
      method: 'POST',
      url: '/api/access-control/foundation/',
      data: { action, payload },
      meta: { module: 'SYSTEM', explicitBusinessAction: true },
    })
  },
  organizationImportTemplate(entity) {
    return request({ method: 'GET', url: `/api/access-control/organization-import/${entity}/template/`, responseType: 'blob', meta: { module: 'SYSTEM' } })
  },
  organizationImportContext(entity) {
    return request({ method:'GET', url:`/api/access-control/organization-import/${entity}/template/`, params:{context:'1'}, meta:{module:'SYSTEM',readOnly:true} })
  },
  organizationImportErrorReport(entity, file) {
    const data=new FormData(); data.append('file',file)
    return request({method:'POST',url:`/api/access-control/organization-import/${entity}/preview/`,params:{report:'xlsx'},data,responseType:'blob',meta:{module:'SYSTEM',readOnly:true}})
  },
  previewOrganizationImport(entity, file) {
    const data = new FormData()
    data.append('file', file)
    return request({ method: 'POST', url: `/api/access-control/organization-import/${entity}/preview/`, data, meta: { module: 'SYSTEM', readOnly: true } })
  },
  commitOrganizationImport(entity, file, previewFingerprint, idempotencyKey, previewActorBinding) {
    const data = new FormData()
    data.append('file', file)
    data.append('previewFingerprint', previewFingerprint)
    data.append('idempotencyKey', idempotencyKey)
    data.append('confirmed', 'true')
    data.append('previewActorBinding', JSON.stringify(previewActorBinding || {}))
    return request({ method: 'POST', url: `/api/access-control/organization-import/${entity}/commit/`, data, meta: { module: 'SYSTEM', explicitBusinessAction: true } })
  },
}
