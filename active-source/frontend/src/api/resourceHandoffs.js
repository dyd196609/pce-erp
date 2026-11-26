import request from './request'
import { RESOURCE_HANDOFF_API } from '@/meta/runtime/operationResourceHandoff.js'

export const resourceHandoffsApi = Object.freeze({
  read(params = {}) {
    return request({ method: 'GET', url: RESOURCE_HANDOFF_API, params: { ...params, responseMode: 'selected-detail' }, timeout: 90000,
      meta: { module: 'MES', readOnly: true } })
  },
  confirm(operationId, data) {
    return request({ method: 'POST', url: `${RESOURCE_HANDOFF_API}${encodeURIComponent(operationId)}/confirm/`, data,
      timeout: 90000, meta: { module: 'MES', explicitBusinessAction: true } })
  },
})
