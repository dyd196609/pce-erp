import request, { getAuthenticationHeaders } from './request.js'
import { adaptPurchaseRequestPayload } from './purchaseRequestPayloadAdapter.js'

export { adaptPurchaseRequestPayload } from './purchaseRequestPayloadAdapter.js'

export const purchaseRequestApi = Object.freeze({
  create(data) {
    return request({ method: 'POST', url: '/api/procurement/purchase-requests/',
      data: adaptPurchaseRequestPayload(data), headers: getAuthenticationHeaders(),
      meta: { module: 'SCM', explicitBusinessAction: true, requiresAuthentication: true,
        permissionCode: 'procurement.purchase_request.create' } })
  },
  update(id, data) {
    return request({ method: 'PUT', url: `/api/procurement/purchase-requests/${id}/`,
      data: adaptPurchaseRequestPayload(data), headers: getAuthenticationHeaders(),
      meta: { module: 'SCM', explicitBusinessAction: true, requiresAuthentication: true,
        permissionCode: 'purchase_request.update' } })
  },
  submit(id) {
    return request({
      method: 'POST',
      url: `/api/procurement/purchase-requests/${id}/submit/`,
      headers: getAuthenticationHeaders(),
      meta: { module: 'SCM', explicitBusinessAction: true, requiresAuthentication: true, permissionCode: 'purchase_request.submit' },
    })
  },
  approve(id) {
    return request({
      method: 'POST',
      url: `/api/procurement/purchase-requests/${id}/approve/`,
      headers: getAuthenticationHeaders(),
      meta: { module: 'SCM', explicitBusinessAction: true, requiresAuthentication: true, permissionCode: 'purchase_request.approve' },
    })
  },
  close(id) {
    return request({ method: 'POST', url: `/api/procurement/purchase-requests/${id}/close/`, meta: { module: 'SCM', explicitBusinessAction: true } })
  },
  remove(id) {
    return request({ method: 'DELETE', url: `/api/procurement/purchase-requests/${id}/`, meta: { module: 'SCM', explicitBusinessAction: true } })
  },
  searchReference(type, query, limit = 20) {
    return request({
      method: 'GET',
      url: `/api/procurement/purchase-request-references/${type}/`,
      params: { q: query, limit },
      headers: getAuthenticationHeaders(),
      meta: { module: 'SCM', readOnly: true, requiresAuthentication: true },
    })
  },
})
