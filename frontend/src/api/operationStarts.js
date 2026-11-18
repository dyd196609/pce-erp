import request from './request'
import { OPERATION_START_PAGE } from '@/meta/runtime/operationStartContract.js'

export const operationStartsApi = Object.freeze({
  read(params = {}) {
    return request({ method: 'GET', url: OPERATION_START_PAGE.apiUrl, params, timeout: 90000,
      meta: { module: 'MES', readOnly: true } })
  },
  start(taskId, data) {
    return request({ method: 'POST', url: `${OPERATION_START_PAGE.apiUrl}${encodeURIComponent(taskId)}/start/`, data,
      timeout: 90000, meta: { module: 'MES', explicitBusinessAction: true } })
  },
})
