import request from './request'
import { OPERATION_RESOURCE_API } from '@/meta/runtime/operationResourceAdmission.js'

export const operationResourcesApi = Object.freeze({
  read(params = {}) {
    return request({ method: 'GET', url: OPERATION_RESOURCE_API, params: { ...params, responseMode: 'selected-detail' }, timeout: 90000,
      meta: { module: 'MES', readOnly: true } })
  },
  selectResource(operationId, data) {
    return request({ method: 'POST', url: `${OPERATION_RESOURCE_API}${encodeURIComponent(operationId)}/select/`, data,
      timeout: 90000, meta: { module: 'MES', explicitBusinessAction: true } })
  },
  receiveOperation(operationId, data) {
    return request({ method: 'POST', url: `${OPERATION_RESOURCE_API}${encodeURIComponent(operationId)}/receive/`, data,
      timeout: 90000, meta: { module: 'MES', explicitBusinessAction: true } })
  },
})
