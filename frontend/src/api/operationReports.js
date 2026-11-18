import { timedMesRead } from '@/meta/runtime/mesReadTiming.js'
import request from './request'
import { OPERATION_REPORT_PAGE } from '@/meta/runtime/operationReportContract.js'

export const operationReportsApi = Object.freeze({
  read(params = {}) {
    return timedMesRead(()=>request({ method: 'GET', url: OPERATION_REPORT_PAGE.apiUrl, params, timeout: 90000,
      meta: { module: 'MES', readOnly: true } }),OPERATION_REPORT_PAGE.apiUrl)
  },
  report(taskId, data) {
    return request({ method: 'POST', url: `${OPERATION_REPORT_PAGE.apiUrl}${encodeURIComponent(taskId)}/report/`, data,
      timeout: 90000, meta: { module: 'MES', explicitBusinessAction: true } })
  },
  confirmExecution(taskId, data) {
    return request({ method: 'POST', url: `${OPERATION_REPORT_PAGE.apiUrl}${encodeURIComponent(taskId)}/confirm-execution/`, data,
      timeout: 90000, meta: { module: 'MES', explicitBusinessAction: true } })
  },
})
