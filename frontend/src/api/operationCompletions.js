import { timedMesRead } from '@/meta/runtime/mesReadTiming.js'
import request from './request'
import { OPERATION_COMPLETION_PAGE } from '@/meta/runtime/operationCompletionContract.js'
export const operationCompletionsApi = Object.freeze({
  read(params = {}) {
    return timedMesRead(()=>request({ method: 'GET', url: OPERATION_COMPLETION_PAGE.apiUrl, params, timeout: 90000,
      meta: { module: 'MES', readOnly: true } }),OPERATION_COMPLETION_PAGE.apiUrl)
  },
  request(taskId, data) {
    return request({ method: 'POST', url: `${OPERATION_COMPLETION_PAGE.apiUrl}${encodeURIComponent(taskId)}/request/`, data,
      timeout: 90000, meta: { module: 'MES', explicitBusinessAction: true } })
  },
  approve(taskId, data) {
    return request({ method: 'POST', url: `${OPERATION_COMPLETION_PAGE.apiUrl}${encodeURIComponent(taskId)}/approve/`, data,
      timeout: 90000, meta: { module: 'MES', explicitBusinessAction: true } })
  },
  withdrawReplace(taskId, data) {
    return request({ method: 'POST', url: `${OPERATION_COMPLETION_PAGE.apiUrl}${encodeURIComponent(taskId)}/withdraw-and-replace/`, data,
      timeout: 90000, meta: { module: 'MES', explicitBusinessAction: true } })
  },
})
