import request from './request'
import { WORKSHOP_TASK_PAGE } from '@/meta/runtime/workshopTaskDispatchContract.js'

export const workshopTasksApi = Object.freeze({
  read(params = {}) {
    return request({ method: 'GET', url: WORKSHOP_TASK_PAGE.apiUrl, params, timeout: 90000,
      meta: { module: 'MES', readOnly: true } })
  },
  saveDraft(data) {
    return request({ method: 'POST', url: `${WORKSHOP_TASK_PAGE.apiUrl}draft/`, data, timeout: 90000,
      meta: { module: 'MES', explicitBusinessAction: true } })
  },
  dispatch(taskId, data) {
    return request({ method: 'POST', url: `${WORKSHOP_TASK_PAGE.apiUrl}${encodeURIComponent(taskId)}/dispatch/`, data, timeout: 90000,
      meta: { module: 'MES', explicitBusinessAction: true } })
  },
})
