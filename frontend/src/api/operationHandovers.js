import { timedMesRead } from '@/meta/runtime/mesReadTiming.js'
import request from './request'
import { OPERATION_HANDOVER_PAGE } from '@/meta/runtime/operationHandoverContract.js'

const allowed = /^\/api\/planning\/operation-(?:handovers|outputs)\/(?:[a-z-]+\/|[a-z-]+\/[a-z-]+\/|[1-9]\d*\/[a-z-]+\/|[a-z-]+\/[1-9]\d*\/[a-z-]+\/)?$/
export const operationHandoversApi = Object.freeze({
  read(params = {}) {
    return timedMesRead(()=>request({ method: 'GET', url: OPERATION_HANDOVER_PAGE.apiUrl, params, timeout: 90000,
      meta: { module: 'MES', readOnly: true } }),OPERATION_HANDOVER_PAGE.apiUrl)
  },
  readOutputs(params = {}) {
    return timedMesRead(()=>request({ method: 'GET', url: OPERATION_HANDOVER_PAGE.outputApiUrl, params, timeout: 90000,
      meta: { module: 'MES', readOnly: true } }),OPERATION_HANDOVER_PAGE.outputApiUrl)
  },
  execute(action, data) {
    if (action?.httpMethod !== 'POST' || !allowed.test(action.apiPath || '')) {
      throw new Error('正式工序交接动作接口未通过登记校验。')
    }
    return request({ method: 'POST', url: action.apiPath, data, timeout: 90000,
      meta: { module: 'MES', explicitBusinessAction: true, actionCode: action.actionCode } })
  },
})
